"""
Database connection and session management with async support.
"""
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import event, text

from src.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions with async support.

    Attributes:
        engine: SQLAlchemy async engine
        session_factory: Session maker for creating new sessions
    """

    def __init__(self) -> None:
        """Initialize database manager with engine and session factory."""
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    def init_engine(self) -> None:
        """
        Initialize database engine with connection pooling.

        Creates async engine with configured pool size and settings.
        """
        if self.engine is not None:
            logger.warning("Engine already initialized")
            return

        # Create async engine
        self.engine = create_async_engine(
            settings.database_url_str,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            echo=settings.log_level == "DEBUG",  # Log SQL in debug mode
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        logger.info("Database engine initialized successfully")

    async def close(self) -> None:
        """
        Close database engine and clean up connections.

        Should be called on application shutdown.
        """
        if self.engine is not None:
            await self.engine.dispose()
            logger.info("Database engine closed")
            self.engine = None
            self.session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Create a new database session with automatic cleanup.

        Usage:
            async with db_manager.session() as session:
                result = await session.execute(query)

        Yields:
            AsyncSession: Database session

        Raises:
            RuntimeError: If engine not initialized
        """
        if self.session_factory is None:
            raise RuntimeError("Database engine not initialized. Call init_engine() first.")

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            bool: True if database is accessible, False otherwise
        """
        if self.engine is None:
            return False

        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.

    Usage in FastAPI:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Database session
    """
    async with db_manager.session() as session:
        yield session


async def init_db() -> None:
    """
    Initialize database connection on application startup.

    Should be called in FastAPI lifespan context.
    """
    db_manager.init_engine()

    # Test connection
    if await db_manager.health_check():
        logger.info("Database connection established successfully")
    else:
        logger.error("Failed to establish database connection")
        raise RuntimeError("Database connection failed")


async def close_db() -> None:
    """
    Close database connection on application shutdown.

    Should be called in FastAPI lifespan context.
    """
    await db_manager.close()
