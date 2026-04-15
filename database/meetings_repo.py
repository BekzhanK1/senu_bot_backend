"""Meeting slots, schedule settings, bookings."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from database.db import async_session
from database.models import MeetingBooking, MentorScheduleSettings, Request, User

SCHEDULE_ROW_ID = 1

DEFAULT_WEEKLY: dict[str, dict[str, Any]] = {
    str(i): {"enabled": i < 5, "start": "10:00", "end": "18:00"} for i in range(7)
}


def _parse_hhmm(s: str) -> time:
    h, m = s.strip().split(":", 1)
    return time(int(h), int(m))


def _utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


async def ensure_schedule_row() -> None:
    async with async_session() as session:
        row = await session.get(MentorScheduleSettings, SCHEDULE_ROW_ID)
        if row is None:
            session.add(
                MentorScheduleSettings(
                    id=SCHEDULE_ROW_ID,
                    weekly_hours=dict(DEFAULT_WEEKLY),
                    slot_minutes=30,
                    timezone="Asia/Almaty",
                )
            )
            await session.commit()


async def get_schedule_settings() -> MentorScheduleSettings:
    await ensure_schedule_row()
    async with async_session() as session:
        row = await session.get(MentorScheduleSettings, SCHEDULE_ROW_ID)
        if row is None:
            raise RuntimeError("schedule row missing")
        return row


async def update_schedule_settings(
    *,
    weekly_hours: dict[str, Any],
    slot_minutes: int,
    tz_name: str,
) -> None:
    await ensure_schedule_row()
    if slot_minutes not in (15, 20, 30, 45, 60):
        raise ValueError("slot_minutes must be 15, 20, 30, 45 or 60")
    try:
        ZoneInfo(tz_name)
    except Exception as e:
        raise ValueError(f"invalid timezone: {tz_name}") from e
    for key, cfg in weekly_hours.items():
        if key not in {str(i) for i in range(7)}:
            raise ValueError(f"invalid day key: {key}")
        if not isinstance(cfg, dict):
            raise ValueError("day config must be object")
        _parse_hhmm(str(cfg["start"]))
        _parse_hhmm(str(cfg["end"]))
    async with async_session() as session:
        row = await session.get(MentorScheduleSettings, SCHEDULE_ROW_ID)
        if row is None:
            raise RuntimeError("schedule row missing")
        row.weekly_hours = weekly_hours
        row.slot_minutes = slot_minutes
        row.timezone = tz_name
        await session.commit()


def _intervals_overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> bool:
    return a0 < b1 and b0 < a1


async def _bookings_for_local_day(local_date: date, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
    """Return list of (start_utc_naive, end_utc_naive) active bookings intersecting this local calendar day."""
    day_local_start = datetime.combine(local_date, time.min, tzinfo=tz)
    day_local_end = day_local_start + timedelta(days=1)
    range_start = _utc_naive(day_local_start.astimezone(timezone.utc))
    range_end = _utc_naive(day_local_end.astimezone(timezone.utc))
    async with async_session() as session:
        q = select(MeetingBooking.start_at, MeetingBooking.end_at).where(
            MeetingBooking.status.in_(("pending_confirm", "confirmed")),
            MeetingBooking.start_at < range_end,
            MeetingBooking.end_at > range_start,
        )
        r = await session.execute(q)
        return [(row[0], row[1]) for row in r.all()]


async def get_available_slots(local_date: date) -> list[dict[str, Any]]:
    settings = await get_schedule_settings()
    tz = ZoneInfo(settings.timezone)
    weekly = settings.weekly_hours or DEFAULT_WEEKLY
    day_key = str(local_date.weekday())  # Mon=0
    day_cfg = weekly.get(day_key) or {"enabled": False, "start": "10:00", "end": "18:00"}
    if not day_cfg.get("enabled", False):
        return []

    start_t = _parse_hhmm(str(day_cfg["start"]))
    end_t = _parse_hhmm(str(day_cfg["end"]))
    slot_m = settings.slot_minutes

    day_start = datetime.combine(local_date, start_t, tzinfo=tz)
    day_end = datetime.combine(local_date, end_t, tzinfo=tz)
    if day_end <= day_start:
        return []

    busy = await _bookings_for_local_day(local_date, tz)

    slots: list[dict[str, Any]] = []
    cur = day_start
    while cur + timedelta(minutes=slot_m) <= day_end:
        slot_end = cur + timedelta(minutes=slot_m)
        s_utc = _utc_naive(cur.astimezone(timezone.utc))
        e_utc = _utc_naive(slot_end.astimezone(timezone.utc))
        taken = any(_intervals_overlap(s_utc, e_utc, b0, b1) for b0, b1 in busy)
        if not taken:
            label = cur.strftime("%H:%M")
            slots.append(
                {
                    "start_at": cur.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "end_at": slot_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "label": label,
                }
            )
        cur = slot_end
    return slots


async def create_meeting_booking(
    *,
    student_id: int,
    start_at: datetime,
    end_at: datetime,
    topic: Optional[str],
) -> tuple[int, int]:
    """Returns (booking_id, request_id). start_at/end_at must be timezone-aware UTC or naive UTC."""
    s = _utc_naive(start_at if start_at.tzinfo else start_at.replace(tzinfo=timezone.utc))
    e = _utc_naive(end_at if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc))
    if e <= s:
        raise ValueError("invalid slot range")

    settings = await get_schedule_settings()
    tz = ZoneInfo(settings.timezone)
    s_utc = s.replace(tzinfo=timezone.utc) if s.tzinfo is None else s.astimezone(timezone.utc)
    local_start = s_utc.astimezone(tz)
    local_date = local_start.date()
    if (e - s) != timedelta(minutes=settings.slot_minutes):
        raise ValueError("invalid slot duration")
    day_key = str(local_date.weekday())
    weekly = settings.weekly_hours or DEFAULT_WEEKLY
    day_cfg = weekly.get(day_key) or {}
    if not day_cfg.get("enabled", False):
        raise ValueError("mentor is not available on this day")

    available = await get_available_slots(local_date)
    iso_s = s_utc.isoformat().replace("+00:00", "Z")
    match = next((sl for sl in available if sl["start_at"] == iso_s), None)
    if match is None:
        raise ValueError("slot is outside available hours or already taken")

    busy = await _bookings_for_local_day(local_date, tz)
    if any(_intervals_overlap(s, e, b0, b1) for b0, b1 in busy):
        raise ValueError("slot no longer available")

    when_human = local_start.strftime("%d.%m.%Y %H:%M")

    async with async_session() as session:
        booking = MeetingBooking(
            student_user_id=student_id,
            start_at=s,
            end_at=e,
            status="pending_confirm",
            topic=topic,
        )
        session.add(booking)
        await session.flush()
        bid = booking.id
        content = f"📅 Встреча (слот)\nID брони: {bid}\n{when_human}\nТема: {topic or '—'}"
        req = Request(user_id=student_id, request_type="meeting", content=content, status="pending")
        session.add(req)
        await session.flush()
        rid = req.id
        booking.request_id = rid
        await session.commit()
        return bid, rid


async def list_meeting_bookings(
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[tuple[MeetingBooking, str, Optional[str]]]:
    async with async_session() as session:
        q = (
            select(MeetingBooking, User.full_name, User.username)
            .join(User, MeetingBooking.student_user_id == User.telegram_id)
            .order_by(MeetingBooking.start_at.asc())
        )
        if date_from:
            q = q.where(MeetingBooking.start_at >= datetime.combine(date_from, time.min))
        if date_to:
            q = q.where(MeetingBooking.start_at < datetime.combine(date_to + timedelta(days=1), time.min))
        q = q.limit(300)
        r = await session.execute(q)
        return list(r.all())


async def get_booking(booking_id: int) -> MeetingBooking | None:
    async with async_session() as session:
        return await session.get(MeetingBooking, booking_id)


async def confirm_meeting_booking(booking_id: int) -> MeetingBooking | None:
    async with async_session() as session:
        b = await session.get(MeetingBooking, booking_id)
        if b is None or b.status != "pending_confirm":
            return None
        b.status = "confirmed"
        await session.commit()
        return b


async def complete_meeting_booking(booking_id: int) -> MeetingBooking | None:
    async with async_session() as session:
        b = await session.get(MeetingBooking, booking_id)
        if b is None or b.status != "confirmed":
            return None
        b.status = "completed"
        if b.request_id:
            await session.execute(update(Request).where(Request.id == b.request_id).values(status="resolved"))
        await session.commit()
        return b


def format_booking_local_human(booking: MeetingBooking, tz_name: str) -> str:
    s = booking.start_at
    d = s.replace(tzinfo=timezone.utc) if s.tzinfo is None else s.astimezone(timezone.utc)
    return d.astimezone(ZoneInfo(tz_name)).strftime("%d.%m.%Y %H:%M")
