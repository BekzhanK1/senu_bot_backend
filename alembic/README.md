# Alembic migrations

Используйте **синхронный** DSN PostgreSQL (без `+asyncpg`):

```bash
export DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/DBNAME
cd senu_bot_backend
alembic upgrade head
```

Переменная `DB_URL` с `postgresql+asyncpg://` также поддерживается: `env.py` заменит драйвер на `postgresql://`.
