import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from html import escape
from typing import Any, Literal, Optional

from aiogram import Bot
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from database.db import (
    add_user,
    block_user,
    create_mentor_event,
    create_request,
    get_all_users,
    get_all_users_ids,
    get_blocked_user_ids,
    get_request_by_id,
    get_requests_for_admin,
    get_user,
    get_user_requests,
    is_user_blocked,
    resolve_request,
    unblock_user,
)
from keyboards.inline import get_admin_resolve_kb
from database.meetings_repo import (
    complete_meeting_booking,
    confirm_meeting_booking,
    create_meeting_booking,
    format_booking_local_human,
    get_available_slots,
    get_booking,
    get_schedule_settings,
    list_meeting_bookings,
    update_schedule_settings,
)
from utils.meeting_messages import (
    format_admin_new_booking,
    format_meeting_completed_student,
    format_meeting_confirmed_student,
    format_meeting_pending_student,
)
from utils.mentor_event_message import format_event_notification_html
from utils.student_notifications import notify_request_resolved


class TgUserPayload(BaseModel):
    id: int
    username: Optional[str] = None
    full_name: str


class QuestionRequest(BaseModel):
    type: Literal["question"]
    text: str = Field(min_length=1, max_length=4096)
    is_anonymous: bool = False
    tg_user: TgUserPayload


class MeetingRequest(BaseModel):
    type: Literal["meeting"]
    day: str = Field(min_length=1, max_length=128)
    time: str = Field(min_length=1, max_length=128)
    tg_user: TgUserPayload


class GameRequest(BaseModel):
    type: Literal["game_108"]
    tg_user: TgUserPayload


class ApiResponse(BaseModel):
    ok: bool
    request_id: int


class AdminResolveRequest(BaseModel):
    tg_user_id: int


class AdminRequestItem(BaseModel):
    id: int
    user_id: int
    user_full_name: str
    user_username: Optional[str] = None
    request_type: str
    content: str
    status: str
    created_at: datetime


class AdminRequestsResponse(BaseModel):
    items: list[AdminRequestItem]

