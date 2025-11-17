"""
Pytest configuration and fixtures for testing.
"""
import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.models import Base
from src.config import settings


# Test database URL (use a separate test database)
TEST_DATABASE_URL = "postgresql+asyncpg://telegram_user:telegram_pass@localhost:5432/telegram_data_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.

    Yields:
        asyncio.AbstractEventLoop: Event loop for async tests
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create a test database engine.

    Yields:
        AsyncEngine: SQLAlchemy async engine for testing
    """
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )

    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a test database session.

    Args:
        engine: Test database engine

    Yields:
        AsyncSession: Database session for testing
    """
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_factory() as test_session:
        yield test_session
        await test_session.rollback()


@pytest.fixture(scope="session")
def test_settings() -> settings:
    """
    Get test settings.

    Returns:
        Settings: Application settings for testing
    """
    return settings
