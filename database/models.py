from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(32))
    full_name: Mapped[str] = mapped_column(String(128))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

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
