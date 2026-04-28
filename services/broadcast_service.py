"""Service for broadcasting messages and events."""

import logging
from html import escape

from database.db import create_mentor_event, get_all_users_ids
from services.notification_service import NotificationService
from utils.mentor_event_message import format_event_notification_html

logger = logging.getLogger(__name__)


class BroadcastService:
    """Service for broadcasting messages to users."""
    
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service
    
    async def broadcast_text(self, text: str) -> tuple[int, int]:
        """
        Broadcast plain text message to all users.
        
        Returns:
            Tuple of (delivered_count, total_count)
        """
        escaped_text = escape(text.strip())
        message = f"📢 <b>Объявление от ментора:</b>\n\n{escaped_text}"
        
        if len(message) > 4096:
            raise ValueError("Broadcast text too long for Telegram (max 4096 characters)")
        
        user_ids = await get_all_users_ids()
        logger.info(f"Broadcasting text message to {len(user_ids)} users")
        
        delivered, total = await self.notification_service.broadcast_message(
            user_ids,
            message,
            parse_mode="HTML",
        )
        
        logger.info(f"Broadcast completed: {delivered}/{total} delivered")
        return delivered, total
    
    async def create_and_broadcast_event(
        self,
        title: str,
        place: str,
        description: str,
    ) -> tuple[int, int, int]:
        """
        Create an event and broadcast it to all users.
        
        Returns:
            Tuple of (event_id, delivered_count, total_count)
        """
        # Validate and truncate fields
        title = title.strip()[:256]
        place = place.strip()[:256]
        description = description.strip()[:3500]
        
        # Format announcement
        announcement = format_event_notification_html(
            title=title,
            place=place,
            description=description,
        )
        
        if len(announcement) > 4000:
            raise ValueError("Event announcement too long for Telegram")
        
        # Create event in database
        event_id = await create_mentor_event(
            title=title,
            place=place,
            description=description,
        )
        logger.info(f"Event created: id={event_id} title={title}")
        
        # Broadcast to all users
        user_ids = await get_all_users_ids()
        logger.info(f"Broadcasting event {event_id} to {len(user_ids)} users")
        
        delivered, total = await self.notification_service.broadcast_message(
            user_ids,
            announcement,
            parse_mode="HTML",
        )
        
        logger.info(f"Event broadcast completed: {delivered}/{total} delivered")
        return event_id, delivered, total
