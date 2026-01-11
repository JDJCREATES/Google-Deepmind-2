"""
Authentication Routes

Google OAuth 2.0 authentication endpoints with comprehensive error handling.
Implements secure session management and user profile handling.
"""

from fastapi import APIRouter, Request, HTTPException, Response, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.base_client import OAuthError
from typing import Optional, Dict, Any
import secrets
import logging

from app.oauth_config import get_oauth_config, SESSION_COOKIE_NAME
from app.database import get_session

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
        
        # Build callback URL
        callback_url = str(request.url_for('google_callback'))
        
        # Use authlib's async authorize_redirect method
        # This automatically generates state and sets it in the session
        return await oauth.oauth.google.authorize_redirect(request, callback_url)
        
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
async def google_callback(request: Request, db: AsyncSession = Depends(get_session)):
    """
    Handle Google OAuth callback.
    
    Exchanges authorization code for access token,
    fetches user profile, creates/updates user in database,
    and creates session.
    
    Returns:
        RedirectResponse to frontend with session cookie
        
    Raises:
        HTTPException: On OAuth errors
    """
    try:
        oauth = get_oauth_config()
        
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
            logger.info(f"Callback Request URL: {request.url}")
            token = await oauth.oauth.google.authorize_access_token(request)
        except OAuthError as e:
            logger.error(f"Token exchange failed: {e}")
            # Include the specific error in the description for debugging
            raise AuthError(
                error="token_exchange_failed",
                description=f"Failed to obtain access token: {str(e)}",
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
        
        # Find or create user in database
        from sqlalchemy import select
        from app.models import User
        from datetime import datetime
        
        result = await db.execute(
            select(User).where(User.google_id == user_info['id'])
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing user
            user.name = user_info['name']
            user.avatar_url = user_info.get('picture')
            user.last_login_at = datetime.utcnow()
        else:
            # Create new user with free tier
            user = User(
                email=user_info['email'],
                name=user_info['name'],
                google_id=user_info['id'],
                avatar_url=user_info.get('picture'),
                tier='free',
                subscription_status='inactive',
                last_login_at=datetime.utcnow()
            )
            db.add(user)
        
        await db.commit()
        await db.refresh(user)
        
        # Create session
        request.session['user'] = {
            'id': str(user.id),
            'email': user.email,
            'name': user.name,
            'picture': user.avatar_url,
            'tier': user.tier,
            'auth_method': 'google',
        }
        
        logger.info(f"✓ User authenticated: {user.email} (tier: {user.tier})")
        
        # Redirect to frontend
        frontend_url = request.url_for('root')
        return RedirectResponse(url=str(frontend_url))
        
    except AuthError as e:
        logger.error(f"OAuth callback error: {e.description}")
        # Redirect to frontend with error
        error_url = f"/?auth_error={e.error}&auth_error_description={e.description}"
        return RedirectResponse(url=error_url)
    except Exception as e:
        logger.error(f"Unexpected error during OAuth callback: {e}", exc_info=True)
        # return specific error for debugging
        import urllib.parse
        safe_error = urllib.parse.quote(str(e))
        
        # Redirect to FRONTEND, not backend root
        import os
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        error_url = f"{frontend_url}/?auth_error=server_error&auth_error_description={safe_error}"
        return RedirectResponse(url=error_url)


@router.get("/user")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_session)):
    """
    Get currently authenticated user with subscription info.
    
    Returns:
        JSONResponse with user data including tier and limits
    """
    session_user = request.session.get('user')
    
    if not session_user:
        return JSONResponse(content={"user": None, "authenticated": False})
    
    # Fetch full user from database
    from sqlalchemy import select
    from app.models import User
    
    try:
        result = await db.execute(
            select(User).where(User.email == session_user['email'])
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # User deleted from DB but session still exists
            request.session.clear()
            return JSONResponse(content={"user": None, "authenticated": False})
        
        # Get tier limits
        limits = user.get_tier_limits()
        
        return JSONResponse(content={
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "picture": user.avatar_url,
                "tier": user.tier,
                "subscription_status": user.subscription_status,
                "auth_method": session_user.get('auth_method', 'google'),
            },
            "limits": {
                "prompts_per_day": limits['prompts_per_day'],
                "max_projects": limits['max_projects'],
                "tokens_per_month": limits['tokens_per_month'],
                "priority_queue": limits['priority_queue'],
            },
            "usage": {
                "prompts_used_today": user.prompts_used_today,
                "tokens_used_month": user.tokens_used_month,
            },
            "authenticated": True
        })
        
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return JSONResponse(content={
            "user": session_user,
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
