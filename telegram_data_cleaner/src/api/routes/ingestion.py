"""
API routes for ingestion management.
"""
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import db_manager
from src.services.ingestion_service import IngestionService
from src.schemas.ingestion import IngestionStatsSchema, SyncStatusSchema
from src.core.logging import get_logger
from src.core.exceptions import APIError, DatabaseOperationError

logger = get_logger(__name__)

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


async def get_db_session() -> AsyncSession:
    """
    Dependency for database session.

    Yields:
        Database session
    """
    async with db_manager.session() as session:
        yield session


async def get_ingestion_service(
    session: AsyncSession = Depends(get_db_session)
) -> IngestionService:
    """
    Dependency for ingestion service.

    Args:
        session: Database session

    Returns:
        Ingestion service instance
    """
    # TODO: Initialize Redis client from app state
    return IngestionService(session=session, redis_client=None)


@router.post("/sync", response_model=IngestionStatsSchema, status_code=200)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=100, ge=1, le=1000, description="Messages to fetch"),
    offset: Optional[int] = Query(default=None, ge=0, description="Pagination offset"),
    use_cache: bool = Query(default=True, description="Use Redis cache"),
    update_existing: bool = Query(default=True, description="Update existing messages"),
    background: bool = Query(default=False, description="Run in background"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> IngestionStatsSchema:
    """
    Trigger manual synchronization.

    Fetches messages from API and stores them in database.

    Args:
        background_tasks: FastAPI background tasks
        limit: Number of messages to fetch
        offset: Pagination offset
        use_cache: Whether to use cache
        update_existing: Whether to update existing messages
        background: Run in background (returns immediately)
        ingestion_service: Ingestion service

    Returns:
        Ingestion statistics

    Raises:
        HTTPException: If ingestion fails
    """
    logger.info(
        f"Manual sync triggered: limit={limit}, offset={offset}, background={background}"
    )

    if background:
        # Run in background
        background_tasks.add_task(
            ingestion_service.ingest_batch,
            limit=limit,
            offset=offset,
            use_cache=use_cache,
            update_existing=update_existing,
        )
        return IngestionStatsSchema(
            messages_processed=0,
            messages_inserted=0,
            messages_updated=0,
            messages_skipped=0,
            channels_processed=0,
            errors=0,
            duration_seconds=0,
        )
    else:
        # Run synchronously
        try:
            stats = await ingestion_service.ingest_batch(
                limit=limit,
                offset=offset,
                use_cache=use_cache,
                update_existing=update_existing,
            )
            return stats

        except APIError as e:
            logger.error(f"API error during sync: {e}")
            raise HTTPException(status_code=502, detail=str(e)) from e

        except DatabaseOperationError as e:
            logger.error(f"Database error during sync: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

        except Exception as e:
            logger.error(f"Unexpected error during sync: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/sync-all", response_model=IngestionStatsSchema, status_code=200)
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(default=100, ge=10, le=1000, description="Batch size"),
    max_messages: Optional[int] = Query(
        default=None, ge=1, description="Maximum messages to fetch"
    ),
    background: bool = Query(default=True, description="Run in background"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> IngestionStatsSchema:
    """
    Trigger full synchronization (all messages).

    Fetches all available messages using pagination.

    Args:
        background_tasks: FastAPI background tasks
        batch_size: Messages per batch
        max_messages: Maximum total messages
        background: Run in background
        ingestion_service: Ingestion service

    Returns:
        Ingestion statistics (empty if background)

    Raises:
        HTTPException: If ingestion fails
    """
    logger.info(
        f"Full sync triggered: batch_size={batch_size}, "
        f"max_messages={max_messages}, background={background}"
    )

    if background:
        # Run in background
        background_tasks.add_task(
            ingestion_service.ingest_all,
            batch_size=batch_size,
            max_messages=max_messages,
        )
        return IngestionStatsSchema()
    else:
        # Run synchronously (not recommended for large datasets)
        try:
            stats = await ingestion_service.ingest_all(
                batch_size=batch_size,
                max_messages=max_messages,
            )
            return stats

        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/cleanup", status_code=200)
async def trigger_cleanup(
    days: Optional[int] = Query(default=None, ge=1, description="Days to keep"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> Dict[str, Any]:
    """
    Trigger manual cleanup of old messages.

    Args:
        days: Number of days to keep (default: from config)
        ingestion_service: Ingestion service

    Returns:
        Cleanup result

    Raises:
        HTTPException: If cleanup fails
    """
    logger.info(f"Manual cleanup triggered: days={days}")

    try:
        deleted_count = await ingestion_service.cleanup_old_messages(days=days)

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "days_kept": days or "default",
        }

    except DatabaseOperationError as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    except Exception as e:
        logger.error(f"Unexpected error during cleanup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/stats", response_model=Dict[str, Any], status_code=200)
async def get_ingestion_stats(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> Dict[str, Any]:
    """
    Get ingestion statistics.

    Args:
        ingestion_service: Ingestion service

    Returns:
        Statistics dictionary

    Raises:
        HTTPException: If stats retrieval fails
    """
    try:
        stats = await ingestion_service.get_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health", response_model=Dict[str, bool], status_code=200)
async def health_check(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> Dict[str, bool]:
    """
    Check health of ingestion components.

    Args:
        ingestion_service: Ingestion service

    Returns:
        Health status for each component

    Raises:
        HTTPException: If health check fails
    """
    try:
        health = await ingestion_service.health_check()
        return health

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/cache/clear", status_code=200)
async def clear_cache(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> Dict[str, str]:
    """
    Clear all caches.

    Args:
        ingestion_service: Ingestion service

    Returns:
        Success message
    """
    try:
        ingestion_service.clear_cache()
        return {"status": "success", "message": "All caches cleared"}

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/channels", status_code=200)
async def get_channels(
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Get all channels.

    Args:
        session: Database session

    Returns:
        List of channels
    """
    from sqlalchemy import select
    from src.models.channel import Channel

    try:
        result = await session.execute(
            select(Channel).where(Channel.is_active == True).order_by(Channel.name)
        )
        channels = result.scalars().all()

        return {
            "channels": [
                {
                    "id": str(channel.id),
                    "name": channel.name,
                    "username": channel.username,
                    "is_active": channel.is_active,
                }
                for channel in channels
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get channels: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
