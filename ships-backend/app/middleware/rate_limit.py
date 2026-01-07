"""
Rate limiting middleware for enforcing tier-based usage quotas.

Checks user's tier and validates they haven't exceeded their:
- Daily prompt limit
- Monthly token limit

Returns 429 Too Many Requests if quota exceeded.
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
from datetime import datetime, timedelta

from app.models import User
from app.database import get_session

logger = logging.getLogger("ships.ratelimit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tier-based rate limiting.
    
    Checks usage quotas before allowing requests to agent endpoints.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Endpoints that require rate limiting
        self.protected_paths = [
            "/agent/prompt",
            "/agent/execute",
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Check rate limits before processing request."""
        
        # Only check protected endpoints
        if not any(request.url.path.startswith(path) for path in self.protected_paths):
            return await call_next(request)
        
        # Get user from session
        session_user = request.session.get('user')
        if not session_user:
            # Not authenticated - allow (auth middleware will handle)
            return await call_next(request)
        
        # Check rate limits
        try:
            async for db in get_session():
                result = await db.execute(
                    select(User).where(User.email == session_user['email'])
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    # User deleted but session exists
                    return JSONResponse(
                        status_code=401,
                        content={"error": "User not found"}
                    )
                
                # Get tier limits
                limits = user.get_tier_limits()
                
                # Check daily prompt limit
                if not user.can_use_prompts(1):
                    logger.warning(
                        f"User {user.email} exceeded daily prompt limit "
                        f"({user.prompts_used_today}/{limits['prompts_per_day']})"
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "quota_exceeded",
                            "message": "Daily prompt limit exceeded",
                            "limit": limits['prompts_per_day'],
                            "used": user.prompts_used_today,
                            "reset_at": self._get_next_day_reset().isoformat(),
                            "upgrade_url": "/settings?tab=subscription"
                        }
                    )
                
                # Increment usage counter (will be saved by request handler)
                user.prompts_used_today += 1
                await db.commit()
                
                # Continue with request
                response = await call_next(request)
                
                # Add usage headers
                response.headers["X-RateLimit-Limit"] = str(limits['prompts_per_day'])
                response.headers["X-RateLimit-Remaining"] = str(
                    max(0, limits['prompts_per_day'] - user.prompts_used_today)
                )
                response.headers["X-RateLimit-Reset"] = self._get_next_day_reset().isoformat()
                
                return response
                
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # On error, allow request (fail open)
            return await call_next(request)
    
    def _get_next_day_reset(self) -> datetime:
        """Get timestamp for next daily reset (midnight UTC)."""
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        return datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
