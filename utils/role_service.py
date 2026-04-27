"""Service for role-based access control."""

from __future__ import annotations

import json
import time
from typing import Optional

from database.db import get_user_roles, check_mentor_exists


_CACHE_TTL_SECONDS = 120
_role_cache: dict[int, dict] = {}
_cache_expires_at: dict[int, float] = {}


def invalidate_role_cache(user_id: Optional[int] = None) -> None:
    """Invalidate role cache for a specific user or all users."""
    global _role_cache, _cache_expires_at
    if user_id:
        _role_cache.pop(user_id, None)
        _cache_expires_at.pop(user_id, None)
    else:
        _role_cache = {}
        _cache_expires_at = {}


async def get_user_permissions(user_id: int) -> dict:
    """Get user permissions with caching."""
    global _role_cache, _cache_expires_at
    now = time.monotonic()
    
    if user_id in _cache_expires_at and now < _cache_expires_at[user_id]:
        return _role_cache[user_id]
    
    roles = await get_user_roles(user_id)
    permissions = {
        "is_admin": False,
        "is_mentor": False,
        "can_manage_users": False,
        "can_manage_content": False,
        "can_view_analytics": False,
        "can_manage_settings": False,
        "roles": []
    }
    
    for role in roles:
        permissions["roles"].append(role["name"])
        if role["name"] == "admin":
            permissions["is_admin"] = True
            permissions["is_mentor"] = True
            permissions["can_manage_users"] = True
            permissions["can_manage_content"] = True
            permissions["can_view_analytics"] = True
            permissions["can_manage_settings"] = True
        elif role["name"] == "mentor":
            permissions["is_mentor"] = True
        
        # Parse custom permissions from role
        if role.get("permissions"):
            try:
                custom_perms = json.loads(role["permissions"])
                permissions.update(custom_perms)
            except (json.JSONDecodeError, TypeError):
                pass
    
    _role_cache[user_id] = permissions
    _cache_expires_at[user_id] = now + _CACHE_TTL_SECONDS
    
    return permissions


async def is_admin(user_id: int) -> bool:
    """Check if user has admin role."""
    perms = await get_user_permissions(user_id)
    return perms["is_admin"]


async def is_mentor(user_id: int) -> bool:
    """Check if user has mentor role."""
    perms = await get_user_permissions(user_id)
    return perms["is_mentor"]


async def has_permission(user_id: int, permission: str) -> bool:
    """Check if user has a specific permission."""
    perms = await get_user_permissions(user_id)
    return perms.get(permission, False)
