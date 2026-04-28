"""Router for meeting-related endpoints."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from database.meetings_repo import (
    format_booking_local_human,
    get_schedule_settings,
    update_schedule_settings,
)
from services.container import get_services
from services.audit_service import AuditService
from utils.security import verify_internal_token, verify_admin_access, rate_limit, get_api_rate_limiter


router = APIRouter(prefix="/api", tags=["meetings"])


# Request/Response models
class TgUserPayload(BaseModel):
    id: int
    username: Optional[str] = None
    full_name: str


class MeetingSlotBookRequest(BaseModel):
    tg_user: TgUserPayload
    start_at: str
    end_at: str
    topic: Optional[str] = Field(default=None, max_length=2000)


class ScheduleUpdateRequest(BaseModel):
    tg_user_id: int
    weekly_hours: dict[str, dict[str, Any]]
    slot_minutes: int = 30
    timezone: str = Field(default="Asia/Almaty", max_length=64)


class AdminMeetingActionRequest(BaseModel):
    tg_user_id: int


def _parse_iso_datetime(s: str) -> datetime:
    """Parse ISO datetime string."""
    raw = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/meetings/availability")
@rate_limit(get_api_rate_limiter())
async def meetings_availability(
    on_date: str = Query(..., alias="date"),
    x_internal_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Get available meeting slots for a date."""
    await verify_internal_token(x_internal_token)
    
    try:
        day = date.fromisoformat(on_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date, use YYYY-MM-DD")
    
    services = get_services()
    sched = await get_schedule_settings()
    slots = await services.meeting_service.get_available_slots_for_date(day)
    
    return {
        "slots": slots,
        "timezone": sched.timezone,
        "slot_minutes": sched.slot_minutes,
    }


@router.post("/meetings/book")
@rate_limit(get_api_rate_limiter())
async def meetings_book_slot(
    payload: MeetingSlotBookRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Book a meeting slot."""
    await verify_internal_token(x_internal_token)
    
    user = payload.tg_user
    
    # Check if user is blocked
    from database.db import is_user_blocked, add_user
    if await is_user_blocked(user.id):
        raise HTTPException(status_code=403, detail="User is blocked")
    
    await add_user(user.id, user.username, user.full_name)
    
    try:
        start_dt = _parse_iso_datetime(payload.start_at)
        end_dt = _parse_iso_datetime(payload.end_at)
        
        services = get_services()
        booking_id, request_id = await services.meeting_service.create_booking(
            student_id=user.id,
            student_name=user.full_name,
            start_at=start_dt,
            end_at=end_dt,
            topic=payload.topic,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=user.id,
        action="book_meeting",
        entity_type="meeting",
        entity_id=str(booking_id),
        details={"topic": payload.topic},
    )
    
    return {"ok": True, "booking_id": booking_id, "request_id": request_id}


@router.get("/admin/schedule")
@rate_limit(get_api_rate_limiter())
async def admin_schedule_get(
    tg_user_id: int = Query(...),
    x_internal_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Get mentor schedule settings."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(tg_user_id)
    
    row = await get_schedule_settings()
    return {
        "weekly_hours": row.weekly_hours,
        "slot_minutes": row.slot_minutes,
        "timezone": row.timezone,
    }


@router.put("/admin/schedule")
@rate_limit(get_api_rate_limiter())
async def admin_schedule_put(
    payload: ScheduleUpdateRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Update mentor schedule settings."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    try:
        weekly = {str(k): dict(v) for k, v in payload.weekly_hours.items()}
        await update_schedule_settings(
            weekly_hours=weekly,
            slot_minutes=payload.slot_minutes,
            tz_name=payload.timezone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="update_schedule",
        entity_type="schedule",
        details={"slot_minutes": payload.slot_minutes, "timezone": payload.timezone},
    )
    
    return {"ok": True}


@router.get("/admin/meetings")
@rate_limit(get_api_rate_limiter())
async def admin_meetings_list(
    tg_user_id: int = Query(...),
    x_internal_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """List meeting bookings."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(tg_user_id)
    
    services = get_services()
    sched = await get_schedule_settings()
    tz = ZoneInfo(sched.timezone)
    today = datetime.now(tz).date()
    
    rows = await services.meeting_service.list_bookings(
        date_from=today - timedelta(days=1),
        date_to=today + timedelta(days=90),
    )
    
    items: list[dict[str, Any]] = []
    for booking, full_name, uname in rows:
        items.append({
            "id": booking.id,
            "student_user_id": booking.student_user_id,
            "student_full_name": full_name,
            "student_username": uname,
            "start_at": booking.start_at.isoformat(),
            "end_at": booking.end_at.isoformat(),
            "start_local_label": format_booking_local_human(booking, sched.timezone),
            "status": booking.status,
            "topic": booking.topic,
            "request_id": booking.request_id,
        })
    
    return {"items": items, "timezone": sched.timezone}


@router.post("/admin/meetings/{booking_id}/confirm")
@rate_limit(get_api_rate_limiter())
async def admin_meeting_confirm(
    booking_id: int,
    payload: AdminMeetingActionRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Confirm a meeting booking."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    services = get_services()
    success = await services.meeting_service.confirm_booking(booking_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Booking not found or not pending")
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="confirm_meeting",
        entity_type="meeting",
        entity_id=str(booking_id),
    )
    
    return {"ok": True}


@router.post("/admin/meetings/{booking_id}/complete")
@rate_limit(get_api_rate_limiter())
async def admin_meeting_complete(
    booking_id: int,
    payload: AdminMeetingActionRequest,
    x_internal_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Complete a meeting booking."""
    await verify_internal_token(x_internal_token)
    await verify_admin_access(payload.tg_user_id)
    
    services = get_services()
    success = await services.meeting_service.complete_booking(booking_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Booking not found or not confirmed")
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=payload.tg_user_id,
        action="complete_meeting",
        entity_type="meeting",
        entity_id=str(booking_id),
    )
    
    return {"ok": True}
