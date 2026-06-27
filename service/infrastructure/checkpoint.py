# service/infrastructure/checkpoint.py
"""
Checkpoint store abstraction and local directory implementation.
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path

class CheckpointStore(ABC):
    """
    Abstractions for loading and saving session checkpoints, enabling state
    persistence across application restarts.
    """
    @abstractmethod
    async def save_checkpoint(self, session_id: str, state_data: Dict[str, Any]) -> None:
        """
        Saves workflow context state data.
        """
        pass

    @abstractmethod
    async def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Loads workflow context state data.
        """
        pass

    @abstractmethod
    async def delete_checkpoint(self, session_id: str) -> None:
        """
        Removes checkpoint file associated with session.
        """
        pass


class LocalCheckpointStore(CheckpointStore):
    """
    Concrete implementation of CheckpointStore storing states in a local directory
    as JSON files.
    """
    def __init__(self, checkpoint_dir: str) -> None:
        self.directory = Path(checkpoint_dir)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _get_path(self, session_id: str) -> Path:
        return self.directory / f"{session_id}.json"

    async def save_checkpoint(self, session_id: str, state_data: Dict[str, Any]) -> None:
        file_path = self._get_path(session_id)
        # Handle datetime serialization if any
        # Pydantic dicts can be serialized directly
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(state_data, f, indent=2, default=str)
        os.replace(temp_path, file_path)

    async def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_path(session_id)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    async def delete_checkpoint(self, session_id: str) -> None:
        file_path = self._get_path(session_id)
        if file_path.exists():
            file_path.unlink()
