"""add app settings table

Revision ID: v2_20260415_04
Revises: v2_20250415_03
Create Date: 2026-04-15
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "v2_20260415_04"
down_revision: Union[str, None] = "v2_20250415_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    app_settings_table = sa.table(
        "app_settings",
        sa.column("id", sa.Integer),
        sa.column("settings_json", sa.JSON),
        sa.column("updated_by", sa.BigInteger),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        app_settings_table,
        [
            {
                "id": 1,
                "settings_json": {
                    "welcome_message": (
                        "🌟 <b>Привет, {first_name}!</b>\n\n"
                        "Я бот SENU Buddy: помогаю связаться с ментором без лишних шагов. ✨\n\n"
                        "🚀 <b>Что здесь можно сделать:</b>\n"
                        "• <b>🆘 Мне тяжело сейчас</b> — короткая поддержка и связь с ментором\n"
                        "• Записаться на встречу или задать вопрос (в т.ч. анонимно)\n"
                        "• Игра «108», совет дня, контакты PCS\n\n"
                        "Все заявки идут ментору; <b>когда статус заявки изменится, я напишу тебе сюда</b>.\n\n"
                        "Выбери раздел в меню ниже 👇"
                    ),
                    "mentor_about_text": (
                        "👑 <b>Айнур — твой проводник и ментор</b>\n\n"
                        "🎓 <i>Bolashak alumni, выпускница George Washington University (GWU)</i>\n"
                        "🏢 <i>Многолетний опыт работы в Nazarbayev University</i>\n"
                        "🧘 <i>Сертифицированный фасилитатор трансформационной игры «108»</i>\n\n"
                        "Айнур помогает студентам NU находить внутренний баланс, строить академическую траекторию.\n\n"
                        "<b>Твои перемены начинаются здесь!</b>"
                    ),
                    "mentor_photo_url": "",
                    "support_bot_username": "@pcs_nu_bot",
                    "support_hotline": "111",
                    "miniapp_home_title": "Твой SENU-помощник готов к работе",
                    "miniapp_home_footer": "SENU Digital Mentor v2.0",
                },
                "updated_by": None,
                "updated_at": datetime.now(timezone.utc),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("app_settings")
