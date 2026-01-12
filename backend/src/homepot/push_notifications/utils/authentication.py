"""Authentication utilities for push notification providers.

This module provides common authentication patterns used by different
push notification services including:
- Service account authentication (FCM, Firebase)
- OAuth2 authentication (APNs, WNS)
- API key authentication (Web Push)
- Certificate-based authentication (APNs)
"""

from abc import ABC, abstractmethod
from pathlib import Path
import time
from typing import Any, Dict, Optional, Type

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

try:
    import jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


class Authenticator(ABC):
    """Abstract base class for authentication providers."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize authenticator with configuration.

        Args:
            config: Authentication configuration dictionary
        """
        self.config = config
        self._token: Optional[str] = None
        self._token_expiry: Optional[float] = None

    @abstractmethod
    async def get_auth_header(self) -> Dict[str, str]:
        """Get authentication headers for API requests.

        Returns:
            Dictionary with authentication headers
        """
        pass

    @abstractmethod
    async def refresh_token(self) -> bool:
        """Refresh the authentication token.

        Returns:
            True if refresh successful, False otherwise
        """
        pass

    def is_token_valid(self, buffer_seconds: int = 300) -> bool:
        """Check if current token is valid.

        Args:
            buffer_seconds: Refresh token this many seconds before expiry

        Returns:
            True if token is valid, False if expired or missing
        """
        if not self._token or not self._token_expiry:
            return False

        return time.time() < (self._token_expiry - buffer_seconds)

    async def ensure_valid_token(self) -> None:
        """Ensure we have a valid token, refresh if needed."""
        if not self.is_token_valid():
            await self.refresh_token()


