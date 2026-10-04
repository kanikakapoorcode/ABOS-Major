"""
Async SQLAlchemy session factory and database initialization.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.APP_DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Init ──────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """
    Called at app startup.
    In production, use Alembic migrations instead of create_all.
    create_all here is a safety net for development / first run.
    """
    from backend.db.models import user, goal, workflow, execution, agent_profile, feedback  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
