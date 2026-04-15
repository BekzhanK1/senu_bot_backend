import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import CallbackQuery, ContentType, Message

from database.db import add_user, get_user, is_user_blocked

logger = logging.getLogger(__name__)


class RequireStartMiddleware(BaseMiddleware):
    """Require /start (or Mini App registration) before other user flows."""

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        if await is_user_blocked(user.id):
            logger.info("Blocked user attempted interaction: user_id=%s", user.id)
            if isinstance(event, CallbackQuery):
                await event.answer("Ваш доступ ограничен администратором.", show_alert=True)
                return None
            if isinstance(event, Message):
                await event.answer("⛔ Ваш доступ к боту ограничен администратором.")
                return None
            return None

        if isinstance(event, Message):
            text = event.text or ""
            if text.startswith("/start"):
                await add_user(
                    telegram_id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                )
                logger.info("User registered via /start: user_id=%s username=%s", user.id, user.username)
                return await handler(event, data)

            if event.content_type == ContentType.WEB_APP_DATA:
                await add_user(
                    telegram_id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                )
                logger.info("User registered via WEB_APP_DATA: user_id=%s username=%s", user.id, user.username)
                return await handler(event, data)

        existing_user = await get_user(user.id)
        if existing_user:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("Сначала нажми /start в чате с ботом.", show_alert=True)
            await event.message.answer("👋 Для начала работы отправь команду /start.")
            return None

        if isinstance(event, Message):
            await event.answer("👋 Для начала работы отправь команду /start.")
            return None

        return await handler(event, data)
