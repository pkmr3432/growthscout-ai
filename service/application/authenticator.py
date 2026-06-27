# service/application/authenticator.py
"""
Interface for Authenticator services verifying client access keys and credentials.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class Authenticator(ABC):
    """
    Authoritative boundary abstraction defining standard contract for API key
    and JWT authentication checks.
    """
    @abstractmethod
    async def authenticate(self, api_key: str) -> bool:
        """
        Verifies if the provided API key is valid.
        """
        pass

    @abstractmethod
    async def get_client_scopes(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves scopes and metadata associated with the authenticated client.
        """
        pass
