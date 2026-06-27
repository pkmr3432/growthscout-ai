# service/application/scheduler.py
"""
Task scheduler implementation with timeout, cancellation, orphan cleanup, and shutdown controls.
"""

import asyncio
import logging
from typing import Dict, Optional, Callable, Awaitable

logger = logging.getLogger("growthscout.scheduler")

class TaskScheduler:
    """
    Tracks and manages background asyncio execution tasks, enforcing timeouts,
    orchestrating cleanup, and implementing graceful shutdown boundaries.
    """
    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._global_lock = asyncio.Lock()

    async def schedule_task(
        self,
        session_id: str,
        coro: Awaitable,
        timeout_seconds: Optional[float] = None,
        on_done: Optional[Callable[[asyncio.Task], None]] = None
    ) -> bool:
        """
        Schedules a workflow run coroutine task in the background.
        If timeout_seconds is set, wraps execution in an asyncio.wait_for block.
        """
        async with self._global_lock:
            # Ensure no active task is running for this session
            if session_id in self._tasks and not self._tasks[session_id].done():
                return False

            # Wrap in timeout if requested
            if timeout_seconds is not None:
                execution_coro = asyncio.wait_for(coro, timeout=timeout_seconds)
            else:
                execution_coro = coro

            task = asyncio.create_task(execution_coro, name=f"task_{session_id}")
            self._tasks[session_id] = task

            def clean_up(t: asyncio.Task) -> None:
                asyncio.create_task(self._remove_task(session_id))
                if on_done:
                    try:
                        on_done(t)
                    except Exception as e:
                        logger.error(f"Error in on_done task callback: {e}")

            task.add_done_callback(clean_up)
            return True

    async def cancel_task(self, session_id: str) -> bool:
        """
        Cancels the active background task for a given session.
        Returns True if a task was found and cancelled; False otherwise.
        """
        async with self._global_lock:
            if session_id in self._tasks:
                task = self._tasks[session_id]
                if not task.done():
                    task.cancel()
                    return True
            return False

    async def is_task_running(self, session_id: str) -> bool:
        """
        Returns True if the background task is actively running.
        """
        async with self._global_lock:
            if session_id in self._tasks:
                return not self._tasks[session_id].done()
            return False

    async def cleanup_orphan_tasks(self) -> None:
        """
        Scans track registry and discards completed/abandoned tasks.
        """
        async with self._global_lock:
            done_keys = [k for k, t in self._tasks.items() if t.done()]
            for key in done_keys:
                self._tasks.pop(key, None)

    async def graceful_shutdown(self, timeout_seconds: float = 10.0) -> None:
        """
        Cancels all active tasks and waits up to timeout_seconds for termination.
        """
        async with self._global_lock:
            active_tasks = [t for t in self._tasks.values() if not t.done()]
            if not active_tasks:
                return

            logger.info(f"Gracefully shutting down {len(active_tasks)} active background tasks...")
            for task in active_tasks:
                task.cancel()

            # Wait for all tasks to acknowledge cancellation
            try:
                await asyncio.wait_for(
                    asyncio.gather(*active_tasks, return_exceptions=True),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning("Graceful shutdown timeout reached; some tasks may not have completed cleanups.")
            
            self._tasks.clear()

    async def _remove_task(self, session_id: str) -> None:
        async with self._global_lock:
            if session_id in self._tasks:
                task = self._tasks[session_id]
                if task.done():
                    self._tasks.pop(session_id, None)

    async def cancel_all(self, timeout_seconds: float = 10.0) -> None:
        """
        Alias for graceful_shutdown used by ServiceRegistry.shutdown().
        Cancels all active tasks and waits for termination.
        """
        await self.graceful_shutdown(timeout_seconds=timeout_seconds)
