from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .config import get_settings

settings = get_settings()

# 동기 엔진 (기존 코드 호환용)
engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 비동기 엔진
async_database_url = settings.database_url.replace('postgresql://', 'postgresql+asyncpg://')
async_engine = create_async_engine(
    async_database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
)
async_session_maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """동기 DB 세션 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """비동기 DB 세션 의존성."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
