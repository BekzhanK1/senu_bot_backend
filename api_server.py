import os
from datetime import datetime
from typing import Literal, Optional

from aiogram import Bot
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from database.db import (
    add_user,
    block_user,
    create_request,
    get_all_users,
    get_blocked_user_ids,
    get_user,
    get_user_requests,
    get_requests_for_admin,
    is_user_blocked,
    resolve_request,
    unblock_user,
)
from keyboards.inline import get_admin_resolve_kb


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
        await resolve_request(request_id)
        return {"ok": True}

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

    return app
