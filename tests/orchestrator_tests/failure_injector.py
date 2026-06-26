# tests/orchestrator_tests/failure_injector.py
import asyncio
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from typing import Dict, Any, Generator

from agents.orchestrator_agent.error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from agents.orchestrator_agent.service_names import ServiceName

class FailureInjector:
    def __init__(self) -> None:
        self.active_failures: Dict[str, Dict[str, Any]] = {}
        self._patches = []

    def inject_failure(self, service: str, failure_type: str, details: Dict[str, Any] = None) -> None:
        """
        Configure a failure scenario.
        service can be: "gemini", "mcp", "firestore", "network", "checkpoint", "recovery"
        """
        self.active_failures[service] = {
            "type": failure_type,
            "details": details or {}
        }

    def clear(self) -> None:
        self.active_failures.clear()

    @contextmanager
    def activate(self) -> Generator[FailureInjector, None, None]:
        """
        A context manager that installs mocks to intercept calls and raise failures when active.
        """
        # Patch WorkflowExecutor._execute_agent_run
        from agents.orchestrator_agent.workflow_executor import WorkflowExecutor
        original_execute_agent_run = WorkflowExecutor._execute_agent_run

        async def patched_execute_agent_run(executor_self, agent_instance, request, output_schema, session_id=None):
            if "gemini" in self.active_failures:
                fail = self.active_failures["gemini"]
                ftype = fail["type"]
                details = fail["details"]

                if ftype == "timeout":
                    # Simulate Gemini timeout by sleeping longer than worker timeout and raising asyncio.TimeoutError
                    timeout_val = details.get("duration", request.timeout + 2.0)
                    await asyncio.sleep(timeout_val)
                    raise asyncio.TimeoutError("Gemini API request timed out")
                
                elif ftype == "auth_failure":
                    raise GrowthScoutRuntimeError(
                        error_code=RuntimeErrorCode.AUTH_ERROR,
                        message="API key invalid: unauthorized user",
                        service=ServiceName.GEMINI,
                        retryable=False,
                    )
                
                elif ftype == "quota_failure":
                    raise GrowthScoutRuntimeError(
                        error_code=RuntimeErrorCode.RATE_LIMIT,
                        message="429: Too many requests, quota exceeded",
                        service=ServiceName.GEMINI,
                        retryable=True,
                    )
                
                elif ftype == "slow_response":
                    await asyncio.sleep(details.get("duration", 2.0))
                    # Fall back to original run

            # Also check network failures on worker runs
            if "network" in self.active_failures:
                fail = self.active_failures["network"]
                ftype = fail["type"]
                if ftype == "interruption":
                    raise GrowthScoutRuntimeError(
                        error_code=RuntimeErrorCode.NETWORK_ERROR,
                        message="Network connection reset by peer",
                        service=ServiceName.GEMINI,
                        retryable=True,
                    )

            return await original_execute_agent_run(executor_self, agent_instance, request, output_schema, session_id)

        # Patch MCPLifecycleManager.acquire
        from agents.orchestrator_agent.mcp_lifecycle import MCPLifecycleManager
        original_mcp_acquire = MCPLifecycleManager.acquire

        async def patched_mcp_acquire(mcp_self, server_name, command, args, env):
            if "mcp" in self.active_failures:
                fail = self.active_failures["mcp"]
                ftype = fail["type"]
                if ftype == "unavailable":
                    raise RuntimeError(f"MCP server {server_name} failed readiness verification on startup")
                elif ftype == "disconnect":
                    # simulate acquisition succeeds but drops immediately or process terminates
                    await original_mcp_acquire(mcp_self, server_name, command, args, env)
                    instance = mcp_self._servers[server_name]
                    if instance.process:
                        instance.process.terminate()
                    return instance.state
            return await original_mcp_acquire(mcp_self, server_name, command, args, env)

        # Patch Firestore client and FirestoreCheckpointInterface operations
        from agents.orchestrator_agent.interfaces.firestore_checkpoint import FirestoreCheckpointInterface
        original_firestore_save = FirestoreCheckpointInterface.save
        original_firestore_load = FirestoreCheckpointInterface.load

        def patched_firestore_save(fs_self, checkpoint):
            if "firestore" in self.active_failures:
                fail = self.active_failures["firestore"]
                ftype = fail["type"]
                details = fail["details"]

                if ftype == "unavailable":
                    raise RuntimeError("Firestore connection failed: host unreachable")
                elif ftype == "timeout":
                    # Sleep internally to trigger firestore timeout
                    import time
                    time.sleep(fs_self.config.firestore_timeout_seconds + 1.0)
                    raise RuntimeError("Firestore operation exceeded timeout limit")

            if "checkpoint" in self.active_failures:
                fail = self.active_failures["checkpoint"]
                ftype = fail["type"]
                if ftype == "partial_write":
                    # Crash halfway through write
                    # We can write to self.db but then raise exception before returning
                    doc_ref = fs_self.db.collection(fs_self.collection_name).document(f"{checkpoint.session_id}_v{checkpoint.checkpoint_version}")
                    doc_data = checkpoint.model_dump(mode="json")
                    doc_ref.set(doc_data)
                    raise RuntimeError("System crash: partial checkpoint write occurred")

            return original_firestore_save(fs_self, checkpoint)

        def patched_firestore_load(fs_self, session_id):
            if "firestore" in self.active_failures:
                fail = self.active_failures["firestore"]
                ftype = fail["type"]
                if ftype == "unavailable":
                    raise RuntimeError("Firestore connection failed: host unreachable")
                elif ftype == "timeout":
                    import time
                    time.sleep(fs_self.config.firestore_timeout_seconds + 1.0)
                    raise RuntimeError("Firestore load operation exceeded timeout limit")
            return original_firestore_load(fs_self, session_id)

        # Patch ResumabilityController.resume / evaluation
        from agents.orchestrator_agent.interfaces.resumability import ResumabilityController
        original_resume_evaluate = ResumabilityController._evaluate

        def patched_resume_evaluate(rc_self, session_id):
            if "recovery" in self.active_failures:
                fail = self.active_failures["recovery"]
                ftype = fail["type"]
                details = fail["details"]
                if ftype == "slow_recovery":
                    import time
                    time.sleep(details.get("duration", 2.0))
            return original_resume_evaluate(rc_self, session_id)

        # Apply patches
        p1 = patch.object(WorkflowExecutor, "_execute_agent_run", patched_execute_agent_run)
        p2 = patch.object(MCPLifecycleManager, "acquire", patched_mcp_acquire)
        p3 = patch.object(FirestoreCheckpointInterface, "save", patched_firestore_save)
        p4 = patch.object(FirestoreCheckpointInterface, "load", patched_firestore_load)
        p5 = patch.object(ResumabilityController, "_evaluate", patched_resume_evaluate)

        p1.start()
        p2.start()
        p3.start()
        p4.start()
        p5.start()

        self._patches = [p1, p2, p3, p4, p5]

        try:
            yield self
        finally:
            # Stop patches
            for p in self._patches:
                p.stop()
            self.clear()
