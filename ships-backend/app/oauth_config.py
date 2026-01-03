"""
Google OAuth 2.0 Configuration

Modern implementation using Google Identity Services (2025).
Handles OAuth flow, token validation, and user profile retrieval.
"""

import os
from typing import Optional, Dict, Any
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client import OAuthError
from starlette.config import Config
from starlette.datastructures import URL
import logging

logger = logging.getLogger("ships.auth")

# Load environment variables
config = Config(".env")

# OAuth Configuration
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default=None)
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default=None)
SECRET_KEY = config("SECRET_KEY", default="dev-secret-key-change-in-production")

# Session settings
SESSION_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
SESSION_COOKIE_NAME = "ships_session"


class GoogleOAuthConfig:
    """
    Google OAuth configuration and utilities.
    
    Uses Google Identity Services (modern API) with proper error handling
    and security best practices.
    """
    
    def __init__(self):
        """Initialize OAuth configuration."""
        self.oauth = OAuth()
        self._validate_config()
        self._register_google()
    
    def _validate_config(self) -> None:
        """Validate OAuth configuration."""
        if not GOOGLE_CLIENT_ID:
            logger.warning("GOOGLE_CLIENT_ID not set - OAuth will not work")
        if not GOOGLE_CLIENT_SECRET:
            logger.warning("GOOGLE_CLIENT_SECRET not set - OAuth will not work")
        
        if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
            logger.info("✓ Google OAuth configured")
    
    def _register_google(self) -> None:
        """Register Google OAuth client with modern scopes."""
        self.oauth.register(
            name='google',
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile',
                # Use modern Google Identity Services
                'prompt': 'select_account',  # Always show account picker
                'access_type': 'offline',     # Get refresh token
            }
        )
    
    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    
    def get_authorization_url(self, redirect_uri: str) -> tuple[str, str]:
        """
        Generate Google OAuth authorization URL.
        
        Args:
            redirect_uri: Callback URL after OAuth flow
            
        Returns:
            Tuple of (authorization_url, state)
            
        Raises:
            OAuthError: If OAuth client is not configured
        """
        if not self.is_configured():
            raise OAuthError(
                error='not_configured',
                description='Google OAuth credentials not configured'
            )
        
        try:
            return self.oauth.google.authorize_redirect_url(redirect_uri)
        except Exception as e:
            logger.error(f"Failed to generate OAuth URL: {e}")
            raise OAuthError(
                error='authorization_failed',
                description='Failed to generate authorization URL'
            )
    
    async def fetch_user_info(self, token: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch user profile from Google.
        
        Args:
            token: OAuth token dictionary
            
        Returns:
            User profile dict or None if failed
        """
        try:
            # Use userinfo endpoint (modern Google Identity Services)
            resp = await self.oauth.google.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                token=token
            )
            
            if resp.status_code != 200:
                logger.error(f"Failed to fetch user info: {resp.status_code}")
                return None
            
            user_data = resp.json()
            
            # Normalize to our user model
            return {
                'id': user_data.get('sub'),  # Google user ID
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'picture': user_data.get('picture'),
                'email_verified': user_data.get('email_verified', False),
            }
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            return None


# Singleton instance
_oauth_config: Optional[GoogleOAuthConfig] = None


def get_oauth_config() -> GoogleOAuthConfig:
    """Get or create OAuth configuration singleton."""
    global _oauth_config
    if _oauth_config is None:
        _oauth_config = GoogleOAuthConfig()
    return _oauth_config
