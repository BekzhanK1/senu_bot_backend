"""Service for audit logging."""

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import async_session
from database.models_v2 import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Service for logging admin actions."""
    
    @staticmethod
    async def log_action(
        actor_telegram_id: Optional[int],
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log an admin action to the audit log.
        
        Args:
            actor_telegram_id: Telegram ID of user performing action
            action: Action name (e.g., "create_request", "resolve_request")
            entity_type: Type of entity (e.g., "request", "user", "meeting")
            entity_id: ID of the entity being acted upon
            details: Additional details as JSON
        """
        try:
            async with async_session() as session:
                log_entry = AuditLog(
                    actor_telegram_id=actor_telegram_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id else None,
                    details_json=details or {},
                )
                session.add(log_entry)
                await session.commit()
                
                logger.info(
                    f"Audit log: actor={actor_telegram_id} action={action} "
                    f"entity={entity_type}:{entity_id}"
                )
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    @staticmethod
    async def get_recent_logs(
        limit: int = 100,
        actor_id: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> list[AuditLog]:
        """
        Get recent audit logs.
        
        Args:
            limit: Maximum number of logs to return
            actor_id: Filter by actor telegram ID
            entity_type: Filter by entity type
        
        Returns:
            List of audit log entries
        """
        async with async_session() as session:
            query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            
            if actor_id:
                query = query.where(AuditLog.actor_telegram_id == actor_id)
            
            if entity_type:
                query = query.where(AuditLog.entity_type == entity_type)
            
            result = await session.execute(query)
            return list(result.scalars().all())
