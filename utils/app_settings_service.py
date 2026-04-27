from __future__ import annotations

import time
from typing import TypedDict

from database.db import get_app_settings


class AppSettingsPayload(TypedDict):
    welcome_message: str
    mentor_about_text: str
    mentor_photo_url: str
    support_bot_username: str
    support_hotline: str
    miniapp_home_title: str
    miniapp_home_footer: str


_CACHE_TTL_SECONDS = 30
_cache: AppSettingsPayload | None = None
_cache_expires_at = 0.0


def invalidate_app_settings_cache() -> None:
    global _cache, _cache_expires_at
    _cache = None
    _cache_expires_at = 0.0


async def get_cached_app_settings() -> AppSettingsPayload:
    global _cache, _cache_expires_at
    now = time.monotonic()
    if _cache is not None and now < _cache_expires_at:
        return _cache
    settings, _, _ = await get_app_settings()
    _cache = settings  # type: ignore[assignment]
    _cache_expires_at = now + _CACHE_TTL_SECONDS
    return _cache
