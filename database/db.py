import os
from datetime import datetime
from urllib.parse import quote_plus

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import database.models_v2  # noqa: F401 — analytics_events + optional v2 tables
from database.models import AppSettings, Base, BlockedUser, DynamicContent, MenuButton, MentorEvent, Request, Tip, User
from database.models_v2 import Mentor, Role, mentor_roles


DEFAULT_APP_SETTINGS: dict[str, str] = {
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
}


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
    await ensure_app_settings_row()


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


def _merged_settings(payload: dict | None) -> dict[str, str]:
    merged = dict(DEFAULT_APP_SETTINGS)
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in merged and isinstance(value, str):
                merged[key] = value
    return merged


async def ensure_app_settings_row() -> None:
    async with async_session() as session:
        row = await session.get(AppSettings, 1)
        if row:
            return
        session.add(AppSettings(id=1, settings_json=dict(DEFAULT_APP_SETTINGS), updated_by=None))
        await session.commit()


async def get_app_settings() -> tuple[dict[str, str], int | None, datetime | None]:
    await ensure_app_settings_row()
    async with async_session() as session:
        row = await session.get(AppSettings, 1)
        if row is None:
            return dict(DEFAULT_APP_SETTINGS), None, None
        return _merged_settings(row.settings_json), row.updated_by, row.updated_at


async def update_app_settings(payload: dict[str, str], updated_by: int) -> tuple[dict[str, str], int | None, datetime | None]:
    await ensure_app_settings_row()
    async with async_session() as session:
        row = await session.get(AppSettings, 1)
        if row is None:
            row = AppSettings(id=1, settings_json=dict(DEFAULT_APP_SETTINGS), updated_by=updated_by)
            session.add(row)
        merged = _merged_settings(payload)
        row.settings_json = merged
        row.updated_by = updated_by
        await session.commit()
        await session.refresh(row)
        return merged, row.updated_by, row.updated_at


# ===== Dynamic Content Functions =====

async def get_dynamic_content_by_key(key: str) -> str | None:
    """Get dynamic content by key."""
    async with async_session() as session:
        result = await session.execute(
            select(DynamicContent).where(DynamicContent.key == key)
        )
        content = result.scalar_one_or_none()
        return content.content if content else None


async def get_all_dynamic_content(category: str | None = None):
    """Get all dynamic content, optionally filtered by category."""
    async with async_session() as session:
        query = select(DynamicContent).order_by(DynamicContent.category, DynamicContent.key)
        if category:
            query = query.where(DynamicContent.category == category)
        result = await session.execute(query)
        return result.scalars().all()


