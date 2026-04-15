"""Notify students about request lifecycle (Telegram)."""

from __future__ import annotations

import logging

from aiogram import Bot

from utils.request_labels import format_request_type_ru

logger = logging.getLogger(__name__)

STATUS_FOOTER = (
    "\n\nЕсли нужна ещё помощь — открой меню или нажми «🆘 Мне тяжело сейчас», "
    "если снова тяжело."
)


async def notify_request_resolved(
    bot: Bot,
    *,
    request_id: int,
    user_telegram_id: int,
    request_type: str,
) -> None:
    label = format_request_type_ru(request_type)
    text = (
        f"✅ <b>Заявка №{request_id} закрыта</b>\n\n"
        f"Ментор отметил обращение как <b>решённое</b>.\n"
        f"Тип: {label}"
        f"{STATUS_FOOTER}"
    )
    try:
        await bot.send_message(user_telegram_id, text, parse_mode="HTML")
    except Exception:
        logger.exception(
            "notify_request_resolved failed user_id=%s request_id=%s",
            user_telegram_id,
            request_id,
        )
