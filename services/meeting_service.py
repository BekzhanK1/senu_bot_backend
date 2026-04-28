"""Service for managing meeting bookings."""

import logging
from datetime import date, datetime
from typing import Optional

from database.meetings_repo import (
    complete_meeting_booking,
    confirm_meeting_booking,
    create_meeting_booking,
    format_booking_local_human,
    get_available_slots,
    get_booking,
    get_schedule_settings,
    list_meeting_bookings,
)
from services.notification_service import NotificationService
from utils.meeting_messages import (
    format_admin_new_booking,
    format_meeting_completed_student,
    format_meeting_confirmed_student,
    format_meeting_pending_student,
)

logger = logging.getLogger(__name__)


class MeetingService:
    """Service for managing meeting bookings."""
    
    def __init__(self, notification_service: NotificationService, admin_id: int):
        self.notification_service = notification_service
        self.admin_id = admin_id
    
    async def get_available_slots_for_date(self, target_date: date):
        """Get available meeting slots for a specific date."""
        return await get_available_slots(target_date)
    
    async def create_booking(
        self,
        student_id: int,
        student_name: str,
        start_at: datetime,
        end_at: datetime,
        topic: Optional[str] = None,
    ) -> tuple[int, int]:
        """
        Create a new meeting booking.
        
        Returns:
            Tuple of (booking_id, request_id)
        """
        try:
            booking_id, request_id = await create_meeting_booking(
                student_id=student_id,
                start_at=start_at,
                end_at=end_at,
                topic=topic,
            )
            logger.info(
                f"Meeting booking created: booking_id={booking_id} "
                f"request_id={request_id} student_id={student_id}"
            )
            
            # Get schedule settings for timezone
            sched = await get_schedule_settings()
            booking = await get_booking(booking_id)
            
            if booking:
                when_human = format_booking_local_human(booking, sched.timezone)
                
                # Notify student
                await self.notification_service.send_message(
                    student_id,
                    format_meeting_pending_student(when_human=when_human, topic=topic),
                    parse_mode="HTML",
                )
                
                # Notify admin
                await self.notification_service.send_message(
                    self.admin_id,
                    format_admin_new_booking(
                        booking_id=booking_id,
                        student_name=student_name,
                        when_human=when_human,
                        topic=topic,
                    ),
                    parse_mode="HTML",
                )
            
            return booking_id, request_id
            
        except ValueError as e:
            logger.warning(f"Failed to create booking: {e}")
            raise
    
    async def confirm_booking(self, booking_id: int) -> bool:
        """
        Confirm a meeting booking.
        
        Returns:
            True if booking was confirmed successfully
        """
        booking = await confirm_meeting_booking(booking_id)
        if not booking:
            logger.warning(f"Booking not found or not pending: id={booking_id}")
            return False
        
        logger.info(f"Meeting booking confirmed: id={booking_id}")
        
        # Notify student
        sched = await get_schedule_settings()
        when = format_booking_local_human(booking, sched.timezone)
        
        await self.notification_service.send_message(
            booking.student_user_id,
            format_meeting_confirmed_student(when_human=when),
            parse_mode="HTML",
        )
        
        return True
    
    async def complete_booking(self, booking_id: int) -> bool:
        """
        Mark a meeting booking as completed.
        
        Returns:
            True if booking was completed successfully
        """
        booking = await complete_meeting_booking(booking_id)
        if not booking:
            logger.warning(f"Booking not found or not confirmed: id={booking_id}")
            return False
        
        logger.info(f"Meeting booking completed: id={booking_id}")
        
        # Notify student
        sched = await get_schedule_settings()
        when = format_booking_local_human(booking, sched.timezone)
        
        await self.notification_service.send_message(
            booking.student_user_id,
            format_meeting_completed_student(when_human=when),
            parse_mode="HTML",
        )
        
        return True
    
    async def list_bookings(self, date_from: date, date_to: date):
        """List meeting bookings in date range."""
        return await list_meeting_bookings(date_from=date_from, date_to=date_to)