async def upsert_dynamic_content(
    key: str,
    content: str,
    content_type: str = "text",
    category: str = "general",
    description: str | None = None,
    updated_by: int | None = None,
) -> int:
    """Create or update dynamic content."""
    async with async_session() as session:
        result = await session.execute(
            select(DynamicContent).where(DynamicContent.key == key)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.content = content
            existing.content_type = content_type
            existing.category = category
            existing.description = description
            existing.updated_by = updated_by
            existing.updated_at = datetime.now()
            content_id = existing.id
        else:
            new_content = DynamicContent(
                key=key,
                content=content,
                content_type=content_type,
                category=category,
                description=description,
                updated_by=updated_by,
            )
            session.add(new_content)
            await session.flush()
            content_id = new_content.id
        
        await session.commit()
        return content_id


async def delete_dynamic_content(key: str) -> bool:
    """Delete dynamic content by key."""
    async with async_session() as session:
        result = await session.execute(
            select(DynamicContent).where(DynamicContent.key == key)
        )
        content = result.scalar_one_or_none()
        if content:
            await session.delete(content)
            await session.commit()
            return True
        return False


# ===== Menu Button Functions =====

async def get_all_menu_buttons() -> list[dict]:
    """Get all active menu buttons ordered by position."""
    async with async_session() as session:
        result = await session.execute(
            select(MenuButton)
            .where(MenuButton.is_active == True)
            .order_by(MenuButton.position)
        )
        buttons = result.scalars().all()
        return [
            {
                "id": btn.id,
                "text": btn.text,
                "action_type": btn.action_type,
                "action_value": btn.action_value,
                "position": btn.position,
                "icon": btn.icon,
                "required_role": btn.required_role,
            }
            for btn in buttons
        ]


async def create_menu_button(
    text: str,
    action_type: str,
    action_value: str,
    position: int = 0,
    icon: str | None = None,
    required_role: str | None = None,
) -> int:
    """Create a new menu button."""
    async with async_session() as session:
        button = MenuButton(
            text=text,
            action_type=action_type,
            action_value=action_value,
            position=position,
            icon=icon,
            required_role=required_role,
        )
        session.add(button)
        await session.flush()
        button_id = button.id
        await session.commit()
        return button_id


async def update_menu_button(
    button_id: int,
    text: str | None = None,
    action_type: str | None = None,
    action_value: str | None = None,
    position: int | None = None,
    icon: str | None = None,
    required_role: str | None = None,
    is_active: bool | None = None,
) -> bool:
    """Update a menu button."""
    async with async_session() as session:
        button = await session.get(MenuButton, button_id)
        if not button:
            return False
        
        if text is not None:
            button.text = text
        if action_type is not None:
            button.action_type = action_type
        if action_value is not None:
            button.action_value = action_value
        if position is not None:
            button.position = position
        if icon is not None:
            button.icon = icon
        if required_role is not None:
            button.required_role = required_role
        if is_active is not None:
            button.is_active = is_active
        
        await session.commit()
        return True


async def delete_menu_button(button_id: int) -> bool:
    """Delete a menu button."""
    async with async_session() as session:
        button = await session.get(MenuButton, button_id)
        if button:
            await session.delete(button)
            await session.commit()
            return True
        return False


# ===== Role and Permission Functions =====

async def get_user_roles(user_id: int) -> list[dict]:
    """Get all roles for a user."""
    async with async_session() as session:
        # Check if user is a mentor
        mentor = await session.get(Mentor, user_id)
        if not mentor:
            return []
        
        result = await session.execute(
            select(Role)
            .join(mentor_roles)
            .where(mentor_roles.c.mentor_user_id == user_id)
        )
        roles = result.scalars().all()
        return [
            {
                "id": role.id,
                "name": role.name,
                "permissions": role.permissions,
            }
            for role in roles
        ]


async def check_mentor_exists(user_id: int) -> bool:
    """Check if a user is a mentor."""
    async with async_session() as session:
        mentor = await session.get(Mentor, user_id)
        return mentor is not None


async def create_mentor(
    user_id: int,
    display_name: str,
    languages: str | None = None,
    skills: str | None = None,
) -> bool:
    """Create a mentor record."""
    async with async_session() as session:
        # Check if user exists
        user = await session.get(User, user_id)
        if not user:
            return False
        
        # Check if already a mentor
        existing = await session.get(Mentor, user_id)
        if existing:
            return False
        
        mentor = Mentor(
            user_id=user_id,
            display_name=display_name,
            languages=languages,
            skills=skills,
        )
        session.add(mentor)
        await session.commit()
        return True


async def assign_role_to_mentor(user_id: int, role_name: str) -> bool:
    """Assign a role to a mentor."""
    async with async_session() as session:
        # Check if mentor exists
        mentor = await session.get(Mentor, user_id)
        if not mentor:
            return False
        
        # Get or create role
        result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = result.scalar_one_or_none()
        
        if not role:
            role = Role(name=role_name)
            session.add(role)
            await session.flush()
        
        # Check if already assigned
        result = await session.execute(
            select(mentor_roles)
            .where(
                mentor_roles.c.mentor_user_id == user_id,
                mentor_roles.c.role_id == role.id
            )
        )
        if result.first():
            return True
        
        # Assign role
        await session.execute(
            mentor_roles.insert().values(
                mentor_user_id=user_id,
                role_id=role.id
            )
        )
        await session.commit()
        return True


async def remove_role_from_mentor(user_id: int, role_name: str) -> bool:
    """Remove a role from a mentor."""
    async with async_session() as session:
        result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = result.scalar_one_or_none()
        if not role:
            return False
        
        await session.execute(
            mentor_roles.delete().where(
                mentor_roles.c.mentor_user_id == user_id,
                mentor_roles.c.role_id == role.id
            )
        )
        await session.commit()
        return True


async def get_all_mentors(limit: int = 100):
    """Get all mentors."""
    async with async_session() as session:
        result = await session.execute(
            select(Mentor, User.full_name, User.username)
            .join(User, Mentor.user_id == User.telegram_id)
            .where(Mentor.is_active == True)
            .order_by(Mentor.created_at.desc())
            .limit(limit)
        )
        return result.all()


async def get_all_roles():
    """Get all roles."""
    async with async_session() as session:
        result = await session.execute(select(Role).order_by(Role.name))
        return result.scalars().all()
