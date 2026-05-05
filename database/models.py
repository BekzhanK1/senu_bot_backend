from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(32))
    full_name: Mapped[str] = mapped_column(String(128))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    # v2 profile / consent (nullable for backward compatibility)
    locale: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    faculty: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    study_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    analytics_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    crisis_consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    requests = relationship("Request", back_populates="user")

class Tip(Base):
    __tablename__ = "tips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    request_type: Mapped[str] = mapped_column(String(32))  # 'meeting', 'game_108', 'question', 'anonymous_question'
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # 'pending', 'resolved'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user = relationship("User", back_populates="requests")


class BlockedUser(Base):
    __tablename__ = "blocked_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class MentorEvent(Base):
    """Событие от ментора: рассылка всем студентам с названием, местом, описанием."""

    __tablename__ = "mentor_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    place: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class MentorScheduleSettings(Base):
    """Одна строка id=1: рабочие часы по дням недели и длина слота."""

    __tablename__ = "mentor_schedule_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # {"0": {"enabled": true, "start": "10:00", "end": "18:00"}, ... "6": ...}  Mon=0
    weekly_hours: Mapped[dict] = mapped_column("weekly_hours_json", JSON, default=dict)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Almaty")


class MeetingBooking(Base):
    """Реальная бронь слота: ожидает подтверждения → подтверждена → завершена."""

    __tablename__ = "meeting_bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending_confirm", index=True)
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("requests.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user = relationship("User", foreign_keys=[student_user_id])


class AppSettings(Base):
    """Single JSON row with editable app/bot copy and runtime settings."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class GroupPoll(Base):
    __tablename__ = "group_polls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    topics = relationship("PollTopic", back_populates="poll", cascade="all, delete-orphan")


class PollTopic(Base):
    __tablename__ = "poll_topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(Integer, ForeignKey("group_polls.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    suggested_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    poll = relationship("GroupPoll", back_populates="topics")
    votes = relationship("PollVote", back_populates="topic", cascade="all, delete-orphan")


class PollVote(Base):
    __tablename__ = "poll_votes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(Integer, ForeignKey("group_polls.id", ondelete="CASCADE"))
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("poll_topics.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    topic = relationship("PollTopic", back_populates="votes")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
