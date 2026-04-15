"""Append-only analytics events (v2)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from database.db import async_session
from database.models_v2 import AnalyticsEvent

logger = logging.getLogger(__name__)


def _hash_actor(telegram_id: int) -> str:
    return hashlib.sha256(str(telegram_id).encode()).hexdigest()


async def emit_event(
    *,
    event_name: str,
    user_telegram_id: int | None = None,
    case_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist an analytics event. Failures are logged and do not break user flows."""
    actor_hash = _hash_actor(user_telegram_id) if user_telegram_id is not None else None
    payload = metadata or {}
    try:
        async with async_session() as session:
            session.add(
                AnalyticsEvent(
                    event_name=event_name,
                    actor_id_hash=actor_hash,
                    case_id=case_id,
                    metadata_json=payload,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("emit_event failed: event_name=%s", event_name)
