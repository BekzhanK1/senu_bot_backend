import os
from typing import Literal, Optional

from aiogram import Bot
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from database.db import add_user, create_request
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


def create_api_app(bot: Bot) -> FastAPI:
    app = FastAPI(title="SENU Bot API", version="1.0.0")
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    internal_token = os.getenv("INTERNAL_API_TOKEN")

    async def verify_token(x_internal_token: str | None) -> None:
        if internal_token and x_internal_token != internal_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

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

    return app
