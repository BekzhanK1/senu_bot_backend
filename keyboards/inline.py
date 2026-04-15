from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

def get_webapp_kb(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Открыть календарь", web_app=WebAppInfo(url=url))]
    ])

def get_game_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Хочу сыграть!", callback_data="wanna_play_108")]
    ])

def get_question_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Открыто", callback_data="ask_public"),
            InlineKeyboardButton(text="🕵️ Анонимно", callback_data="ask_anon")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])

def get_admin_resolve_kb(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Решено", callback_data=f"resolve_{request_id}"),
            InlineKeyboardButton(text="✍️ Ответить", callback_data=f"reply_{request_id}")
        ]
    ])

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel_fsm")]
    ])
