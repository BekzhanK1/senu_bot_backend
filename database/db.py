import os
from urllib.parse import quote_plus

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import database.models_v2  # noqa: F401 — analytics_events + optional v2 tables
from database.models import Base, BlockedUser, MentorEvent, Request, Tip, User


def _normalize_async_db_url(url: str) -> str:
    """
    create_async_engine requires an async driver. Plain postgresql:// makes SQLAlchemy
    use psycopg2 (sync), which is not installed — we use asyncpg instead.
    """
    url = url.strip()
    if not url:
        return url
    if url.startswith("sqlite"):
        if url.startswith("sqlite+aiosqlite://"):
            return url
        if url.startswith("sqlite://"):
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url
    scheme = url.split("://", 1)[0]
    if "+asyncpg" in scheme or "+aiosqlite" in scheme:
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


def _build_db_url() -> str:
    # 1) Direct URL has highest priority
    db_url = os.getenv("DB_URL")
    if db_url:
        return _normalize_async_db_url(db_url)

    # 2) Compose URL from individual Postgres fields in .env
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD", "")
    db_sslmode = os.getenv("DB_SSLMODE")

    if db_host or db_name or db_user:
        missing = [name for name, value in (
            ("DB_HOST", db_host),
            ("DB_NAME", db_name),
            ("DB_USER", db_user),
        ) if not value]
        if missing:
            raise RuntimeError(
                f"Missing required DB settings: {', '.join(missing)}. "
                "Set DB_URL or full DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD."
            )

        auth_part = quote_plus(db_user)
        if db_password:
            auth_part = f"{auth_part}:{quote_plus(db_password)}"

        url = f"postgresql+asyncpg://{auth_part}@{db_host}:{db_port}/{db_name}"
        if db_sslmode:
            url = f"{url}?sslmode={quote_plus(db_sslmode)}"
        return _normalize_async_db_url(url)

    # 3) Backward-compatible fallback for local quick start
    return _normalize_async_db_url("sqlite+aiosqlite:///senu_bot.db")


DB_URL = _build_db_url()

engine = create_async_engine(DB_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Добавим несколько советов, если их нет
    async with async_session() as session:
        result = await session.execute(select(Tip).limit(1))
        if not result.scalar_one_or_none():
            tips = [
                Tip(text="Не забывай делать перерывы каждые 45 минут учебы.", category="Academic"),
                Tip(text="Стакан воды с утра поможет проснуться быстрее, чем кофе.", category="Health"),
                Tip(text="Если задача кажется огромной, разбей ее на 5 маленьких шагов.", category="Productivity"),
                Tip(text="Твое ментальное здоровье важнее любой оценки.", category="Mental Health"),
                Tip(text="Попробуй технику 'Помидоро' для концентрации.", category="Productivity"),
            ]
            session.add_all(tips)
            await session.commit()

    from database.meetings_repo import ensure_schedule_row

    await ensure_schedule_row()


async def add_user(telegram_id: int, username: str, full_name: str):
    async with async_session() as session:
        user = await session.get(User, telegram_id)
        if not user:
            new_user = User(telegram_id=telegram_id, username=username, full_name=full_name)
            session.add(new_user)
            await session.commit()

async def get_user(telegram_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, telegram_id)

async def create_mentor_event(title: str, place: str, description: str) -> int:
    async with async_session() as session:
        event = MentorEvent(
            title=title[:256],
            place=place[:256],
            description=description,
        )
        session.add(event)
        await session.flush()
        event_id = event.id
        await session.commit()
        return event_id


async def create_request(user_id: int, request_type: str, content: str):
    async with async_session() as session:
        new_request = Request(user_id=user_id, request_type=request_type, content=content)
        session.add(new_request)
        await session.flush()
        request_id = new_request.id
        await session.commit()
        return request_id

async def resolve_request(request_id: int):
    async with async_session() as session:
        await session.execute(
            update(Request).where(Request.id == request_id).values(status="resolved")
        )
        await session.commit()

async def get_all_users_ids():
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        return [row[0] for row in result.all()]

async def get_pending_requests():
    async with async_session() as session:
        result = await session.execute(
            select(Request, User.full_name, User.username)
            .join(User)
            .where(Request.status == "pending")
            .order_by(Request.created_at.desc())
        )
        return result.all()

async def get_requests_for_admin(
    request_type: str | None = None,
    status: str | None = None,
    limit: int = 200,
):
    async with async_session() as session:
        query = (
            select(Request, User.full_name, User.username)
            .join(User)
            .order_by(Request.created_at.desc())
            .limit(limit)
        )
        if request_type:
            query = query.where(Request.request_type == request_type)
        if status:
            query = query.where(Request.status == status)
        result = await session.execute(query)
        return result.all()

async def get_request_by_id(req_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Request).where(Request.id == req_id)
        )
        return result.scalar_one_or_none()

async def get_random_tip():
    async with async_session() as session:
        result = await session.execute(select(Tip).order_by(func.random()).limit(1))
        return result.scalar_one_or_none()

async def get_user_requests(user_id: int, limit: int = 5):
    async with async_session() as session:
        result = await session.execute(
            select(Request)
            .where(Request.user_id == user_id)
            .order_by(Request.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def get_all_users(limit: int = 500):
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.joined_at.desc()).limit(limit)
        )
        return result.scalars().all()


async def is_user_blocked(telegram_id: int) -> bool:
    async with async_session() as session:
        blocked = await session.get(BlockedUser, telegram_id)
        return blocked is not None


async def block_user(telegram_id: int, reason: str | None = None):
    async with async_session() as session:
        blocked = await session.get(BlockedUser, telegram_id)
        if blocked:
            blocked.reason = reason
        else:
            session.add(BlockedUser(telegram_id=telegram_id, reason=reason))
        await session.commit()


async def unblock_user(telegram_id: int):
    async with async_session() as session:
        blocked = await session.get(BlockedUser, telegram_id)
        if blocked:
            await session.delete(blocked)
            await session.commit()


async def get_blocked_user_ids() -> set[int]:
    async with async_session() as session:
        result = await session.execute(select(BlockedUser.telegram_id))
        return {row[0] for row in result.all()}
