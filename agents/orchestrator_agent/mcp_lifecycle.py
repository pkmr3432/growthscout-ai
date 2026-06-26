# agents/orchestrator_agent/mcp_lifecycle.py
import asyncio
import sys
import os
import logging
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class MCPProcessState(str, Enum):
    STARTING = "STARTING"
    READY = "READY"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"

class MCPProcessInstance:
    def __init__(self, server_name: str, command: str, args: List[str], env: Dict[str, str]):
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env
        self.process: Optional[asyncio.subprocess.Process] = None
        self.state = MCPProcessState.FAILED
        self.ref_count = 0

class MCPLifecycleManager:
    def __init__(self, startup_timeout: float = 5.0, shutdown_timeout: float = 3.0) -> None:
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self._servers: Dict[str, MCPProcessInstance] = {}
        self._lock = asyncio.Lock()

    def get_state(self, server_name: str) -> MCPProcessState:
        """Return the current state of the server or FAILED if not known."""
        if server_name in self._servers:
            return self._servers[server_name].state
        return MCPProcessState.FAILED

    def get_ref_count(self, server_name: str) -> int:
        """Return reference count of the server."""
        if server_name in self._servers:
            return self._servers[server_name].ref_count
        return 0

    async def start_server(
        self, server_name: str, command: str, args: List[str], env: Dict[str, str]
    ) -> MCPProcessState:
        """Directly start an MCP server process."""
        logger.info(f"Starting MCP server '{server_name}' using command: {command} {args}")
        
        # Canonicalize python command to use current sys.executable
        cmd = command
        if command == "python" or command == "python3":
            cmd = sys.executable

        # Clean/inject environment variables
        full_env = dict(os.environ)
        full_env.update(env)

        # Run process
        try:
            process = await asyncio.create_subprocess_exec(
                cmd, *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env
            )
            
            instance = MCPProcessInstance(server_name, command, args, env)
            instance.process = process
            instance.state = MCPProcessState.STARTING
            self._servers[server_name] = instance
            return MCPProcessState.STARTING
        except Exception as e:
            logger.error(f"Failed to start subprocess for MCP server '{server_name}': {str(e)}")
            raise RuntimeError(f"Failed to start MCP server '{server_name}': {str(e)}")

    async def verify_ready(self, server_name: str) -> bool:
        """Verify server is ready (not exited immediately) within startup_timeout."""
        if server_name not in self._servers:
            return False

        instance = self._servers[server_name]
        if instance.process is None:
            instance.state = MCPProcessState.FAILED
            return False

        # Wait a short stabilization period, then check if it's still alive
        try:
            # Let it stabilize for 0.5s or up to startup_timeout
            stabilization_time = min(0.5, self.startup_timeout)
            await asyncio.sleep(stabilization_time)
            
            if instance.process.returncode is not None:
                # Process exited immediately
                stderr_data = b""
                try:
                    stderr_data = await asyncio.wait_for(instance.process.stderr.read(), timeout=0.1)
                except Exception:
                    pass
                stderr_str = stderr_data.decode().strip()
                logger.error(
                    f"MCP server '{server_name}' exited immediately with code {instance.process.returncode}. Stderr: {stderr_str}"
                )
                instance.state = MCPProcessState.FAILED
                return False
            
            # Still running!
            instance.state = MCPProcessState.READY
            logger.info(f"MCP server '{server_name}' is verified READY.")
            return True

        except Exception as e:
            logger.error(f"Error verifying readiness of MCP server '{server_name}': {str(e)}")
            instance.state = MCPProcessState.FAILED
            return False

    async def acquire(
        self, server_name: str, command: str, args: List[str], env: Dict[str, str]
    ) -> MCPProcessState:
        """Acquire a reference to the MCP server. Starts it if not running."""
        async with self._lock:
            if server_name in self._servers:
                instance = self._servers[server_name]
                if instance.state in (MCPProcessState.STARTING, MCPProcessState.READY):
                    instance.ref_count += 1
                    logger.info(f"Reused MCP server '{server_name}'. Ref count: {instance.ref_count}")
                    return instance.state

            # Start and verify
            await self.start_server(server_name, command, args, env)
            instance = self._servers[server_name]
            ready = await self.verify_ready(server_name)
            if not ready:
                instance.state = MCPProcessState.FAILED
                raise RuntimeError(f"MCP server '{server_name}' failed readiness verification on startup.")
            
            instance.ref_count = 1
            logger.info(f"Acquired new MCP server '{server_name}'. Ref count: {instance.ref_count}")
            return instance.state

    async def release(self, server_name: str) -> None:
        """Release a reference to the MCP server. Shuts it down if ref count reaches zero."""
        async with self._lock:
            if server_name not in self._servers:
                return

            instance = self._servers[server_name]
            if instance.ref_count <= 0:
                return

            instance.ref_count -= 1
            logger.info(f"Released reference to MCP server '{server_name}'. Ref count: {instance.ref_count}")
            
            if instance.ref_count == 0:
                await self.shutdown_server(server_name)

    async def shutdown_server(self, server_name: str) -> None:
        """Gracefully shut down a single MCP server."""
        if server_name not in self._servers:
            return

        instance = self._servers[server_name]
        if instance.process is None:
            instance.state = MCPProcessState.TERMINATED
            return

        instance.state = MCPProcessState.SHUTTING_DOWN
        logger.info(f"Shutting down MCP server '{server_name}'...")

        try:
            # 1. Try graceful SIGTERM
            instance.process.terminate()
            try:
                await asyncio.wait_for(instance.process.wait(), timeout=self.shutdown_timeout)
                instance.state = MCPProcessState.TERMINATED
                logger.info(f"MCP server '{server_name}' terminated gracefully.")
            except asyncio.TimeoutError:
                # 2. Force SIGKILL if it hangs
                logger.warning(f"MCP server '{server_name}' did not exit in time. Killing...")
                instance.process.kill()
                await instance.process.wait()
                instance.state = MCPProcessState.TERMINATED
                logger.info(f"MCP server '{server_name}' killed successfully.")
        except Exception as e:
            logger.error(f"Error during shutdown of MCP server '{server_name}': {str(e)}")
            instance.state = MCPProcessState.FAILED
        finally:
            instance.ref_count = 0

    async def shutdown_all(self) -> None:
        """Shut down all registered MCP servers."""
        logger.info("Shutting down all managed MCP servers...")
        # Take a copy of keys to avoid modification during iteration
        for server_name in list(self._servers.keys()):
            await self.shutdown_server(server_name)
