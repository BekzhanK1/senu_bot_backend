import os
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    resolve_request, 
    get_all_users_ids, 
    get_pending_requests, 
    get_request_by_id
)
from keyboards.inline import get_admin_resolve_kb

admin_router = Router()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

class AdminState(StatesGroup):
    waiting_for_reply = State()

# Команда /admin для списка всех активных заявок
@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    requests = await get_pending_requests()
    if not requests:
        await message.answer("Активных заявок пока нет.")
        return
    
    for req, full_name, username in requests:
        user_info = f"{full_name} (@{username})" if username else full_name
        text = (
            f"📦 <b>Заявка #{req.id}</b>\n"
            f"Тип: {req.request_type}\n"
            f"От: {user_info}\n"
            f"Контент: {req.content}\n"
            f"Дата: {req.created_at.strftime('%d.%m %H:%M')}"
        )
        await message.answer(text, reply_markup=get_admin_resolve_kb(req.id), parse_mode="HTML")

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
            reply_text = f"<b>Ответ от ментора Айнур:</b>\n\n{message.text}"
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
async def process_resolve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав.")
        return
    
    req_id = int(callback.data.split("_")[1])
    await resolve_request(req_id)
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ <b>СТАТУС: РЕШЕНО</b>",
        parse_mode="HTML"
    )
    await callback.answer("Статус обновлен ✅")

@admin_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("⚠️ <b>Использование:</b> /broadcast <текст рассылки>")
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
