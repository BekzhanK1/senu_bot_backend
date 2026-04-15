"""Format mentor-created community events for Telegram (HTML)."""

from __future__ import annotations

from html import escape


def format_event_notification_html(*, title: str, place: str, description: str) -> str:
    return (
        "🎉 <b>Новое событие SENU</b>\n\n"
        f"<b>Название:</b> {escape(title.strip())}\n"
        f"<b>Место:</b> {escape(place.strip())}\n\n"
        f"<b>О событии:</b>\n{escape(description.strip())}\n\n"
        "<i>Если не планируешь приходить — просто проигнорируй это сообщение.</i>"
    )
