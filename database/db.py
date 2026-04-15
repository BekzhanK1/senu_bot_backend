import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, update, func
from database.models import Base, User, Request, Tip

DB_URL = "sqlite+aiosqlite:///senu_bot.db"

engine = create_async_engine(DB_URL, echo=False)
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
                Tip(text="Попробуй технику 'Помидоро' для концентрации.", category="Productivity")
            ]
            session.add_all(tips)
            await session.commit()

async def add_user(telegram_id: int, username: str, full_name: str):
    async with async_session() as session:
        user = await session.get(User, telegram_id)
        if not user:
            new_user = User(telegram_id=telegram_id, username=username, full_name=full_name)
            session.add(new_user)
            await session.commit()

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
