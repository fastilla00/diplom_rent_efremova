# EcomProfit Guard — database
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Зависимость FastAPI: выдаёт async-сессию SQLAlchemy, коммит при успехе, откат при ошибке."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _migrate_costs_columns(conn):
    """Добавить новые колонки в costs, если их ещё нет (SQLite)."""
    if "sqlite" not in str(settings.database_url):
        return
    from sqlalchemy import text
    try:
        result = await conn.execute(text("PRAGMA table_info(costs)"))
        rows = result.fetchall()
    except Exception:
        return
    existing = {row[1] for row in rows} if rows else set()
    new_columns = [
        ("cost_center", "VARCHAR(255)"),
        ("sheet_project", "VARCHAR(255)"),
        ("specialist", "VARCHAR(255)"),
        ("payment_amount", "NUMERIC(14,2)"),
        ("payment_date", "DATE"),
        ("payment_status", "VARCHAR(64)"),
        ("cost_month", "VARCHAR(32)"),
        ("debt", "VARCHAR(64)"),
    ]
    for col, typ in new_columns:
        if col not in existing:
            try:
                await conn.execute(text(f"ALTER TABLE costs ADD COLUMN {col} {typ}"))
            except Exception:
                pass


async def _migrate_acts_columns(conn):
    """Добавить новые колонки в acts, если их ещё нет (SQLite)."""
    if "sqlite" not in str(settings.database_url):
        return
    from sqlalchemy import text
    try:
        result = await conn.execute(text("PRAGMA table_info(acts)"))
        rows = result.fetchall()
    except Exception:
        return
    existing = {row[1] for row in rows} if rows else set()
    if "shipment_date" not in existing:
        try:
            await conn.execute(text("ALTER TABLE acts ADD COLUMN shipment_date DATE"))
        except Exception:
            pass


async def init_db() -> None:
    """Создаёт таблицы по моделям и применяет лёгкие миграции SQLite для новых колонок."""
    from app import models  # noqa: F401 — register models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_costs_columns(conn)
        await _migrate_acts_columns(conn)
