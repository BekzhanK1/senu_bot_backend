"""Dependency injection container for services."""

import os
from typing import Optional

from aiogram import Bot

from services.audit_service import AuditService
from services.broadcast_service import BroadcastService
from services.meeting_service import MeetingService
from services.notification_service import NotificationService
from services.request_service import RequestService


class ServiceContainer:
    """Container for all application services."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.admin_id = int(os.getenv("ADMIN_ID", "0"))
        
        # Initialize services
        self._notification_service: Optional[NotificationService] = None
        self._request_service: Optional[RequestService] = None
        self._meeting_service: Optional[MeetingService] = None
        self._broadcast_service: Optional[BroadcastService] = None
        self._audit_service: Optional[AuditService] = None
    
    @property
    def notification_service(self) -> NotificationService:
        """Get notification service instance."""
        if self._notification_service is None:
            self._notification_service = NotificationService(self.bot)
        return self._notification_service
    
    @property
    def request_service(self) -> RequestService:
        """Get request service instance."""
        if self._request_service is None:
            self._request_service = RequestService(self.notification_service)
        return self._request_service
    
    @property
    def meeting_service(self) -> MeetingService:
        """Get meeting service instance."""
        if self._meeting_service is None:
            self._meeting_service = MeetingService(
                self.notification_service,
                self.admin_id,
            )
        return self._meeting_service
    
    @property
    def broadcast_service(self) -> BroadcastService:
        """Get broadcast service instance."""
        if self._broadcast_service is None:
            self._broadcast_service = BroadcastService(self.notification_service)
        return self._broadcast_service
    
    @property
    def audit_service(self) -> AuditService:
        """Get audit service instance."""
        if self._audit_service is None:
            self._audit_service = AuditService()
        return self._audit_service


# Global service container instance
_container: Optional[ServiceContainer] = None


def init_services(bot: Bot) -> ServiceContainer:
    """Initialize global service container."""
    global _container
    _container = ServiceContainer(bot)
    return _container


def get_services() -> ServiceContainer:
    """Get global service container."""
    if _container is None:
        raise RuntimeError("Services not initialized. Call init_services() first.")
    return _container
