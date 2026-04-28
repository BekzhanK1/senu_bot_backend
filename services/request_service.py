"""Service for managing user requests."""

import logging
from typing import Optional

from database.db import (
    create_request,
    get_request_by_id,
    get_requests_for_admin,
    get_user_requests,
    resolve_request,
)
from services.notification_service import NotificationService
from utils.student_notifications import notify_request_resolved

logger = logging.getLogger(__name__)


class RequestService:
    """Service for managing user requests."""
    
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service
    
    async def create_user_request(
        self,
        user_id: int,
        request_type: str,
        content: str,
    ) -> int:
        """
        Create a new user request.
        
        Returns:
            Request ID
        """
        request_id = await create_request(user_id, request_type, content)
        logger.info(f"Request created: id={request_id} type={request_type} user_id={user_id}")
        return request_id
    
    async def resolve_user_request(
        self,
        request_id: int,
        notify_user: bool = True,
    ) -> bool:
        """
        Resolve a user request.
        
        Args:
            request_id: Request ID to resolve
            notify_user: Whether to send notification to user
        
        Returns:
            True if request was resolved successfully
        """
        req = await get_request_by_id(request_id)
        if not req:
            logger.warning(f"Request not found: id={request_id}")
            return False
        
        if req.status == "resolved":
            logger.info(f"Request already resolved: id={request_id}")
            return True
        
        await resolve_request(request_id)
        logger.info(f"Request resolved: id={request_id}")
        
        if notify_user:
            await notify_request_resolved(
                self.notification_service.bot,
                request_id=request_id,
                user_telegram_id=req.user_id,
                request_type=req.request_type,
            )
        
        return True
    
    async def reply_to_request(
        self,
        request_id: int,
        reply_text: str,
    ) -> bool:
        """
        Send a reply to user about their request.
        
        Returns:
            True if reply was sent successfully
        """
        req = await get_request_by_id(request_id)
        if not req:
            logger.warning(f"Request not found: id={request_id}")
            return False
        
        from html import escape
        body = escape(reply_text.strip())
        message = (
            f"<b>💬 Сообщение от ментора:</b>\n\n{body}\n\n"
            "<i>Когда вопрос будет полностью закрыт, ментор отметит заявку решённой — "
            "я пришлю отдельное уведомление.</i>"
        )
        
        success = await self.notification_service.send_message(
            req.user_id,
            message,
            parse_mode="HTML",
        )
        
        if success:
            logger.info(f"Reply sent for request: id={request_id}")
        else:
            logger.warning(f"Failed to send reply for request: id={request_id}")
        
        return success
    
    async def get_admin_requests(
        self,
        request_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ):
        """Get requests for admin dashboard."""
        return await get_requests_for_admin(
            request_type=request_type,
            status=status,
            limit=limit,
        )
    
    async def get_user_request_history(
        self,
        user_id: int,
        limit: int = 100,
    ):
        """Get user's request history."""
        return await get_user_requests(user_id, limit=limit)
