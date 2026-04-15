import logging
import os

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.db import create_request
from database.events import emit_event
from handlers.auth_middleware import RequireStartMiddleware
from handlers.crisis_fsm import CrisisFlow
from keyboards.inline import get_admin_resolve_kb
from keyboards.reply import get_main_menu
from utils.ux_copy import NOTIFY_ON_STATUS_CHANGE

logger = logging.getLogger(__name__)

crisis_router = Router()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

CRISIS_ENTRY_TEXTS = frozenset(
    {
        "🆘 Мне тяжело сейчас",
    }
)

GROUNDING_MESSAGE = (
    "🫂 <b>Спасибо, что написал(а).</b> То, что ты чувствуешь — важно.\n\n"
    "Сделай 3 медленных вдоха: вдох на 4 счёта — пауза — выдох на 6.\n"
    "Если хочешь, положи руку на грудь и назови вслух один предмет рядом с собой.\n\n"
    "Когда будешь готов(а) продолжить, нажми кнопку ниже."
)

PCS_BLOCK = (
    "\n\n<b>🆘 Если тебе нужна срочная поддержка прямо сейчас:</b>\n"
    "• Бот PCS: @pcs_nu_bot\n"
    "• Телефон доверия: <b>111</b>\n"
    "Ты не обязан(а) справляться один(а)."
)


def _crisis_continue_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Продолжить ▶️", callback_data="crisis:continue")]]
    )


def _stress_to_severity(level: int) -> str:
    if level >= 4:
        return "high"
    if level >= 3:
        return "medium"
    return "low"


crisis_router.message.middleware(RequireStartMiddleware())
crisis_router.callback_query.middleware(RequireStartMiddleware())


@crisis_router.message(Command("crisis"))
@crisis_router.message(Command("heavy"))
@crisis_router.message(F.text.in_(CRISIS_ENTRY_TEXTS))
async def crisis_entry(message: Message, state: FSMContext) -> None:
    await state.set_state(CrisisFlow.after_grounding)
    await emit_event(event_name="crisis_flow_started", user_telegram_id=message.from_user.id)
    await message.answer(GROUNDING_MESSAGE, reply_markup=_crisis_continue_kb(), parse_mode="HTML")


@crisis_router.callback_query(StateFilter(CrisisFlow.after_grounding), F.data == "crisis:continue")
async def crisis_after_grounding(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(CrisisFlow.waiting_stress)
    await emit_event(event_name="crisis_grounding_ack", user_telegram_id=callback.from_user.id)
    await callback.message.answer(
        "Оцени свой уровень стресса <b>от 1</b> (легко) <b>до 5</b> (очень тяжело). "
        "Отправь одну цифру.",
        parse_mode="HTML",
    )


@crisis_router.message(StateFilter(CrisisFlow.waiting_stress), F.text.regexp(r"^[1-5]$"))
async def crisis_stress_level(message: Message, state: FSMContext, bot: Bot) -> None:
    level = int(message.text or "0")
    user = message.from_user
    severity = _stress_to_severity(level)

    await emit_event(
        event_name="crisis_stress_reported",
        user_telegram_id=user.id,
        metadata={"stress_level": level, "severity": severity},
    )

    content = (
        f"Crisis triage (Mini flow)\n"
        f"Стресс: {level}/5\n"
        f"Severity: {severity}\n"
        f"User: {user.full_name} (@{user.username or '—'})"
    )
    req_id = await create_request(user.id, "crisis_triage", content)

    route_event = "crisis_routed_high" if level >= 4 else "crisis_routed_standard"
    await emit_event(
        event_name=route_event,
        user_telegram_id=user.id,
        metadata={"stress_level": level, "request_id": req_id},
    )

    if level >= 4:
        await bot.send_message(
            ADMIN_ID,
            f"⚠️ <b>Crisis triage (высокий стресс {level}/5)</b>\n{content}",
            reply_markup=get_admin_resolve_kb(req_id),
            parse_mode="HTML",
        )
        await message.answer(
            "Я рядом. Ментор получит уведомление."
            + PCS_BLOCK
            + "\n\nМожешь записаться на встречу через меню «📅 Запись на встречу»."
            + NOTIFY_ON_STATUS_CHANGE,
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )
    else:
        await bot.send_message(
            ADMIN_ID,
            f"🔔 <b>Crisis triage</b> ({level}/5)\n{content}",
            reply_markup=get_admin_resolve_kb(req_id),
            parse_mode="HTML",
        )
        await message.answer(
            "Спасибо за честность. Ментор увидит это сообщение и свяжется с тобой.\n"
            "Пока можешь открыть «💡 Совет дня» или записаться на встречу.\n"
            "Если станет хуже — нажми «🆘 Мне тяжело сейчас» снова или "
            "«🚑 Помощь (PCS)»."
            + (PCS_BLOCK if level >= 3 else "")
            + NOTIFY_ON_STATUS_CHANGE,
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )

    await state.clear()


@crisis_router.message(StateFilter(CrisisFlow.waiting_stress))
async def crisis_stress_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправь одну цифру от <b>1</b> до <b>5</b>.", parse_mode="HTML")
