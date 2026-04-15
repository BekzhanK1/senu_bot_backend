from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    buttons = [
        [KeyboardButton(text="🆘 Мне тяжело сейчас")],
        [KeyboardButton(text="💎 Ментор Айнур"), KeyboardButton(text="📅 Запись на встречу")],
        [KeyboardButton(text="🎭 Игра «108»"), KeyboardButton(text="❓ Задать вопрос")],
        [KeyboardButton(text="💡 Совет дня"), KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="🚑 Помощь (PCS)")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие в меню 👇"
    )
