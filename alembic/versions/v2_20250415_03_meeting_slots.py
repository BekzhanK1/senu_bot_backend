"""mentor_schedule_settings + meeting_bookings for real slot booking.

Revision ID: v2_core_003
Revises: v2_core_002
Create Date: 2025-04-15

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v2_core_003"
down_revision: Union[str, None] = "v2_core_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_WEEKLY = {str(i): {"enabled": i < 5, "start": "10:00", "end": "18:00"} for i in range(7)}


def upgrade() -> None:
    op.create_table(
        "mentor_schedule_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("weekly_hours_json", sa.JSON(), nullable=False),
        sa.Column("slot_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Almaty", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "meeting_bookings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending_confirm", nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_bookings_student_user_id", "meeting_bookings", ["student_user_id"], unique=False)
    op.create_index("ix_meeting_bookings_start_at", "meeting_bookings", ["start_at"], unique=False)
    op.create_index("ix_meeting_bookings_status", "meeting_bookings", ["status"], unique=False)

    schedule = sa.table(
        "mentor_schedule_settings",
        sa.column("id", sa.Integer),
        sa.column("weekly_hours_json", sa.JSON),
        sa.column("slot_minutes", sa.Integer),
        sa.column("timezone", sa.String(length=64)),
    )
    op.bulk_insert(
        schedule,
        [
            {
                "id": 1,
                "weekly_hours_json": _DEFAULT_WEEKLY,
                "slot_minutes": 30,
                "timezone": "Asia/Almaty",
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_meeting_bookings_status", table_name="meeting_bookings")
    op.drop_index("ix_meeting_bookings_start_at", table_name="meeting_bookings")
    op.drop_index("ix_meeting_bookings_student_user_id", table_name="meeting_bookings")
    op.drop_table("meeting_bookings")
    op.drop_table("mentor_schedule_settings")
