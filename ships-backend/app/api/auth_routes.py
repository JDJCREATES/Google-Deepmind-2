"""
Authentication Routes

Google OAuth 2.0 authentication endpoints with comprehensive error handling.
Implements secure session management and user profile handling.
"""

from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.base_client import OAuthError
from typing import Optional, Dict, Any
import secrets
import logging

from app.oauth_config import get_oauth_config, SESSION_COOKIE_NAME

logger = logging.getLogger("ships.auth")

router = APIRouter(prefix="/auth", tags=["authentication"])


class AuthError(Exception):
    """Custom authentication error."""
    def __init__(self, error: str, description: str, status_code: int = 400):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(description)


@router.get("/google")
async def google_login(request: Request):
    """
    Initiate Google OAuth flow.
    
    Redirects user to Google consent screen.
    Generates and stores state for CSRF protection.
    
    Returns:
        RedirectResponse to Google OAuth
        
    Raises:
        HTTPException: If OAuth is not configured
    """
    try:
        oauth = get_oauth_config()
        
        if not oauth.is_configured():
            raise AuthError(
                error="not_configured",
                description="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
                status_code=500
            )
        
        # Generate CSRF token
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        
        # Build callback URL
        callback_url = str(request.url_for('google_callback'))
        
        # Get authorization URL
        redirect_uri, _ = oauth.get_authorization_url(callback_url)
        
        logger.info(f"Initiating OAuth flow with callback: {callback_url}")
        return RedirectResponse(redirect_uri)
        
    except AuthError as e:
        logger.error(f"OAuth error: {e.description}")
        raise HTTPException(status_code=e.status_code, detail={
            "error": e.error,
            "description": e.description
        })
    except Exception as e:
        logger.error(f"Unexpected error during OAuth initiation: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "server_error",
            "description": "Failed to initiate authentication"
        })


@router.get("/google/callback")
async def google_callback(request: Request):
    """
    Handle Google OAuth callback.
    
    Exchanges authorization code for access token,
    fetches user profile, and creates session.
    
    Returns:
        RedirectResponse to frontend with session cookie
        
    Raises:
        HTTPException: On OAuth errors
    """
    try:
        oauth = get_oauth_config()
        
        # Verify state for CSRF protection
        stored_state = request.session.get('oauth_state')
        callback_state = request.query_params.get('state')
        
        if not stored_state or stored_state != callback_state:
            raise AuthError(
                error="invalid_state",
                description="CSRF validation failed. Please try logging in again.",
                status_code=400
            )
        
        # Check for OAuth errors
        error = request.query_params.get('error')
        if error:
            error_description = request.query_params.get('error_description', 'Unknown error')
            raise AuthError(
                error=error,
                description=error_description,
                status_code=400
            )
        
        # Exchange code for token
        try:
            token = await oauth.oauth.google.authorize_access_token(request)
        except OAuthError as e:
            logger.error(f"Token exchange failed: {e}")
            raise AuthError(
                error="token_exchange_failed",
                description="Failed to obtain access token from Google",
                status_code=400
            )
        
        # Fetch user profile
        user_info = await oauth.fetch_user_info(token)
        
        if not user_info:
            raise AuthError(
                error="profile_fetch_failed",
                description="Failed to retrieve user profile from Google",
                status_code=500
            )
        
        # Verify email
        if not user_info.get('email_verified'):
            raise AuthError(
                error="email_not_verified",
                description="Please verify your email address with Google first",
                status_code=403
            )
        
        # Create session
        request.session['user'] = {
            'id': user_info['id'],
            'email': user_info['email'],
            'name': user_info['name'],
            'picture': user_info.get('picture'),
            'auth_method': 'google',
        }
        
        # Clear OAuth state
        request.session.pop('oauth_state', None)
        
        logger.info(f"✓ User authenticated: {user_info['email']}")
        
        # Redirect to frontend
        frontend_url = request.url_for('root')  # Adjust based on your frontend route
        return RedirectResponse(url=str(frontend_url))
        
    except AuthError as e:
        logger.error(f"OAuth callback error: {e.description}")
        # Redirect to frontend with error
        error_url = f"/?auth_error={e.error}&auth_error_description={e.description}"
        return RedirectResponse(url=error_url)
    except Exception as e:
        logger.error(f"Unexpected error during OAuth callback: {e}")
        error_url = "/?auth_error=server_error&auth_error_description=Authentication failed"
        return RedirectResponse(url=error_url)


@router.get("/user")
async def get_current_user(request: Request):
    """
    Get currently authenticated user.
    
    Returns:
        JSONResponse with user data or null
    """
    user = request.session.get('user')
    
    if not user:
        return JSONResponse(content={"user": None, "authenticated": False})
    
    return JSONResponse(content={
        "user": user,
        "authenticated": True
    })


@router.post("/logout")
async def logout(request: Request):
    """
    Clear user session.
    
    Returns:
        JSONResponse confirming logout
    """
    request.session.clear()
    logger.info("User logged out")
    
    return JSONResponse(content={
        "success": True,
        "message": "Logged out successfully"
    })
