import os

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database.db import (
    create_mentor_event,
    get_all_users_ids,
    get_pending_requests,
    get_request_by_id,
    resolve_request,
)
from keyboards.inline import get_admin_resolve_kb
from utils.mentor_event_message import format_event_notification_html
from utils.request_labels import format_request_type_ru
from utils.student_notifications import notify_request_resolved

admin_router = Router()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

_MAX_TITLE_PLACE = 250
_MAX_DESCRIPTION = 3500


class AdminState(StatesGroup):
    waiting_for_reply = State()


class EventForm(StatesGroup):
    title = State()
    place = State()
    description = State()

@admin_router.message(Command("new_event"))
async def cmd_new_event(message: Message, state: FSMContext) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(EventForm.title)
    await message.answer(
        "🎉 <b>Новое событие</b> (шаг 1 из 3)\n\n"
        "Напиши <b>название</b> — как на афише, коротко.\n\n"
        "<i>/cancel — отменить.</i>",
        parse_mode="HTML",
    )


@admin_router.message(Command("cancel"), StateFilter(EventForm))
async def event_form_cancel(message: Message, state: FSMContext) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("Создание события отменено.")


@admin_router.message(EventForm.title, F.text)
async def event_form_title(message: Message, state: FSMContext) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    if message.text and message.text.startswith("/"):
        await message.answer("Сейчас мастер создания события. Продолжи шаг или отправь /cancel.")
        return
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("Название слишком короткое. Напиши хотя бы пару слов.")
        return
    title = title[:_MAX_TITLE_PLACE]
    await state.update_data(event_title=title)
    await state.set_state(EventForm.place)
    await message.answer(
        "📍 Шаг 2 из 3: <b>место</b>\n\n"
        "Аудитория, кампус, онлайн — что угодно, главное чтобы студентам было понятно.",
        parse_mode="HTML",
    )


@admin_router.message(EventForm.place, F.text)
async def event_form_place(message: Message, state: FSMContext) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    if message.text and message.text.startswith("/"):
        await message.answer("Сейчас мастер создания события. Продолжи шаг или отправь /cancel.")
        return
    place = (message.text or "").strip()
    if len(place) < 2:
        await message.answer("Уточни место чуть подробнее (хотя бы пара символов).")
        return
    place = place[:_MAX_TITLE_PLACE]
    await state.update_data(event_place=place)
    await state.set_state(EventForm.description)
    await message.answer(
        "📝 Шаг 3 из 3: <b>описание</b>\n\n"
        "Расскажи, что будет на событии, для кого оно, во сколько начало (если знаешь). "
        "Можно одним сообщением.",
        parse_mode="HTML",
    )


@admin_router.message(EventForm.description, F.text)
async def event_form_description(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    if message.text and message.text.startswith("/"):
        await message.answer("Сейчас мастер создания события. Продолжи шаг или отправь /cancel.")
        return
    description = (message.text or "").strip()
    if len(description) < 5:
        await message.answer("Описание слишком короткое. Добавь пару предложений о событии.")
        return
    description = description[:_MAX_DESCRIPTION]

    data = await state.get_data()
    title = data.get("event_title") or ""
    place = data.get("event_place") or ""
    if not title or not place:
        await state.clear()
        await message.answer("Что-то пошло не так с черновиком. Начни снова: /new_event")
        return

    announcement = format_event_notification_html(title=title, place=place, description=description)
    if len(announcement) > 4000:
        await message.answer(
            "Текст уведомления слишком длинный для Telegram. Сократи описание и начни снова: /new_event"
        )
        await state.clear()
        return

    event_id = await create_mentor_event(title=title, place=place, description=description)

    user_ids = await get_all_users_ids()
    delivered = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, announcement, parse_mode="HTML")
            delivered += 1
        except Exception:
            pass

    await state.clear()
    await message.answer(
        f"✅ Событие <b>№{event_id}</b> сохранено.\n"
        f"Уведомления отправлены: <b>{delivered}</b> из {len(user_ids)} пользователей бота.",
        parse_mode="HTML",
    )


# Команда /admin для списка всех активных заявок
@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    requests = await get_pending_requests()
    if not requests:
        await message.answer(
            "Активных заявок пока нет.\n\n"
            "💡 Событие для всех студентов (название, место, описание): /new_event"
        )
        return
    
    for req, full_name, username in requests:
        user_info = f"{full_name} (@{username})" if username else full_name
        type_ru = format_request_type_ru(req.request_type)
        text = (
            f"📦 <b>Заявка #{req.id}</b>\n"
            f"Тип: {type_ru}\n"
            f"От: {user_info}\n"
            f"Контент: {req.content}\n"
            f"Дата: {req.created_at.strftime('%d.%m %H:%M')}"
        )
        await message.answer(text, reply_markup=get_admin_resolve_kb(req.id), parse_mode="HTML")

    await message.answer("💡 Событие для всех студентов (название, место, описание): /new_event")

# Обработка кнопки "Ответить"
@admin_router.callback_query(F.data.startswith("reply_"))
async def process_reply_button(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    req_id = int(callback.data.split("_")[1])
    await state.update_data(reply_to_req_id=req_id)
    await state.set_state(AdminState.waiting_for_reply)
    await callback.message.answer(f"Введите ответ для заявки #{req_id}:")
    await callback.answer()

# Получение текста ответа и отправка студенту
@admin_router.message(AdminState.waiting_for_reply)
async def send_reply_to_user(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    req_id = data['reply_to_req_id']
    req = await get_request_by_id(req_id)
    
    if req:
        try:
            # Отправляем ответ студенту
            reply_text = (
                f"<b>💬 Сообщение от ментора:</b>\n\n{message.text}\n\n"
                "<i>Когда вопрос будет полностью закрыт, ментор отметит заявку решённой — "
                "я пришлю отдельное уведомление.</i>"
            )
            await bot.send_message(req.user_id, reply_text, parse_mode="HTML")
            
            # Помечаем как решенное (по желанию, можно оставить pending)
            # await resolve_request(req_id)
            
            await message.answer(f"Ответ отправлен пользователю (ID: {req.user_id}).")
        except Exception as e:
            await message.answer(f"Ошибка при отправке: {e}")
    else:
        await message.answer("Заявка не найдена.")
    
    await state.clear()

@admin_router.callback_query(F.data.startswith("resolve_"))
async def process_resolve(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав.")
        return

    req_id = int(callback.data.split("_")[1])
    req = await get_request_by_id(req_id)
    if not req:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if req.status == "resolved":
        await callback.answer("Уже отмечена как решённая.", show_alert=True)
        return

    await resolve_request(req_id)
    await notify_request_resolved(
        bot,
        request_id=req_id,
        user_telegram_id=req.user_id,
        request_type=req.request_type,
    )

    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ <b>СТАТУС: РЕШЕНО</b>",
        parse_mode="HTML",
    )
    await callback.answer("Статус обновлен ✅ Студент уведомлён.")

@admin_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer(
            "⚠️ Использование: /broadcast и дальше текст рассылки одним сообщением.\n\n"
            "Для события (название, место, описание): /new_event"
        )
        return
    
    broadcast_text = f"📢 <b>Объявление от ментора:</b>\n\n{command_parts[1]}"
    user_ids = await get_all_users_ids()
    
    count = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, broadcast_text)
            count += 1
        except Exception:
            pass
    
    await message.answer(f"Рассылка завершена. Доставлено: {count} пользователям.")