class ServiceAccountAuthenticator(Authenticator):
    """Google Service Account authentication for FCM and other Google services.

    This authenticator uses service account JSON files to authenticate
    with Google Cloud services like Firebase Cloud Messaging.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize service account authenticator.

        Args:
            config: Configuration dict containing service_account_path and scopes
        """
        super().__init__(config)

        if not GOOGLE_AUTH_AVAILABLE:
            raise ImportError(
                "google-auth library required for service account authentication"
            )

        self.service_account_path = config.get("service_account_path")
        self.scopes = config.get(
            "scopes", ["https://www.googleapis.com/auth/firebase.messaging"]
        )

        if not self.service_account_path:
            raise ValueError(
                "service_account_path required for ServiceAccountAuthenticator"
            )

        self._credentials: Optional[service_account.Credentials] = None
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load service account credentials from file."""
        if self.service_account_path is None:
            raise ValueError("service_account_path is required")

        service_account_file = Path(self.service_account_path)
        if not service_account_file.exists():
            raise FileNotFoundError(
                f"Service account file not found: {self.service_account_path}"
            )

        self._credentials = service_account.Credentials.from_service_account_file(
            str(service_account_file), scopes=self.scopes
        )

    async def get_auth_header(self) -> Dict[str, str]:
        """Get Bearer token authentication header.

        Returns:
            Dictionary with Authorization header
        """
        await self.ensure_valid_token()
        return {"Authorization": f"Bearer {self._token}"}

    async def refresh_token(self) -> bool:
        """Refresh the OAuth2 access token.

        Returns:
            True if refresh successful, False otherwise
        """
        try:
            if not self._credentials:
                return False

            request = Request()
            self._credentials.refresh(request)

            self._token = self._credentials.token
            self._token_expiry = time.time() + 3600  # 1 hour from now

            return True

        except Exception:
            return False


class OAuth2Authenticator(Authenticator):
    """OAuth2 authentication for services like Microsoft WNS.

    This authenticator handles OAuth2 client credentials flow
    for services that require OAuth2 authentication.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize OAuth2 authenticator.

        Args:
            config: Configuration dict containing OAuth2 credentials and URLs
        """
        super().__init__(config)

        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.token_url = config.get("token_url")
        self.scope = config.get("scope")

        if not all([self.client_id, self.client_secret, self.token_url]):
            raise ValueError(
                "client_id, client_secret, and token_url required for OAuth2"
            )

    async def get_auth_header(self) -> Dict[str, str]:
        """Get Bearer token authentication header.

        Returns:
            Dictionary with Authorization header
        """
        await self.ensure_valid_token()
        return {"Authorization": f"Bearer {self._token}"}

    async def refresh_token(self) -> bool:
        """Refresh OAuth2 access token using client credentials flow.

        Returns:
            True if refresh successful, False otherwise
        """
        import aiohttp

        try:
            if self.token_url is None:
                raise ValueError("token_url is required")

            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            if self.scope:
                data["scope"] = self.scope

            async with aiohttp.ClientSession() as session:
                async with session.post(self.token_url, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self._token = token_data.get("access_token")
                        expires_in = token_data.get("expires_in", 3600)
                        self._token_expiry = time.time() + expires_in
                        return True
                    else:
                        return False

        except Exception:
            return False


class APIKeyAuthenticator(Authenticator):
    """Simple API key authentication for services like Web Push VAPID.

    This authenticator handles API key-based authentication
    where the key is passed in headers or URL parameters.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize API key authenticator.

        Args:
            config: Configuration dict containing api_key and optional header_name
        """
        super().__init__(config)

        self.api_key = config.get("api_key")
        self.header_name = config.get("header_name", "Authorization")
        self.header_prefix = config.get("header_prefix", "key=")

        if not self.api_key:
            raise ValueError("api_key required for APIKeyAuthenticator")

        # API keys don't expire by default
        self._token = self.api_key
        self._token_expiry = time.time() + (365 * 24 * 3600)  # 1 year

    async def get_auth_header(self) -> Dict[str, str]:
        """Get API key authentication header.

        Returns:
            Dictionary with API key header
        """
        return {self.header_name: f"{self.header_prefix}{self._token}"}

    async def refresh_token(self) -> bool:
        """Refresh API key token (no-op for API keys).

        Returns:
            Always True for API keys
        """
        return True


class JWTAuthenticator(Authenticator):
    """JWT-based authentication for services like APNs.

    This authenticator creates and manages JWT tokens for services
    that use JWT-based authentication like Apple Push Notification Service.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize JWT authenticator.

        Args:
            config: Configuration dict containing JWT credentials and settings
        """
        super().__init__(config)

        if not JWT_AVAILABLE:
            raise ImportError("PyJWT library required for JWT authentication")

        self.key_id = config.get("key_id")
        self.team_id = config.get("team_id")
        self.private_key_path = config.get("private_key_path")
        self.algorithm = config.get("algorithm", "ES256")

        if not all([self.key_id, self.team_id, self.private_key_path]):
            raise ValueError("key_id, team_id, and private_key_path required for JWT")

        self._private_key: Optional[str] = None
        self._load_private_key()

    def _load_private_key(self) -> None:
        """Load private key from file."""
        if self.private_key_path is None:
            raise ValueError("private_key_path is required")

        key_file = Path(self.private_key_path)
        if not key_file.exists():
            raise FileNotFoundError(
                f"Private key file not found: {self.private_key_path}"
            )

        self._private_key = key_file.read_text()

    async def get_auth_header(self) -> Dict[str, str]:
        """Get Bearer JWT authentication header.

        Returns:
            Dictionary with Authorization header
        """
        await self.ensure_valid_token()
        return {"Authorization": f"Bearer {self._token}"}

    async def refresh_token(self) -> bool:
        """Generate a new JWT token.

        Returns:
            True if token generation successful, False otherwise
        """
        try:
            if not self._private_key:
                return False

            # JWT payload
            now = int(time.time())
            payload = {
                "iss": self.team_id,
                "iat": now,
                "exp": now + 3600,  # 1 hour expiry
            }

            # JWT headers
            headers = {
                "kid": self.key_id,
                "alg": self.algorithm,
            }

            # Generate JWT
            self._token = jwt.encode(
                payload=payload,
                key=self._private_key,
                algorithm=self.algorithm,
                headers=headers,
            )

            self._token_expiry = now + 3600
            return True

        except Exception:
            return False


# Factory function for creating authenticators
def create_authenticator(auth_type: str, config: Dict[str, Any]) -> Authenticator:
    """Create an authenticator based on type.

    Args:
        auth_type: Type of authenticator (service_account, oauth2, api_key, jwt)
        config: Authentication configuration

    Returns:
        Appropriate authenticator instance

    Raises:
        ValueError: If auth_type is not supported
    """
    authenticators: Dict[str, Type[Authenticator]] = {
        "service_account": ServiceAccountAuthenticator,
        "oauth2": OAuth2Authenticator,
        "api_key": APIKeyAuthenticator,
        "jwt": JWTAuthenticator,
    }

    if auth_type not in authenticators:
        raise ValueError(f"Unsupported auth type: {auth_type}")

    authenticator_class = authenticators[auth_type]
    return authenticator_class(config)
