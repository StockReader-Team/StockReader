"""
Tests for database connection and session management.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from src.database import db_manager


@pytest.mark.asyncio
async def test_engine_initialization(engine: AsyncEngine) -> None:
    """
    Test that database engine can be initialized.

    Args:
        engine: Test database engine fixture
    """
    assert engine is not None
    assert not engine.pool._is_disposed


@pytest.mark.asyncio
async def test_session_creation(session: AsyncSession) -> None:
    """
    Test that database session can be created.

    Args:
        session: Test database session fixture
    """
    assert session is not None
    assert not session.is_active or session.in_transaction()


@pytest.mark.asyncio
async def test_database_connection(session: AsyncSession) -> None:
    """
    Test basic database connectivity.

    Args:
        session: Test database session fixture
    """
    result = await session.execute(text("SELECT 1"))
    value = result.scalar()
    assert value == 1


@pytest.mark.asyncio
async def test_session_commit(session: AsyncSession) -> None:
    """
    Test that session can commit transactions.

    Args:
        session: Test database session fixture
    """
    # Execute a simple query
    await session.execute(text("SELECT 1"))

    # Commit should not raise an error
    await session.commit()


@pytest.mark.asyncio
async def test_session_rollback(session: AsyncSession) -> None:
    """
    Test that session can rollback transactions.

    Args:
        session: Test database session fixture
    """
    # Start a transaction
    await session.execute(text("SELECT 1"))

    # Rollback should not raise an error
    await session.rollback()


@pytest.mark.asyncio
async def test_database_manager_health_check() -> None:
    """
    Test database manager health check functionality.
    """
    # Initialize database manager
    db_manager.init_engine()

    try:
        # Health check should return True
        is_healthy = await db_manager.health_check()
        assert is_healthy is True
    finally:
        # Clean up
        await db_manager.close()


@pytest.mark.asyncio
async def test_database_manager_session_context() -> None:
    """
    Test database manager session context manager.
    """
    # Initialize database manager
    db_manager.init_engine()

    try:
        # Create session using context manager
        async with db_manager.session() as test_session:
            result = await test_session.execute(text("SELECT 1"))
            value = result.scalar()
            assert value == 1
    finally:
        # Clean up
        await db_manager.close()


@pytest.mark.asyncio
async def test_database_manager_session_error_handling() -> None:
    """
    Test database manager session error handling and rollback.
    """
    # Initialize database manager
    db_manager.init_engine()

    try:
        # Test that errors trigger rollback
        with pytest.raises(Exception):
            async with db_manager.session() as test_session:
                await test_session.execute(text("SELECT 1"))
                # Raise an error to test rollback
                raise ValueError("Test error")
    finally:
        # Clean up
        await db_manager.close()
