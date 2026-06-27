# service/application/lock_manager.py
"""
Abstraction to manage session locking, preventing concurrent orchestrations on the same session.
"""

import asyncio
from typing import Dict

class SessionLockManager:
    """
    Manages session-level locks in memory to prevent concurrent workflows
    executing under identical session IDs.
    """
    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def acquire(self, session_id: str) -> bool:
        """
        Attempts to acquire a lock for a session.
        Returns True if acquired successfully; False if already locked.
        """
        async with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            
            lock = self._locks[session_id]
            if lock.locked():
                return False
                
            await lock.acquire()
            return True

    async def release(self, session_id: str) -> None:
        """
        Releases the lock for a session.
        """
        async with self._global_lock:
            if session_id in self._locks:
                lock = self._locks[session_id]
                if lock.locked():
                    lock.release()

    async def is_locked(self, session_id: str) -> bool:
        """
        Checks if a lock is currently held for the session.
        """
        async with self._global_lock:
            if session_id in self._locks:
                return self._locks[session_id].locked()
            return False
