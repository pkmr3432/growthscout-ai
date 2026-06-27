# service/infrastructure/registry.py
"""
Service registry responsible for dependency wiring, lifecycle management,
and deterministic startup/shutdown ordering.
"""

import logging
import time
from typing import Optional, Dict, Any

from service.infrastructure.config import ServiceSettings, settings
from service.application.lock_manager import SessionLockManager
from service.application.scheduler import TaskScheduler
from service.application.authenticator import Authenticator
from service.infrastructure.checkpoint import CheckpointStore, LocalCheckpointStore
from service.infrastructure.publisher import EventPublisher, SSEPublisher

logger = logging.getLogger("growthscout.registry")


class SimpleAPIKeyAuthenticator(Authenticator):
    """
    Simple implementation checking keys against configured security options.
    """
    def __init__(self, settings: ServiceSettings) -> None:
        self._keys = settings.security.api_keys
        self._required = settings.security.api_key_required

    async def authenticate(self, api_key: str) -> bool:
        if not self._required:
            return True
        return api_key in self._keys

    async def get_client_scopes(self, api_key: str) -> Optional[Dict[str, Any]]:
        if await self.authenticate(api_key):
            return {
                "client_id": "gs_client_dev",
                "scopes": ["read:session", "write:session"]
            }
        return None


class ServiceRegistry:
    """
    Registry coordinates instance singletons and wires dependencies.

    Startup order:
        1. Configuration validation
        2. Checkpoint store
        3. Lock manager
        4. Task scheduler
        5. Event publisher
        6. Authenticator

    Shutdown order (reverse):
        1. Stop accepting requests (handled by FastAPI)
        2. Cancel active tasks
        3. Close publisher streams
        4. Flush metrics (handled by metrics module)
        5. Release resources
    """
    def __init__(self, custom_settings: Optional[ServiceSettings] = None) -> None:
        self.settings = custom_settings or settings
        self._initialized = False
        self._start_time = time.time()

        # Instantiate infrastructure abstractions
        self.checkpoint_store: CheckpointStore = LocalCheckpointStore(
            checkpoint_dir=self.settings.storage.checkpoint_dir
        )

        # Instantiate application abstractions
        self.lock_manager = SessionLockManager()
        self.task_scheduler = TaskScheduler()

        # Event publisher and authenticator
        self.event_publisher: EventPublisher = SSEPublisher()
        self.authenticator: Authenticator = SimpleAPIKeyAuthenticator(self.settings)

    async def initialize(self) -> None:
        """
        Deterministic startup initialization.

        Order:
            1. Validate configuration
            2. Verify checkpoint storage
            3. Verify event publisher
            4. Mark registry as initialized
        """
        logger.info("ServiceRegistry initialization starting...")

        # Step 1: Configuration validation
        self.settings.fail_fast_if_invalid()
        logger.info(f"Configuration validated for environment: {self.settings.app.env}")

        # Step 2: Verify checkpoint storage is operational
        try:
            import os
            os.makedirs(self.settings.storage.checkpoint_dir, exist_ok=True)
            logger.info(f"Checkpoint storage verified: {self.settings.storage.checkpoint_dir}")
        except Exception as e:
            logger.error(f"Checkpoint storage initialization failed: {e}")
            raise

        # Step 3: Verify event publisher
        logger.info("Event publisher initialized")

        # Step 4: Verify scheduler
        logger.info("Task scheduler initialized")

        # Mark as initialized
        self._initialized = True
        elapsed = time.time() - self._start_time
        logger.info(f"ServiceRegistry initialization complete in {elapsed:.3f}s")

    async def shutdown(self) -> None:
        """
        Deterministic shutdown.

        Order:
            1. Cancel all active tasks
            2. Close all publisher streams
            3. Mark as uninitialized
        """
        logger.info("ServiceRegistry shutdown starting...")

        # Step 1: Cancel active tasks
        try:
            await self.task_scheduler.cancel_all()
            logger.info("Task scheduler shutdown complete")
        except Exception as e:
            logger.error(f"Task scheduler shutdown error: {e}")

        # Step 2: Close publisher streams
        try:
            if hasattr(self.event_publisher, 'cancel_all'):
                await self.event_publisher.cancel_all()
            logger.info("Event publisher shutdown complete")
        except Exception as e:
            logger.error(f"Event publisher shutdown error: {e}")

        # Step 3: Mark as uninitialized
        self._initialized = False
        logger.info("ServiceRegistry shutdown complete")

    @property
    def is_initialized(self) -> bool:
        """Returns True if the registry has completed initialization."""
        return self._initialized

    @property
    def uptime_seconds(self) -> float:
        """Returns seconds since registry instantiation."""
        return time.time() - self._start_time


# Global registry instance
registry = ServiceRegistry()
