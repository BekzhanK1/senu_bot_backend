"""Security utilities for API authentication and authorization."""

import os
import time
from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, Header, Request
from fastapi.responses import JSONResponse

from utils.role_service import is_admin, is_mentor


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class RateLimitExceeded(SecurityError):
    """Raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
    
    def check_rate_limit(self, key: str) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        if key in self._requests:
            self._requests[key] = [
                req_time for req_time in self._requests[key]
                if req_time > window_start
            ]
        else:
            self._requests[key] = []
        
        # Check limit
        if len(self._requests[key]) >= self.max_requests:
            return False
        
        # Add current request
        self._requests[key].append(now)
        return True
    
    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        self._requests.pop(key, None)


# Global rate limiter instances
_api_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
_broadcast_rate_limiter = RateLimiter(max_requests=5, window_seconds=3600)


async def verify_internal_token(x_internal_token: Optional[str] = Header(default=None)) -> None:
    """
    Verify internal API token.
    
    SECURITY: This function MUST be called on all API endpoints.
    If INTERNAL_API_TOKEN is not set, the API is INSECURE.
    """
    internal_token = os.getenv("INTERNAL_API_TOKEN")
    
    if not internal_token:
        # CRITICAL: Token not configured - log warning but allow in dev mode
        if os.getenv("ENV", "production") == "production":
            raise HTTPException(
                status_code=500,
                detail="Internal API token not configured. Set INTERNAL_API_TOKEN in .env"
            )
        # In dev mode, allow without token but log warning
        return
    
    if not x_internal_token or x_internal_token != internal_token:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing token")


async def verify_admin_access(user_id: int) -> None:
    """
    Verify user has admin access.
    
    Checks both legacy ADMIN_ID and database roles.
    """
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    
    # Legacy ADMIN_ID check
    if admin_id and user_id == admin_id:
        return
    
    # Database role check
    if await is_admin(user_id):
        return
    
    raise HTTPException(status_code=403, detail="Admin access required")


async def verify_mentor_access(user_id: int) -> None:
    """
    Verify user has mentor access.
    
    Checks both legacy ADMIN_ID and database roles.
    """
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    
    # Legacy ADMIN_ID check (admins are also mentors)
    if admin_id and user_id == admin_id:
        return
    
    # Database role check
    if await is_mentor(user_id) or await is_admin(user_id):
        return
    
    raise HTTPException(status_code=403, detail="Mentor access required")


def rate_limit(limiter: RateLimiter, key_func: Optional[Callable] = None):
    """
    Decorator for rate limiting endpoints.
    
    Args:
        limiter: RateLimiter instance to use
        key_func: Optional function to extract rate limit key from request
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user_id
            request = None
            user_id = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # Try to get user_id from kwargs
            user_id = kwargs.get('tg_user_id') or kwargs.get('user_id')
            
            # Generate rate limit key
            if key_func:
                key = key_func(request, user_id)
            elif user_id:
                key = f"user:{user_id}"
            elif request:
                key = f"ip:{request.client.host}"
            else:
                key = "global"
            
            # Check rate limit
            if not limiter.check_rate_limit(key):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later."
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_api_rate_limiter() -> RateLimiter:
    """Get global API rate limiter."""
    return _api_rate_limiter


def get_broadcast_rate_limiter() -> RateLimiter:
    """Get broadcast rate limiter."""
    return _broadcast_rate_limiter
