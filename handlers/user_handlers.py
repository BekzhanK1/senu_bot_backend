import os
import json
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.fsm.context import FSMContext

from database.db import add_user, create_request, get_random_tip, get_user_requests
from keyboards.reply import get_main_menu
from keyboards.inline import get_game_kb, get_question_kb, get_admin_resolve_kb, get_back_kb, get_webapp_kb
from handlers.fsm_forms import MeetingForm, QuestionForm

user_router = Router()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-domain.com/calendar")

@user_router.message(CommandStart())
async def cmd_start(message: Message):
    await add_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    
    welcome_text = (
        f"🌟 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        "Я твой цифровой помощник в мире SENU. "
        "Здесь ты можешь стать лучшей версией себя вместе с ментором Айнур! ✨\n\n"
        "🚀 <b>Что я умею:</b>\n"
        "• Записывать на личные встречи\n"
        "• Организовывать игры «108»\n"
        "• Давать полезные советы на каждый день\n"
        "• Отвечать на твои вопросы (даже анонимно!)\n\n"
        "Выбери нужный раздел в меню ниже 👇"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="HTML")

# --- Mini App Data Handler ---

@user_router.message(F.content_type == ContentType.WEB_APP_DATA)
async def process_webapp_data(message: Message, bot: Bot):
    try:
        data = json.loads(message.web_app_data.data)
        data_type = data.get('type')
        user = message.from_user
        username = f"@{user.username}" if user.username else user.full_name
        
        if data_type == 'meeting':
            day = data.get('day')
            time = data.get('time')
            content = f"📅 Встреча через Mini App\nДата: {day}\nВремя: {time}"
            req_id = await create_request(user.id, "meeting", content)
            
            admin_msg = f"🔔 <b>Новая запись: Встреча</b>\nОт: {user.full_name} ({username})\n<b>{day} в {time}</b>"
            await bot.send_message(ADMIN_ID, admin_msg, reply_markup=get_admin_resolve_kb(req_id), parse_mode="HTML")
            await message.answer(f"✨ <b>Запись подтверждена!</b>\nЖдем тебя {day} в {time}.", parse_mode="HTML")
            
        elif data_type == 'game_108':
            req_id = await create_request(user.id, "game_108", "Заявка через Mini App")
            admin_msg = f"🔔 <b>Новая заявка: Игра 108</b>\nОт: {user.full_name} ({username})"
            await bot.send_message(ADMIN_ID, admin_msg, reply_markup=get_admin_resolve_kb(req_id), parse_mode="HTML")
            await message.answer("🙌 <b>Заявка на игру 108 принята!</b>\nАйнур скоро свяжется с тобой.", parse_mode="HTML")

        elif data_type == 'question':
            text = data.get('text')
            is_anon = data.get('is_anonymous')
            q_type = "anonymous_question" if is_anon else "question"
            req_id = await create_request(user.id, q_type, text)
            
            sender = "🕵️ Анонимно" if is_anon else f"👤 {user.full_name}"
            admin_msg = f"🔔 <b>Новый вопрос ({sender})</b>\nТекст: {text}"
            await bot.send_message(ADMIN_ID, admin_msg, reply_markup=get_admin_resolve_kb(req_id), parse_mode="HTML")
            await message.answer("🚀 <b>Твой вопрос отправлен ментору!</b>", parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке данных: {e}")

# --- О менторе ---

@user_router.message(F.text == "💎 Ментор Айнур")
async def about_mentor(message: Message):
    photo_url = os.getenv("MENTOR_PHOTO_URL")
    text = (
        "👑 <b>Айнур — твой проводник и ментор</b>\n\n"
        "🎓 <i>Bolashak alumni, выпускница George Washington University (GWU)</i>\n"
        "🏢 <i>Многолетний опыт работы в Nazarbayev University</i>\n"
        "🧘 <i>Сертифицированный фасилитатор трансформационной игры «108»</i>\n\n"
        "Айнур помогает студентам NU находить внутренний баланс, строить академическую траекторию.\n\n"
        "<b>Твои перемены начинаются здесь!</b>"
    )
    try:
        if photo_url:
            await message.answer_photo(photo=photo_url, caption=text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")
    except Exception:
        await message.answer(text, parse_mode="HTML")

# --- Совет дня и Профиль ---

@user_router.message(F.text == "💡 Совет дня")
@user_router.message(Command("tip"))
async def tip_of_the_day(message: Message):
    tip = await get_random_tip()
    if tip:
        text = f"<b>💡 Совет дня</b>\nКатегория: <i>#{tip.category}</i>\n\n«{tip.text}»"
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("Сегодня советов нет, просто будь собой! ✨")

@user_router.message(F.text == "👤 Мой профиль")
@user_router.message(Command("profile"))
async def my_profile(message: Message):
    requests = await get_user_requests(message.from_user.id)
    text = f"👤 <b>Профиль: {message.from_user.full_name}</b>\n\n"
    if not requests:
        text += "У тебя пока нет активных заявок."
    else:
        text += "<b>Твои последние заявки:</b>\n"
        for req in requests:
            status_emoji = "⏳" if req.status == "pending" else "✅"
            text += f"\n{status_emoji} {req.request_type} — {req.created_at.strftime('%d.%m')}"
    await message.answer(text, parse_mode="HTML")

# --- Запись на встречу (Mini App + Fallback) ---

@user_router.message(F.text == "📅 Запись на встречу")
async def meeting_start(message: Message, state: FSMContext):
    if "your-domain.com" not in WEBAPP_URL:
        await message.answer(
            "🗓 <b>Выберите удобное время в календаре:</b>",
            reply_markup=get_webapp_kb(WEBAPP_URL),
            parse_mode="HTML"
        )
    else:
        await state.set_state(MeetingForm.waiting_for_topic)
        await message.answer(
            "✍️ <b>О чем ты хочешь поговорить?</b>\n(Академические вопросы, личные цели или просто поддержка)\n\n"
            "<i>(P.S. Когда админ настроит Mini App, здесь появится календарь!)</i>", 
            reply_markup=get_back_kb(),
            parse_mode="HTML"
        )

@user_router.message(MeetingForm.waiting_for_topic)
async def meeting_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await state.set_state(MeetingForm.waiting_for_time)
    await message.answer("⏰ <b>Когда тебе удобно встретиться?</b>", reply_markup=get_back_kb(), parse_mode="HTML")

@user_router.message(MeetingForm.waiting_for_time)
async def meeting_time(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    content = f"Тема: {data['topic']}\nВремя: {message.text}"
    req_id = await create_request(message.from_user.id, "meeting", content)
    await bot.send_message(ADMIN_ID, f"🔔 <b>Новая запись:</b>\n{content}", reply_markup=get_admin_resolve_kb(req_id), parse_mode="HTML")
    await state.clear()
    await message.answer("✨ <b>Готово!</b> Айнур свяжется с тобой совсем скоро.", parse_mode="HTML")

# --- Остальные обработчики (Вопросы, Игра, PCS) ---

@user_router.message(F.text == "🚑 Помощь (PCS)")
async def pcs_help(message: Message):
    text = "<b>🆘 Психологическая помощь (PCS)</b>\n\n• Бот: @pcs_nu_bot\n• Телефон доверия: <b>111</b>"
    await message.answer(text, parse_mode="HTML")

@user_router.message(F.text == "🎭 Игра «108»")
async def game_108(message: Message):
    text = "🎯 <b>Трансформационная игра «108»</b>\n\nГотов(а) заглянуть вглубь себя?"
    await message.answer(text, reply_markup=get_game_kb(), parse_mode="HTML")

@user_router.callback_query(F.data == "wanna_play_108")
async def wanna_play(callback: CallbackQuery, bot: Bot):
    req_id = await create_request(callback.from_user.id, "game_108", "Хочет сыграть")
    await bot.send_message(ADMIN_ID, f"🔔 <b>Игра 108:</b> от {callback.from_user.full_name}", reply_markup=get_admin_resolve_kb(req_id), parse_mode="HTML")
    await callback.answer("Заявка отправлена! 🎲")
    await callback.message.answer("🙌 <b>Айнур получила твой запрос на игру!</b>", parse_mode="HTML")

@user_router.message(F.text == "❓ Задать вопрос")
async def question_start(message: Message):
    await message.answer("🕊 <b>Как ты хочешь задать вопрос?</b>", reply_markup=get_question_kb(), parse_mode="HTML")

@user_router.callback_query(F.data.startswith("ask_"))
async def process_ask_choice(callback: CallbackQuery, state: FSMContext):
    if callback.data == "back_to_main":
        await callback.message.answer("Меню:", reply_markup=get_main_menu())
        await callback.answer()
        return
    await state.update_data(is_anonymous=(callback.data == "ask_anon"))
    await state.set_state(QuestionForm.waiting_for_text)
    await callback.message.edit_text("📝 <b>Введи текст вопроса:</b>", reply_markup=get_back_kb(), parse_mode="HTML")
    await callback.answer()

@user_router.message(QuestionForm.waiting_for_text)
async def process_question_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    q_type = "anonymous_question" if data['is_anonymous'] else "question"
    req_id = await create_request(message.from_user.id, q_type, message.text)
    sender = "🕵️ Анонимно" if data['is_anonymous'] else f"👤 {message.from_user.full_name}"
    await bot.send_message(ADMIN_ID, f"🔔 <b>Новый вопрос ({sender}):</b>\n{message.text}", reply_markup=get_admin_resolve_kb(req_id), parse_mode="HTML")
    await state.clear()
    await message.answer("🚀 <b>Твой вопрос улетел к ментору!</b>", parse_mode="HTML")

@user_router.callback_query(F.data == "cancel_fsm")
async def cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()
