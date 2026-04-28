"""Router for request-related endpoints."""

from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from services.container import get_services
from services.audit_service import AuditService
from utils.security import verify_internal_token, verify_admin_access, rate_limit, get_api_rate_limiter


router = APIRouter(prefix="/api", tags=["requests"])


# Request models
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


@router.post("/requests/question", response_model=ApiResponse)
@rate_limit(get_api_rate_limiter())
async def create_question_request(
    payload: QuestionRequest,
    x_internal_token: str | None = Header(default=None),
) -> ApiResponse:
    """Create a question request."""
    await verify_internal_token(x_internal_token)
    
    services = get_services()
    user = payload.tg_user
    
    # Check if user is blocked
    from database.db import is_user_blocked, add_user
    if await is_user_blocked(user.id):
        raise HTTPException(status_code=403, detail="User is blocked")
    
    await add_user(user.id, user.username, user.full_name)
    
    # Create request
    request_type = "anonymous_question" if payload.is_anonymous else "question"
    req_id = await services.request_service.create_user_request(
        user.id,
        request_type,
        payload.text.strip(),
    )
    
    # Notify admin
    sender = "🕵️ Анонимно" if payload.is_anonymous else f"👤 {user.full_name}"
    admin_msg = f"🔔 <b>Новый вопрос ({sender})</b>\nТекст: {payload.text.strip()}"
    
    from keyboards.inline import get_admin_resolve_kb
    await services.notification_service.send_message(
        services.meeting_service.admin_id,
        admin_msg,
        reply_markup=get_admin_resolve_kb(req_id),
        parse_mode="HTML",
    )
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=user.id,
        action="create_question",
        entity_type="request",
        entity_id=str(req_id),
        details={"is_anonymous": payload.is_anonymous},
    )
    
    return ApiResponse(ok=True, request_id=req_id)


@router.post("/requests/meeting", response_model=ApiResponse)
@rate_limit(get_api_rate_limiter())
async def create_meeting_request(
    payload: MeetingRequest,
    x_internal_token: str | None = Header(default=None),
) -> ApiResponse:
    """Create a meeting request (legacy endpoint)."""
    await verify_internal_token(x_internal_token)
    
    services = get_services()
    user = payload.tg_user
    
    # Check if user is blocked
    from database.db import is_user_blocked, add_user
    if await is_user_blocked(user.id):
        raise HTTPException(status_code=403, detail="User is blocked")
    
    await add_user(user.id, user.username, user.full_name)
    
    # Create request
    content = f"📅 Встреча через Mini App\nДата: {payload.day}\nВремя: {payload.time}"
    req_id = await services.request_service.create_user_request(
        user.id,
        "meeting",
        content,
    )
    
    # Notify admin
    username = f"@{user.username}" if user.username else user.full_name
    admin_msg = (
        "🔔 <b>Новая запись: Встреча</b>\n"
        f"От: {user.full_name} ({username})\n"
        f"<b>{payload.day} в {payload.time}</b>"
    )
    
    from keyboards.inline import get_admin_resolve_kb
    await services.notification_service.send_message(
        services.meeting_service.admin_id,
        admin_msg,
        reply_markup=get_admin_resolve_kb(req_id),
        parse_mode="HTML",
    )
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=user.id,
        action="create_meeting_request",
        entity_type="request",
        entity_id=str(req_id),
        details={"day": payload.day, "time": payload.time},
    )
    
    return ApiResponse(ok=True, request_id=req_id)


@router.post("/requests/game_108", response_model=ApiResponse)
@rate_limit(get_api_rate_limiter())
async def create_game_request(
    payload: GameRequest,
    x_internal_token: str | None = Header(default=None),
) -> ApiResponse:
    """Create a game 108 request."""
    await verify_internal_token(x_internal_token)
    
    services = get_services()
    user = payload.tg_user
    
    # Check if user is blocked
    from database.db import is_user_blocked, add_user
    if await is_user_blocked(user.id):
        raise HTTPException(status_code=403, detail="User is blocked")
    
    await add_user(user.id, user.username, user.full_name)
    
    # Create request
    req_id = await services.request_service.create_user_request(
        user.id,
        "game_108",
        "Заявка через Mini App API",
    )
    
    # Notify admin
    username = f"@{user.username}" if user.username else user.full_name
    admin_msg = f"🔔 <b>Новая заявка: Игра 108</b>\nОт: {user.full_name} ({username})"
    
    from keyboards.inline import get_admin_resolve_kb
    await services.notification_service.send_message(
        services.meeting_service.admin_id,
        admin_msg,
        reply_markup=get_admin_resolve_kb(req_id),
        parse_mode="HTML",
    )
    
    # Audit log
    await AuditService.log_action(
        actor_telegram_id=user.id,
        action="create_game_request",
        entity_type="request",
        entity_id=str(req_id),
    )
    
    return ApiResponse(ok=True, request_id=req_id)
