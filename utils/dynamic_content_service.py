"""Service for managing dynamic content and caching."""

from __future__ import annotations

import time
from typing import Optional

from database.db import get_dynamic_content_by_key, get_all_menu_buttons


_CACHE_TTL_SECONDS = 60
_content_cache: dict[str, str] = {}
_content_cache_expires_at = 0.0
_menu_cache: list[dict] = []
_menu_cache_expires_at = 0.0


def invalidate_content_cache() -> None:
    """Invalidate all content caches."""
    global _content_cache, _content_cache_expires_at, _menu_cache, _menu_cache_expires_at
    _content_cache = {}
    _content_cache_expires_at = 0.0
    _menu_cache = []
    _menu_cache_expires_at = 0.0


async def get_dynamic_content(key: str, default: str = "") -> str:
    """Get dynamic content by key with caching."""
    global _content_cache, _content_cache_expires_at
    now = time.monotonic()
    
    if now >= _content_cache_expires_at:
        _content_cache = {}
        _content_cache_expires_at = now + _CACHE_TTL_SECONDS
    
    if key not in _content_cache:
        content = await get_dynamic_content_by_key(key)
        _content_cache[key] = content if content else default
    
    return _content_cache[key]


async def get_menu_buttons_cached(role: Optional[str] = None) -> list[dict]:
    """Get menu buttons with caching, filtered by role if provided."""
    global _menu_cache, _menu_cache_expires_at
    now = time.monotonic()
    
    if now >= _menu_cache_expires_at or not _menu_cache:
        _menu_cache = await get_all_menu_buttons()
        _menu_cache_expires_at = now + _CACHE_TTL_SECONDS
    
    if role:
        return [btn for btn in _menu_cache if not btn.get("required_role") or btn.get("required_role") == role]
    
    return [btn for btn in _menu_cache if not btn.get("required_role")]