class AdminUserItem(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    full_name: str
    joined_at: datetime
    is_blocked: bool


class AdminUsersResponse(BaseModel):
    items: list[AdminUserItem]


class AdminUserActionRequest(BaseModel):
    tg_user_id: int
    reason: Optional[str] = None


class AdminReplyRequest(BaseModel):
    tg_user_id: int
    text: str = Field(min_length=1, max_length=3500)


class AdminEventCreateRequest(BaseModel):
    tg_user_id: int
    title: str = Field(min_length=2, max_length=256)
    place: str = Field(min_length=2, max_length=256)
    description: str = Field(min_length=5, max_length=3500)


class AdminEventCreateResponse(BaseModel):
    ok: bool
    event_id: int
    delivered: int
    total: int


class AdminBroadcastRequest(BaseModel):
    tg_user_id: int
    text: str = Field(min_length=1, max_length=3900)


class ScheduleUpdateRequest(BaseModel):
    tg_user_id: int
    weekly_hours: dict[str, dict[str, Any]]
    slot_minutes: int = 30
    timezone: str = Field(default="Asia/Almaty", max_length=64)


class MeetingSlotBookRequest(BaseModel):
    tg_user: TgUserPayload
    start_at: str
    end_at: str
    topic: Optional[str] = Field(default=None, max_length=2000)


class AdminMeetingActionRequest(BaseModel):
    tg_user_id: int


class ProfileRequest(BaseModel):
    tg_user_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None


class UserRequestItem(BaseModel):
    id: int
    request_type: str
    content: str
    status: str
    created_at: datetime


class UserProfileResponse(BaseModel):
    tg_user_id: int
    username: Optional[str] = None
    full_name: str
    is_blocked: bool
    requests: list[UserRequestItem]


def _parse_iso_datetime(s: str) -> datetime:
    raw = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def create_api_app(bot: Bot) -> FastAPI:
    app = FastAPI(title="SENU Bot API", version="1.0.0")
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    internal_token = os.getenv("INTERNAL_API_TOKEN")

    async def verify_token(x_internal_token: str | None) -> None:
        if internal_token and x_internal_token != internal_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

    def verify_admin_user(user_id: int) -> None:
        if user_id != admin_id:
            raise HTTPException(status_code=403, detail="Admin access required")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/meetings/availability")
    async def meetings_availability(
        on_date: str = Query(..., alias="date"),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        await verify_token(x_internal_token)
        try:
            day = date.fromisoformat(on_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date, use YYYY-MM-DD")
        sched = await get_schedule_settings()
        slots = await get_available_slots(day)
        return {"slots": slots, "timezone": sched.timezone, "slot_minutes": sched.slot_minutes}

    @app.post("/api/meetings/book")
    async def meetings_book_slot(
        payload: MeetingSlotBookRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        await verify_token(x_internal_token)
        user = payload.tg_user
        if await is_user_blocked(user.id):
            raise HTTPException(status_code=403, detail="User is blocked")
        await add_user(user.id, user.username, user.full_name)
        try:
            start_dt = _parse_iso_datetime(payload.start_at)
            end_dt = _parse_iso_datetime(payload.end_at)
            bid, rid = await create_meeting_booking(
                student_id=user.id,
                start_at=start_dt,
                end_at=end_dt,
                topic=payload.topic,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        sched = await get_schedule_settings()
        b = await get_booking(bid)
        if b is None:
            raise HTTPException(status_code=500, detail="Booking not found after create")
        when_human = format_booking_local_human(b, sched.timezone)
        topic = payload.topic
        try:
            await bot.send_message(
                user.id,
                format_meeting_pending_student(when_human=when_human, topic=topic),
                parse_mode="HTML",
            )
            await bot.send_message(
                admin_id,
                format_admin_new_booking(
                    booking_id=bid,
                    student_name=user.full_name,
                    when_human=when_human,
                    topic=topic,
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return {"ok": True, "booking_id": bid, "request_id": rid}

    @app.post("/api/requests/question", response_model=ApiResponse)
    async def create_question_request(
        payload: QuestionRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> ApiResponse:
        await verify_token(x_internal_token)
        user = payload.tg_user
        if await is_user_blocked(user.id):
            raise HTTPException(status_code=403, detail="User is blocked")
        await add_user(user.id, user.username, user.full_name)

        request_type = "anonymous_question" if payload.is_anonymous else "question"
        req_id = await create_request(user.id, request_type, payload.text.strip())
        sender = "🕵️ Анонимно" if payload.is_anonymous else f"👤 {user.full_name}"
        admin_msg = f"🔔 <b>Новый вопрос ({sender})</b>\nТекст: {payload.text.strip()}"
        await bot.send_message(
            admin_id,
            admin_msg,
            reply_markup=get_admin_resolve_kb(req_id),
            parse_mode="HTML",
        )
        return ApiResponse(ok=True, request_id=req_id)

    @app.post("/api/requests/meeting", response_model=ApiResponse)
    async def create_meeting_request(
        payload: MeetingRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> ApiResponse:
        await verify_token(x_internal_token)
        user = payload.tg_user
        if await is_user_blocked(user.id):
            raise HTTPException(status_code=403, detail="User is blocked")
        await add_user(user.id, user.username, user.full_name)

        content = f"📅 Встреча через Mini App\nДата: {payload.day}\nВремя: {payload.time}"
        req_id = await create_request(user.id, "meeting", content)
        username = f"@{user.username}" if user.username else user.full_name
        admin_msg = (
            "🔔 <b>Новая запись: Встреча</b>\n"
            f"От: {user.full_name} ({username})\n"
            f"<b>{payload.day} в {payload.time}</b>"
        )
        await bot.send_message(
            admin_id,
            admin_msg,
            reply_markup=get_admin_resolve_kb(req_id),
            parse_mode="HTML",
        )
        return ApiResponse(ok=True, request_id=req_id)

    @app.post("/api/requests/game_108", response_model=ApiResponse)
    async def create_game_request(
        payload: GameRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> ApiResponse:
        await verify_token(x_internal_token)
        user = payload.tg_user
        if await is_user_blocked(user.id):
            raise HTTPException(status_code=403, detail="User is blocked")
        await add_user(user.id, user.username, user.full_name)

        req_id = await create_request(user.id, "game_108", "Заявка через Mini App API")
        username = f"@{user.username}" if user.username else user.full_name
        admin_msg = f"🔔 <b>Новая заявка: Игра 108</b>\nОт: {user.full_name} ({username})"
        await bot.send_message(
            admin_id,
            admin_msg,
            reply_markup=get_admin_resolve_kb(req_id),
            parse_mode="HTML",
        )
        return ApiResponse(ok=True, request_id=req_id)

    @app.post("/api/profile/me", response_model=UserProfileResponse)
    async def get_my_profile(
        payload: ProfileRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> UserProfileResponse:
        await verify_token(x_internal_token)
        user = await get_user(payload.tg_user_id)
        if not user:
            if not payload.full_name:
                raise HTTPException(status_code=404, detail="User not found")
            await add_user(payload.tg_user_id, payload.username, payload.full_name)
            user = await get_user(payload.tg_user_id)
            if not user:
                raise HTTPException(status_code=500, detail="Failed to create user profile")
        requests = await get_user_requests(payload.tg_user_id, limit=100)
        return UserProfileResponse(
            tg_user_id=user.telegram_id,
            username=user.username,
            full_name=user.full_name,
            is_blocked=await is_user_blocked(user.telegram_id),
            requests=[
                UserRequestItem(
                    id=req.id,
                    request_type=req.request_type,
                    content=req.content,
                    status=req.status,
                    created_at=req.created_at,
                )
                for req in requests
            ],
        )

    @app.get("/api/admin/requests", response_model=AdminRequestsResponse)
    async def list_admin_requests(
        tg_user_id: int = Query(...),
        request_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        x_internal_token: str | None = Header(default=None),
    ) -> AdminRequestsResponse:
        await verify_token(x_internal_token)
        verify_admin_user(tg_user_id)

        rows = await get_requests_for_admin(request_type=request_type, status=status, limit=300)
        items = [
            AdminRequestItem(
                id=req.id,
                user_id=req.user_id,
                user_full_name=full_name,
                user_username=username,
                request_type=req.request_type,
                content=req.content,
                status=req.status,
                created_at=req.created_at,
            )
            for req, full_name, username in rows
        ]
        return AdminRequestsResponse(items=items)

    @app.post("/api/admin/requests/{request_id}/resolve")
    async def resolve_admin_request(
        request_id: int,
        payload: AdminResolveRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        req = await get_request_by_id(request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        if req.status != "resolved":
            await resolve_request(request_id)
            await notify_request_resolved(
                bot,
                request_id=request_id,
                user_telegram_id=req.user_id,
                request_type=req.request_type,
            )
        return {"ok": True}

    @app.post("/api/admin/requests/{request_id}/reply")
    async def reply_admin_request(
        request_id: int,
        payload: AdminReplyRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        req = await get_request_by_id(request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        body = escape(payload.text.strip())
        reply_text = (
            f"<b>💬 Сообщение от ментора:</b>\n\n{body}\n\n"
            "<i>Когда вопрос будет полностью закрыт, ментор отметит заявку решённой — "
            "я пришлю отдельное уведомление.</i>"
        )
        await bot.send_message(req.user_id, reply_text, parse_mode="HTML")
        return {"ok": True}

    @app.post("/api/admin/events", response_model=AdminEventCreateResponse)
    async def create_admin_event(
        payload: AdminEventCreateRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> AdminEventCreateResponse:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        title = payload.title.strip()[:256]
        place = payload.place.strip()[:256]
        description = payload.description.strip()[:3500]
        announcement = format_event_notification_html(title=title, place=place, description=description)
        if len(announcement) > 4000:
            raise HTTPException(status_code=400, detail="Announcement text too long for Telegram")
        event_id = await create_mentor_event(title=title, place=place, description=description)
        user_ids = await get_all_users_ids()
        delivered = 0
        for uid in user_ids:
            try:
                await bot.send_message(uid, announcement, parse_mode="HTML")
                delivered += 1
            except Exception:
                pass
        return AdminEventCreateResponse(ok=True, event_id=event_id, delivered=delivered, total=len(user_ids))

    @app.post("/api/admin/broadcast")
    async def admin_broadcast(
        payload: AdminBroadcastRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool | int]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        text = escape(payload.text.strip())
        broadcast_html = f"📢 <b>Объявление от ментора:</b>\n\n{text}"
        if len(broadcast_html) > 4096:
            raise HTTPException(status_code=400, detail="Broadcast text too long")
        user_ids = await get_all_users_ids()
        delivered = 0
        for uid in user_ids:
            try:
                await bot.send_message(uid, broadcast_html, parse_mode="HTML")
                delivered += 1
            except Exception:
                pass
        return {"ok": True, "delivered": delivered, "total": len(user_ids)}

    @app.get("/api/admin/users", response_model=AdminUsersResponse)
    async def list_admin_users(
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> AdminUsersResponse:
        await verify_token(x_internal_token)
        verify_admin_user(tg_user_id)
        users = await get_all_users(limit=1000)
        blocked_ids = await get_blocked_user_ids()
        items = [
            AdminUserItem(
                telegram_id=user.telegram_id,
                username=user.username,
                full_name=user.full_name,
                joined_at=user.joined_at,
                is_blocked=user.telegram_id in blocked_ids,
            )
            for user in users
        ]
        return AdminUsersResponse(items=items)

    @app.post("/api/admin/users/{telegram_id}/block")
    async def block_admin_user(
        telegram_id: int,
        payload: AdminUserActionRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        if telegram_id == admin_id:
            raise HTTPException(status_code=400, detail="Cannot block admin")
        await block_user(telegram_id, payload.reason)
        return {"ok": True}

    @app.post("/api/admin/users/{telegram_id}/unblock")
    async def unblock_admin_user(
        telegram_id: int,
        payload: AdminUserActionRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        await unblock_user(telegram_id)
        return {"ok": True}

    @app.get("/api/admin/schedule")
    async def admin_schedule_get(
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        await verify_token(x_internal_token)
        verify_admin_user(tg_user_id)
        row = await get_schedule_settings()
        return {
            "weekly_hours": row.weekly_hours,
            "slot_minutes": row.slot_minutes,
            "timezone": row.timezone,
        }

    @app.put("/api/admin/schedule")
    async def admin_schedule_put(
        payload: ScheduleUpdateRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        try:
            weekly = {str(k): dict(v) for k, v in payload.weekly_hours.items()}
            await update_schedule_settings(
                weekly_hours=weekly,
                slot_minutes=payload.slot_minutes,
                tz_name=payload.timezone,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True}

    @app.get("/api/admin/meetings")
    async def admin_meetings_list(
        tg_user_id: int = Query(...),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        await verify_token(x_internal_token)
        verify_admin_user(tg_user_id)
        sched = await get_schedule_settings()
        tz = ZoneInfo(sched.timezone)
        today = datetime.now(tz).date()
        rows = await list_meeting_bookings(
            date_from=today - timedelta(days=1),
            date_to=today + timedelta(days=90),
        )
        items: list[dict[str, Any]] = []
        for booking, full_name, uname in rows:
            items.append(
                {
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
                }
            )
        return {"items": items, "timezone": sched.timezone}

    @app.post("/api/admin/meetings/{booking_id}/confirm")
    async def admin_meeting_confirm(
        booking_id: int,
        payload: AdminMeetingActionRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        b = await confirm_meeting_booking(booking_id)
        if b is None:
            raise HTTPException(status_code=404, detail="Booking not found or not pending")
        sched = await get_schedule_settings()
        when = format_booking_local_human(b, sched.timezone)
        try:
            await bot.send_message(
                b.student_user_id,
                format_meeting_confirmed_student(when_human=when),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return {"ok": True}

    @app.post("/api/admin/meetings/{booking_id}/complete")
    async def admin_meeting_complete(
        booking_id: int,
        payload: AdminMeetingActionRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        await verify_token(x_internal_token)
        verify_admin_user(payload.tg_user_id)
        b = await complete_meeting_booking(booking_id)
        if b is None:
            raise HTTPException(status_code=404, detail="Booking not found or not confirmed")
        sched = await get_schedule_settings()
        when = format_booking_local_human(b, sched.timezone)
        try:
            await bot.send_message(
                b.student_user_id,
                format_meeting_completed_student(when_human=when),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return {"ok": True}

    return app
