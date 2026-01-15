"""
Authentication Routes

Google and GitHub OAuth 2.0 authentication endpoints.
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
import os
import urllib.parse
from datetime import datetime

from app.oauth_config import get_oauth_config, SESSION_COOKIE_NAME
from app.database import get_session
from app.models import User

logger = logging.getLogger("ships.auth")

router = APIRouter(prefix="/auth", tags=["authentication"])


class AuthError(Exception):
    """Custom authentication error."""
    def __init__(self, error: str, description: str, status_code: int = 400):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(description)


async def _initiate_oauth(request: Request, provider: str):
    """Helper to initiate OAuth flow for any provider."""
    try:
        oauth = get_oauth_config()
        
        if not oauth.is_configured(provider):
            raise AuthError(
                error="not_configured",
                description=f"{provider.title()} OAuth is not configured. Please check server logs.",
                status_code=500
            )
        
        # Build callback URL
        callback_url = str(request.url_for(f'{provider}_callback'))
        
        # Authorize
        client = getattr(oauth.oauth, provider)
        return await client.authorize_redirect(request, callback_url)
        
    except AuthError as e:
        logger.error(f"OAuth error: {e.description}")
        raise HTTPException(status_code=e.status_code, detail={
            "error": e.error,
            "description": e.description
        })
    except Exception as e:
        logger.error(f"Unexpected error during {provider} OAuth initiation: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "server_error",
            "description": "Failed to initiate authentication"
        })


async def _handle_oauth_callback(request: Request, db: AsyncSession, provider: str):
    """Helper to handle OAuth callback for any provider."""
    try:
        oauth = get_oauth_config()
        
        # Check for OAuth errors
        error = request.query_params.get('error')
        if error:
            error_description = request.query_params.get('error_description', 'Unknown error')
            raise AuthError(error=error, description=error_description, status_code=400)
        
        # Exchange code for token
        try:
            logger.info(f"Callback Request URL: {request.url}")
            client = getattr(oauth.oauth, provider)
            token = await client.authorize_access_token(request)
        except OAuthError as e:
            logger.error(f"Token exchange failed: {e}")
            raise AuthError(
                error="token_exchange_failed",
                description=f"Failed to obtain access token: {str(e)}",
                status_code=400
            )
        
        # Fetch user profile
        user_info = await oauth.fetch_user_info(provider, token)
        
        if not user_info:
            raise AuthError(
                error="profile_fetch_failed",
                description=f"Failed to retrieve user profile from {provider.title()}",
                status_code=500
            )
        
        # Verify email
        if not user_info.get('email_verified') and provider == 'google':
             raise AuthError(
                error="email_not_verified",
                description="Please verify your email address first",
                status_code=403
            )
            
        if not user_info.get('email'):
             raise AuthError(
                error="email_required",
                description="No email address provided by identity provider",
                status_code=400
            )
        
        # Find or create user in database
        from sqlalchemy import select, or_
        
        # Try to find by provider ID first, then by email
        stmt = select(User).where(
            or_(
                User.email == user_info['email'],
                getattr(User, f"{provider}_id") == user_info['id']
            )
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing user
            # Only update avatar if default or from same provider
            # This prevents overwriting a custom avatar or other provider's avatar unnecessarily
            is_default_avatar = not user.avatar_url
            is_google_avatar = user.avatar_url and 'googleusercontent.com' in user.avatar_url
            is_github_avatar = user.avatar_url and 'githubusercontent.com' in user.avatar_url
            
            should_update_avatar = is_default_avatar or \
                                   (provider == 'google' and is_google_avatar) or \
                                   (provider == 'github' and is_github_avatar)
            
            if should_update_avatar and user_info.get('picture'):
                 user.avatar_url = user_info.get('picture')
            
            # Link provider ID if missing
            if provider == 'google' and not user.google_id:
                user.google_id = user_info['id']
            elif provider == 'github' and not user.github_id:
                user.github_id = user_info['id']
                
            user.last_login_at = datetime.utcnow()
        else:
            # Create new user
            user = User(
                email=user_info['email'],
                name=user_info['name'],
                avatar_url=user_info.get('picture'),
                tier='free',
                subscription_status='inactive',
                last_login_at=datetime.utcnow()
            )
            if provider == 'google':
                user.google_id = user_info['id']
            elif provider == 'github':
                user.github_id = user_info['id']
                
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
            'auth_method': provider,
        }
        
        logger.info(f"✓ User authenticated via {provider}: {user.email}")
        
        # Redirect to frontend
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=str(frontend_url))
        
    except AuthError as e:
        logger.error(f"OAuth callback error: {e.description}")
        safe_error = urllib.parse.quote(e.description)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        error_url = f"{frontend_url}/?auth_error={e.error}&auth_error_description={safe_error}"
        return RedirectResponse(url=error_url)
    except Exception as e:
        logger.error(f"Unexpected error during OAuth callback: {e}", exc_info=True)
        safe_error = urllib.parse.quote(str(e))
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        error_url = f"{frontend_url}/?auth_error=server_error&auth_error_description={safe_error}"
        return RedirectResponse(url=error_url)


# --- Google Routes ---

@router.get("/google")
async def google_login(request: Request):
    """Initiate Google OAuth flow."""
    return await _initiate_oauth(request, 'google')

@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_session)):
    """Handle Google OAuth callback."""
    return await _handle_oauth_callback(request, db, 'google')


# --- GitHub Routes ---

@router.get("/github")
async def github_login(request: Request):
    """Initiate GitHub OAuth flow."""
    return await _initiate_oauth(request, 'github')

@router.get("/github/callback")
async def github_callback(request: Request, db: AsyncSession = Depends(get_session)):
    """Handle GitHub OAuth callback."""
    return await _handle_oauth_callback(request, db, 'github')


# --- Account Linking Routes ---

@router.get("/github/link")
async def github_link_start(request: Request):
    """
    Initiate GitHub OAuth flow for account linking.
    
    User must already be authenticated (via Google).
    This will link their GitHub account to their existing user.
    """
    session_user = request.session.get('user')
    if not session_user:
        raise HTTPException(status_code=401, detail="Must be logged in to link accounts")
    
    # Check if GitHub OAuth is configured
    oauth = get_oauth_config()
    if not oauth.is_configured('github'):
        logger.error("GitHub OAuth not configured - cannot link accounts")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}/settings?link_error=github_not_configured")
    
    # Store linking flag in session
    request.session['linking_github'] = True
    request.session['linking_user_email'] = session_user.get('email')
    
    # Proceed with normal OAuth flow
    return await _initiate_oauth(request, 'github')


@router.get("/github/link/callback")
async def github_link_callback(request: Request, db: AsyncSession = Depends(get_session)):
    """
    Handle GitHub OAuth callback for account linking.
    
    Links the GitHub account to the existing user based on session.
    """
    from sqlalchemy import select
    
    try:
        # Check if this is a linking flow
        if not request.session.get('linking_github'):
            # Not a linking flow, use normal callback
            return await _handle_oauth_callback(request, db, 'github')
        
        session_email = request.session.get('linking_user_email')
        if not session_email:
            raise AuthError(error="session_expired", description="Session expired, please try again", status_code=400)
        
        # Clear linking flags
        request.session.pop('linking_github', None)
        request.session.pop('linking_user_email', None)
        
        # Get GitHub user info
        oauth = get_oauth_config()
        token = await oauth.oauth.github.authorize_access_token(request)
        user_info = await oauth.fetch_user_info('github', token)
        
        if not user_info:
            raise AuthError(error="profile_fetch_failed", description="Failed to get GitHub profile", status_code=500)
        
        # Find the existing user by email (from session)
        result = await db.execute(
            select(User).where(User.email == session_email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise AuthError(error="user_not_found", description="User not found", status_code=404)
        
        # Check if GitHub account is already linked to another user
        if user_info.get('id'):
            existing = await db.execute(
                select(User).where(User.github_id == str(user_info['id']))
            )
            existing_user = existing.scalar_one_or_none()
            if existing_user and existing_user.id != user.id:
                raise AuthError(
                    error="github_already_linked",
                    description="This GitHub account is already linked to another user",
                    status_code=400
                )
        
        # Link GitHub to existing user
        user.github_id = str(user_info['id'])
        user.github_username = user_info.get('login')
        user.set_github_token(token['access_token'])
        # Token expiry is often None for GitHub (never expires), but good to handle if present
        # user.github_token_expires = ... 
        await db.commit()
        
        # Update session to show GitHub is linked
        request.session['user']['github_connected'] = True
        
        logger.info(f"✓ GitHub linked to user: {user.email}")
        
        # Redirect back to settings
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}/settings?linked=github")
        
    except AuthError as e:
        logger.error(f"GitHub linking error: {e.description}")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}/settings?link_error={e.error}")
    except Exception as e:
        logger.error(f"GitHub linking error: {e}", exc_info=True)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}/settings?link_error=server_error")


# --- User Routes ---

@router.get("/user")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_session)):
    """
    Get currently authenticated user with subscription info.
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
                "github_connected": bool(user.github_id),
                "google_connected": bool(user.google_id),
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
        # Return partial data with defaults to prevent frontend crash
        from app.models.user import TIER_LIMITS
        return JSONResponse(content={
            "user": session_user,
            "limits": TIER_LIMITS['free'],
            "usage": {
                "prompts_used_today": 0,
                "tokens_used_month": 0
            },
            "authenticated": True
        })


@router.post("/logout")
async def logout(request: Request):
    """Clear user session."""
    request.session.clear()
    logger.info("User logged out")
    
    return JSONResponse(content={
        "success": True,
        "message": "Logged out successfully"
    })
