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
GITHUB_CLIENT_ID = config("GITHUB_CLIENT_ID", default=None)
GITHUB_CLIENT_SECRET = config("GITHUB_CLIENT_SECRET", default=None)
SECRET_KEY = config("SECRET_KEY", default="dev-secret-key-change-in-production")

# Session settings
SESSION_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
SESSION_COOKIE_NAME = "ships_session"


class OAuthConfig:
    """
    OAuth configuration and utilities for Google and GitHub.
    """
    
    def __init__(self):
        """Initialize OAuth configuration."""
        self.oauth = OAuth()
        self._validate_config()
        self._register_clients()
    
    def _validate_config(self) -> None:
        """Validate OAuth configuration."""
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.warning("Google OAuth not configured (GOOGLE_CLIENT_ID/SECRET missing)")
        
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            logger.warning("GitHub OAuth not configured (GITHUB_CLIENT_ID/SECRET missing)")
        
        if (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET) or (GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET):
            logger.info("✓ OAuth configured")
    
    def _register_clients(self) -> None:
        """Register OAuth clients."""
        # Google
        if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
            self.oauth.register(
                name='google',
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                client_kwargs={
                    'scope': 'openid email profile',
                    'prompt': 'select_account',
                    'access_type': 'offline',
                }
            )
            
        # GitHub
        if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
            self.oauth.register(
                name='github',
                client_id=GITHUB_CLIENT_ID,
                client_secret=GITHUB_CLIENT_SECRET,
                access_token_url='https://github.com/login/oauth/access_token',
                access_token_params=None,
                authorize_url='https://github.com/login/oauth/authorize',
                authorize_params=None,
                api_base_url='https://api.github.com/',
                client_kwargs={'scope': 'user:email read:user'},
            )
    
    def is_configured(self, provider: str = 'google') -> bool:
        """Check if specific provider is configured."""
        if provider == 'google':
            return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
        elif provider == 'github':
            return bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)
        return False
    
    async def fetch_user_info(self, provider: str, token: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch user profile from provider.
        """
        try:
            if provider == 'google':
                return await self._fetch_google_user(token)
            elif provider == 'github':
                return await self._fetch_github_user(token)
            return None
        except Exception as e:
            logger.error(f"Error fetching {provider} user info: {e}")
            return None

    async def _fetch_google_user(self, token: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        resp = await self.oauth.google.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            token=token
        )
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        return {
            'id': data.get('sub'),
            'email': data.get('email'),
            'name': data.get('name'),
            'picture': data.get('picture'),
            'email_verified': data.get('email_verified', False),
            'provider': 'google'
        }

    async def _fetch_github_user(self, token: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Fetch user profile
        resp = await self.oauth.github.get('user', token=token)
        if resp.status_code != 200:
            return None
        user_data = resp.json()
        
        # Fetch emails (GitHub doesn't return email in profile if private)
        email_resp = await self.oauth.github.get('user/emails', token=token)
        email = None
        email_verified = False
        
        if email_resp.status_code == 200:
            emails = email_resp.json()
            # Find primary verified email
            primary = next((e for e in emails if e['primary'] and e['verified']), None)
            if not primary:
                 # Fallback to any verified email
                primary = next((e for e in emails if e['verified']), None)
            
            if primary:
                email = primary['email']
                email_verified = True
        
        return {
            'id': str(user_data.get('id')),
            'email': email or user_data.get('email'),
            'name': user_data.get('name') or user_data.get('login'),
            'picture': user_data.get('avatar_url'),
            'email_verified': email_verified,
            'provider': 'github'
        }


# Singleton instance
_oauth_config: Optional[OAuthConfig] = None


def get_oauth_config() -> OAuthConfig:
    """Get or create OAuth configuration singleton."""
    global _oauth_config
    if _oauth_config is None:
        _oauth_config = OAuthConfig()
    return _oauth_config
