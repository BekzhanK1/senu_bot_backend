"""Human-readable labels for request types (single-mentor / admin flow)."""

REQUEST_TYPE_LABELS_RU: dict[str, str] = {
    "meeting": "Встреча с ментором",
    "game_108": "Игра «108»",
    "question": "Вопрос ментору",
    "anonymous_question": "Анонимный вопрос",
    "crisis_triage": "Поддержка («Мне тяжело»)",
}


def format_request_type_ru(request_type: str) -> str:
    return REQUEST_TYPE_LABELS_RU.get(request_type, request_type)
