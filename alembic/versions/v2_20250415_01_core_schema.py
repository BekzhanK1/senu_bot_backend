"""v2 core schema: user profile columns + mentors, cases, analytics.

Revision ID: v2_core_001
Revises:
Create Date: 2025-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v2_core_001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("faculty", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("study_year", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column("analytics_consent", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("users", sa.Column("crisis_consent_at", sa.DateTime(), nullable=True))

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "mentors",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("languages", sa.String(length=255), nullable=True),
        sa.Column("skills", sa.Text(), nullable=True),
        sa.Column("max_weekly_appointments", sa.Integer(), server_default="10", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "mentor_roles",
        sa.Column("mentor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["mentor_user_id"], ["mentors.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("mentor_user_id", "role_id"),
    )

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_mentor_id", sa.BigInteger(), nullable=True),
        sa.Column("severity", sa.String(length=32), server_default="medium", nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("first_response_due_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("linked_request_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_mentor_id"], ["mentors.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_request_id"], ["requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cases_student_user_id", "cases", ["student_user_id"], unique=False)
    op.create_index("ix_cases_assigned_mentor_id", "cases", ["assigned_mentor_id"], unique=False)
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)

    op.create_table(
        "case_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("author_type", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_messages_case_id", "case_messages", ["case_id"], unique=False)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("mentor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("channel", sa.String(length=64), server_default="telegram", nullable=False),
        sa.Column("attendance_status", sa.String(length=32), server_default="scheduled", nullable=False),
        sa.Column("external_calendar_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mentor_user_id"], ["mentors.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_student_user_id", "appointments", ["student_user_id"], unique=False)
    op.create_index("ix_appointments_mentor_user_id", "appointments", ["mentor_user_id"], unique=False)
    op.create_index("ix_appointments_start_at", "appointments", ["start_at"], unique=False)
    op.create_index("ix_appointments_end_at", "appointments", ["end_at"], unique=False)

    op.create_table(
        "mentor_availability",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mentor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("calendar_event_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["mentor_user_id"], ["mentors.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mentor_availability_mentor_user_id", "mentor_availability", ["mentor_user_id"], unique=False)

    op.create_table(
        "wellbeing_checkins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("stress_score", sa.Integer(), nullable=True),
        sa.Column("mood_note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wellbeing_checkins_user_id", "wellbeing_checkins", ["user_id"], unique=False)

    op.create_table(
        "interventions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("intervention_type", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("perceived_effect", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interventions_user_id", "interventions", ["user_id"], unique=False)

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("actor_id_hash", sa.String(length=64), nullable=True),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_event_name", "analytics_events", ["event_name"], unique=False)
    op.create_index("ix_analytics_events_actor_id_hash", "analytics_events", ["actor_id_hash"], unique=False)
    op.create_index("ix_analytics_events_case_id", "analytics_events", ["case_id"], unique=False)
    op.create_index("ix_analytics_events_created_at", "analytics_events", ["created_at"], unique=False)

    op.create_table(
        "risk_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["mentors.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_flags_case_id", "risk_flags", ["case_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_telegram_id", "audit_logs", ["actor_telegram_id"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_telegram_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_risk_flags_case_id", table_name="risk_flags")
    op.drop_table("risk_flags")

    op.drop_index("ix_analytics_events_created_at", table_name="analytics_events")
    op.drop_index("ix_analytics_events_case_id", table_name="analytics_events")
    op.drop_index("ix_analytics_events_actor_id_hash", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_name", table_name="analytics_events")
    op.drop_table("analytics_events")

    op.drop_index("ix_interventions_user_id", table_name="interventions")
    op.drop_table("interventions")

    op.drop_index("ix_wellbeing_checkins_user_id", table_name="wellbeing_checkins")
    op.drop_table("wellbeing_checkins")

    op.drop_index("ix_mentor_availability_mentor_user_id", table_name="mentor_availability")
    op.drop_table("mentor_availability")

    op.drop_index("ix_appointments_end_at", table_name="appointments")
    op.drop_index("ix_appointments_start_at", table_name="appointments")
    op.drop_index("ix_appointments_mentor_user_id", table_name="appointments")
    op.drop_index("ix_appointments_student_user_id", table_name="appointments")
    op.drop_table("appointments")

    op.drop_index("ix_case_messages_case_id", table_name="case_messages")
    op.drop_table("case_messages")

    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_assigned_mentor_id", table_name="cases")
    op.drop_index("ix_cases_student_user_id", table_name="cases")
    op.drop_table("cases")

    op.drop_table("mentor_roles")
    op.drop_table("mentors")
    op.drop_table("roles")

    op.drop_column("users", "crisis_consent_at")
    op.drop_column("users", "analytics_consent")
    op.drop_column("users", "study_year")
    op.drop_column("users", "faculty")
    op.drop_column("users", "locale")
