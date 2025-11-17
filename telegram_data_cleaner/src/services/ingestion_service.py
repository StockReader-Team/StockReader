"""
Ingestion service for fetching and storing Telegram messages.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import redis.asyncio as aioredis
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.logging import get_logger
from src.core.exceptions import (
    APIError,
    DatabaseOperationError,
    CacheConnectionError,
)
from src.core.ingestion.api_client import TelegramAPIClient
from src.core.ingestion.data_mapper import DataMapper
from src.core.processing.text_normalizer import TextNormalizer
from src.core.matching.matching_service import MatchingService
from src.schemas.ingestion import IngestionStatsSchema
from src.models.message import Message
from src.models.channel import Channel
from src.database import DatabaseManager

logger = get_logger(__name__)


class IngestionService:
    """
    Service for ingesting Telegram messages from API to database.

    Orchestrates:
    - API client for fetching data
    - Data mapper for conversion
    - Text normalizer for processing
    - Database operations
    - Cache management
    - Statistics tracking
    """

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Optional[aioredis.Redis] = None,
        normalize_text: bool = True,
        enable_matching: bool = True,
    ):
        """
        Initialize ingestion service.

        Args:
            session: SQLAlchemy async session
            redis_client: Redis client for caching (optional)
            normalize_text: Whether to normalize text (default: True)
            enable_matching: Whether to enable dictionary matching (default: True)
        """
        self.session = session
        self.redis_client = redis_client
        self.normalize_text_flag = normalize_text
        self.enable_matching_flag = enable_matching

        # Initialize components
        self.data_mapper = DataMapper(session)
        self.text_normalizer = TextNormalizer() if normalize_text else None
        self.matching_service = MatchingService(session) if enable_matching else None

        logger.info(
            f"IngestionService initialized "
            f"(normalize_text={normalize_text}, "
            f"matching={enable_matching}, "
            f"redis={'enabled' if redis_client else 'disabled'})"
        )

    async def _normalize_messages(
        self, messages: list[Message]
    ) -> int:
        """
        Normalize text for a list of messages.

        Args:
            messages: List of Message models

        Returns:
            Number of messages normalized
        """
        if not self.text_normalizer or not self.normalize_text_flag:
            return 0

        normalized_count = 0

        for message in messages:
            if message.text and not message.text_normalized:
                try:
                    message.text_normalized = self.text_normalizer.normalize(
                        message.text
                    )
                    normalized_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to normalize message {message.id}: {e}"
                    )

        return normalized_count

    async def _match_messages(
        self, messages: list[Message]
    ) -> int:
        """
        Match dictionary words in messages.

        Args:
            messages: List of Message models with normalized text

        Returns:
            Total number of word matches found
        """
        if not self.matching_service or not self.enable_matching_flag:
            return 0

        try:
            # Ensure cache is loaded
            await self.matching_service.load_cache()

            # Batch match messages
            results = await self.matching_service.match_messages_batch(
                messages,
                save_matches=True
            )

            # Count total matches
            total_matches = sum(len(word_ids) for word_ids in results.values())

            logger.info(f"Matched {total_matches} dictionary words across {len(messages)} messages")

            return total_matches

        except Exception as e:
            logger.error(f"Failed to match messages: {e}")
            return 0

    async def ingest_batch(
        self,
        limit: int = 100,
        offset: Optional[int] = None,
        use_cache: bool = True,
        update_existing: bool = True,
    ) -> IngestionStatsSchema:
        """
        Ingest a single batch of messages.

        Args:
            limit: Number of messages to fetch
            offset: Offset for pagination
            use_cache: Whether to use cache
            update_existing: Whether to update existing messages

        Returns:
            Ingestion statistics

        Raises:
            APIError: If API fetch fails
            DatabaseOperationError: If database operation fails
        """
        start_time = datetime.now()
        stats = IngestionStatsSchema()

        logger.info(f"Starting batch ingestion (limit={limit}, offset={offset})")

        try:
            # Fetch messages from API
            async with TelegramAPIClient(
                redis_client=self.redis_client,
                cache_ttl=settings.redis_cache_ttl,
            ) as api_client:
                response = await api_client.fetch_messages(
                    limit=limit,
                    offset=offset,
                    use_cache=use_cache,
                )

            logger.info(f"Fetched {len(response.messages)} messages from API")

            # Process messages
            if response.messages:
                # Upsert messages
                upsert_stats = await self.data_mapper.bulk_upsert_messages(
                    response.messages,
                    update_existing=update_existing,
                )

                stats.messages_processed = len(response.messages)
                stats.messages_inserted = upsert_stats["inserted"]
                stats.messages_updated = upsert_stats["updated"]
                stats.messages_skipped = upsert_stats["skipped"]
                stats.errors = upsert_stats["failed"]

                # Get unique channels
                channel_ids = set()
                for msg in response.messages:
                    telegram_id = str(msg.channel.id)
                    if telegram_id in self.data_mapper._channel_cache:
                        channel_ids.add(telegram_id)

                stats.channels_processed = len(channel_ids)
                # Channels inserted/updated are tracked by DataMapper internally

                # Normalize text for new messages
                if self.normalize_text_flag:
                    # Get messages that need normalization
                    result = await self.session.execute(
                        select(Message).where(
                            Message.text.isnot(None),
                            Message.text_normalized.is_(None)
                        ).limit(limit)
                    )
                    messages_to_normalize = list(result.scalars().all())

                    if messages_to_normalize:
                        normalized_count = await self._normalize_messages(
                            messages_to_normalize
                        )
                        await self.session.commit()
                        logger.info(f"Normalized {normalized_count} messages")

                        # Match dictionary words in normalized messages
                        if self.enable_matching_flag and messages_to_normalize:
                            await self._match_messages(messages_to_normalize)

            # Calculate duration
            stats.duration_seconds = (
                datetime.now() - start_time
            ).total_seconds()

            logger.info(
                f"Batch ingestion complete: "
                f"{stats.messages_inserted} inserted, "
                f"{stats.messages_updated} updated, "
                f"{stats.messages_skipped} skipped, "
                f"{stats.errors} errors "
                f"in {stats.duration_seconds:.2f}s"
            )

            return stats

        except APIError as e:
            logger.error(f"API error during ingestion: {e}")
            stats.errors += 1
            stats.duration_seconds = (
                datetime.now() - start_time
            ).total_seconds()
            raise

        except Exception as e:
            logger.error(f"Ingestion batch failed: {e}")
            stats.errors += 1
            stats.duration_seconds = (
                datetime.now() - start_time
            ).total_seconds()
            await self.session.rollback()
            raise DatabaseOperationError(
                operation="ingest_batch",
                reason=str(e)
            ) from e

    async def ingest_all(
        self,
        batch_size: int = 100,
        max_messages: Optional[int] = None,
        use_cache: bool = True,
        update_existing: bool = True,
    ) -> IngestionStatsSchema:
        """
        Ingest all available messages using pagination.

        Args:
            batch_size: Messages per batch
            max_messages: Maximum total messages (None = all)
            use_cache: Whether to use cache
            update_existing: Whether to update existing messages

        Returns:
            Combined ingestion statistics
        """
        start_time = datetime.now()
        total_stats = IngestionStatsSchema()

        logger.info(
            f"Starting full ingestion "
            f"(batch_size={batch_size}, max={max_messages or 'all'})"
        )

        offset = 0
        batch_number = 1

        while True:
            # Check if we've reached the limit
            if max_messages and total_stats.messages_processed >= max_messages:
                logger.info(f"Reached max messages limit: {max_messages}")
                break

            # Ingest batch
            logger.info(f"Processing batch {batch_number}...")
            batch_stats = await self.ingest_batch(
                limit=batch_size,
                offset=offset,
                use_cache=use_cache,
                update_existing=update_existing,
            )

            # Accumulate stats
            total_stats.messages_processed += batch_stats.messages_processed
            total_stats.messages_inserted += batch_stats.messages_inserted
            total_stats.messages_updated += batch_stats.messages_updated
            total_stats.messages_skipped += batch_stats.messages_skipped
            total_stats.channels_processed += batch_stats.channels_processed
            total_stats.errors += batch_stats.errors

            # Check if we should continue
            if batch_stats.messages_processed < batch_size:
                logger.info("Reached end of available messages")
                break

            offset += batch_size
            batch_number += 1

            # Small delay between batches to avoid overwhelming the API
            await asyncio.sleep(1)

        # Calculate total duration
        total_stats.duration_seconds = (
            datetime.now() - start_time
        ).total_seconds()

        logger.info(
            f"Full ingestion complete: "
            f"{total_stats.messages_inserted} inserted, "
            f"{total_stats.messages_updated} updated, "
            f"{total_stats.messages_skipped} skipped, "
            f"{batch_number} batches, "
            f"{total_stats.errors} errors "
            f"in {total_stats.duration_seconds:.2f}s"
        )

        return total_stats

    async def cleanup_old_messages(
        self, days: Optional[int] = None
    ) -> int:
        """
        Delete messages older than specified days.

        Args:
            days: Number of days to keep (default: settings.history_days)

        Returns:
            Number of messages deleted
        """
        days = days or settings.history_days
        cutoff_date = datetime.now() - timedelta(days=days)

        logger.info(f"Cleaning up messages older than {days} days ({cutoff_date})")

        try:
            # Count messages to delete
            result = await self.session.execute(
                select(func.count(Message.id)).where(Message.date < cutoff_date)
            )
            count_to_delete = result.scalar_one()

            if count_to_delete == 0:
                logger.info("No old messages to delete")
                return 0

            # Delete old messages
            result = await self.session.execute(
                delete(Message).where(Message.date < cutoff_date)
            )
            await self.session.commit()

            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} old messages")

            return deleted_count

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            await self.session.rollback()
            raise DatabaseOperationError(
                operation="cleanup_old_messages",
                reason=str(e)
            ) from e

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get ingestion statistics.

        Returns:
            Dict with statistics
        """
        try:
            # Count total messages
            result = await self.session.execute(
                select(func.count(Message.id))
            )
            total_messages = result.scalar_one()

            # Count total channels
            result = await self.session.execute(
                select(func.count(Channel.id))
            )
            total_channels = result.scalar_one()

            # Count active channels
            result = await self.session.execute(
                select(func.count(Channel.id)).where(Channel.is_active == True)
            )
            active_channels = result.scalar_one()

            # Get date range
            result = await self.session.execute(
                select(func.min(Message.date), func.max(Message.date))
            )
            min_date, max_date = result.one()

            # Messages in last 24 hours
            yesterday = datetime.now() - timedelta(hours=24)
            result = await self.session.execute(
                select(func.count(Message.id)).where(Message.date >= yesterday)
            )
            messages_last_24h = result.scalar_one()

            stats_dict = {
                "total_messages": total_messages,
                "total_channels": total_channels,
                "active_channels": active_channels,
                "messages_last_24h": messages_last_24h,
                "oldest_message": min_date.isoformat() if min_date else None,
                "newest_message": max_date.isoformat() if max_date else None,
                "text_normalizer_available": (
                    self.text_normalizer.is_hazm_available()
                    if self.text_normalizer
                    else False
                ),
            }

            # Add matching statistics if enabled
            if self.matching_service:
                matching_stats = await self.matching_service.get_stats()
                stats_dict["matching"] = matching_stats

            return stats_dict

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            raise DatabaseOperationError(
                operation="get_stats",
                reason=str(e)
            ) from e

    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all components.

        Returns:
            Dict with component health status
        """
        health = {
            "database": False,
            "api": False,
            "redis": False,
        }

        # Check database
        try:
            await self.session.execute(select(1))
            health["database"] = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")

        # Check API
        try:
            async with TelegramAPIClient(
                redis_client=self.redis_client
            ) as api_client:
                health["api"] = await api_client.health_check()
        except Exception as e:
            logger.error(f"API health check failed: {e}")

        # Check Redis
        if self.redis_client:
            try:
                await self.redis_client.ping()
                health["redis"] = True
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
        else:
            health["redis"] = None  # Not configured

        return health

    def clear_cache(self) -> None:
        """Clear all caches."""
        self.data_mapper.clear_cache()
        if self.matching_service:
            self.matching_service.clear_cache()
        logger.info("All caches cleared")
