"""HTML messages for meeting booking lifecycle (Telegram)."""

from __future__ import annotations

from html import escape


def format_meeting_pending_student(*, when_human: str, topic: str | None) -> str:
    t = escape(topic.strip()) if topic else "без темы"
    return (
        "📅 <b>Запрос на встречу отправлен</b>\n\n"
        f"Время: <b>{escape(when_human)}</b>\n"
        f"Тема: {t}\n\n"
        "<i>Ментор подтвердит слот — я напишу, когда всё согласовано.</i>"
    )


def format_meeting_confirmed_student(*, when_human: str) -> str:
    return (
        "✅ <b>Встреча подтверждена</b>\n\n"
        f"Ждём тебя: <b>{escape(when_human)}</b>\n\n"
        "<i>Если не сможешь прийти — напиши ментору через бота как можно раньше.</i>"
    )


def format_meeting_completed_student(*, when_human: str) -> str:
    return (
        "🎉 <b>Встреча завершена</b>\n\n"
        f"Мы встречались: {escape(when_human)}\n\n"
        "<i>Если понадобится ещё раз — записывайся снова из меню.</i>"
    )


def format_admin_new_booking(*, booking_id: int, student_name: str, when_human: str, topic: str | None) -> str:
    t = escape(topic.strip()) if topic else "—"
    return (
        f"📅 <b>Новая бронь слота #{booking_id}</b>\n"
        f"От: {escape(student_name)}\n"
        f"Время: <b>{escape(when_human)}</b>\n"
        f"Тема: {t}\n\n"
        "<i>Подтверди или заверши встречу в панели ментора (Mini App).</i>"
    )
