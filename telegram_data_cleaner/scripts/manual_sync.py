#!/usr/bin/env python3
"""
Manual sync script for triggering data ingestion.

Usage:
    python scripts/manual_sync.py [options]

Examples:
    # Sync single batch (default: 100 messages)
    python scripts/manual_sync.py

    # Sync with custom limit
    python scripts/manual_sync.py --limit 500

    # Sync all available messages
    python scripts/manual_sync.py --all

    # Sync without cache
    python scripts/manual_sync.py --no-cache

    # Sync with specific offset
    python scripts/manual_sync.py --offset 1000 --limit 100
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import redis.asyncio as aioredis

from src.config import settings
from src.core.logging import setup_logging, get_logger
from src.database import DatabaseManager
from src.services.ingestion_service import IngestionService
from src.core.exceptions import APIError, DatabaseOperationError

setup_logging()
logger = get_logger(__name__)


async def sync_batch(
    limit: int = 100,
    offset: int = None,
    use_cache: bool = True,
    update_existing: bool = True,
) -> None:
    """
    Sync a single batch of messages.

    Args:
        limit: Number of messages to fetch
        offset: Pagination offset
        use_cache: Whether to use Redis cache
        update_existing: Whether to update existing messages
    """
    logger.info("="*60)
    logger.info("Starting Manual Sync - Single Batch")
    logger.info("="*60)
    logger.info(f"Limit: {limit}")
    logger.info(f"Offset: {offset}")
    logger.info(f"Use Cache: {use_cache}")
    logger.info(f"Update Existing: {update_existing}")
    logger.info("")

    # Initialize database
    db_manager = DatabaseManager()
    db_manager.init_engine()

    # Initialize Redis (optional)
    redis_client = None
    if use_cache:
        try:
            redis_client = aioredis.from_url(
                settings.redis_url_str,
                decode_responses=False,
            )
            await redis_client.ping()
            logger.info("✓ Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Continuing without cache.")
            redis_client = None

    try:
        # Get database session
        async with db_manager.session() as session:
            # Create ingestion service
            ingestion_service = IngestionService(
                session=session,
                redis_client=redis_client,
                normalize_text=True,
            )

            # Run ingestion
            start_time = datetime.now()
            logger.info("Starting ingestion...")

            stats = await ingestion_service.ingest_batch(
                limit=limit,
                offset=offset,
                use_cache=use_cache,
                update_existing=update_existing,
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Print results
            logger.info("")
            logger.info("="*60)
            logger.info("Sync Complete!")
            logger.info("="*60)
            logger.info(f"Messages Processed: {stats.messages_processed}")
            logger.info(f"Messages Inserted:  {stats.messages_inserted}")
            logger.info(f"Messages Updated:   {stats.messages_updated}")
            logger.info(f"Messages Skipped:   {stats.messages_skipped}")
            logger.info(f"Channels Processed: {stats.channels_processed}")
            logger.info(f"Errors:             {stats.errors}")
            logger.info(f"Duration:           {duration:.2f}s")
            logger.info("="*60)

            if stats.errors > 0:
                sys.exit(1)

    except APIError as e:
        logger.error(f"❌ API error: {e}")
        sys.exit(1)

    except DatabaseOperationError as e:
        logger.error(f"❌ Database error: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        if redis_client:
            await redis_client.aclose()
        await db_manager.close()


async def sync_all(
    batch_size: int = 100,
    max_messages: int = None,
    use_cache: bool = True,
) -> None:
    """
    Sync all available messages using pagination.

    Args:
        batch_size: Messages per batch
        max_messages: Maximum total messages (None = all)
        use_cache: Whether to use Redis cache
    """
    logger.info("="*60)
    logger.info("Starting Manual Sync - Full Sync")
    logger.info("="*60)
    logger.info(f"Batch Size: {batch_size}")
    logger.info(f"Max Messages: {max_messages or 'All'}")
    logger.info(f"Use Cache: {use_cache}")
    logger.info("")

    # Initialize database
    db_manager = DatabaseManager()
    db_manager.init_engine()

    # Initialize Redis (optional)
    redis_client = None
    if use_cache:
        try:
            redis_client = aioredis.from_url(
                settings.redis_url_str,
                decode_responses=False,
            )
            await redis_client.ping()
            logger.info("✓ Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Continuing without cache.")
            redis_client = None

    try:
        # Get database session
        async with db_manager.session() as session:
            # Create ingestion service
            ingestion_service = IngestionService(
                session=session,
                redis_client=redis_client,
                normalize_text=True,
            )

            # Run full ingestion
            start_time = datetime.now()
            logger.info("Starting full ingestion...")

            stats = await ingestion_service.ingest_all(
                batch_size=batch_size,
                max_messages=max_messages,
                use_cache=use_cache,
                update_existing=True,
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Print results
            logger.info("")
            logger.info("="*60)
            logger.info("Full Sync Complete!")
            logger.info("="*60)
            logger.info(f"Messages Processed: {stats.messages_processed}")
            logger.info(f"Messages Inserted:  {stats.messages_inserted}")
            logger.info(f"Messages Updated:   {stats.messages_updated}")
            logger.info(f"Messages Skipped:   {stats.messages_skipped}")
            logger.info(f"Channels Processed: {stats.channels_processed}")
            logger.info(f"Errors:             {stats.errors}")
            logger.info(f"Duration:           {duration:.2f}s")
            logger.info(f"Avg Speed:          {stats.messages_processed/duration:.1f} msg/s")
            logger.info("="*60)

            if stats.errors > 0:
                sys.exit(1)

    except APIError as e:
        logger.error(f"❌ API error: {e}")
        sys.exit(1)

    except DatabaseOperationError as e:
        logger.error(f"❌ Database error: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        if redis_client:
            await redis_client.aclose()
        await db_manager.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Manual sync script for Telegram data ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync single batch (100 messages)
  python scripts/manual_sync.py

  # Sync with custom limit
  python scripts/manual_sync.py --limit 500

  # Sync all available messages
  python scripts/manual_sync.py --all

  # Sync without cache
  python scripts/manual_sync.py --no-cache

  # Sync with specific offset
  python scripts/manual_sync.py --offset 1000 --limit 100

  # Full sync with batch size
  python scripts/manual_sync.py --all --batch-size 200
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of messages to fetch (default: 100)"
    )

    parser.add_argument(
        "--offset",
        type=int,
        default=None,
        help="Pagination offset (default: None)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync all available messages (pagination)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for full sync (default: 100)"
    )

    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Maximum messages for full sync (default: all)"
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable Redis cache"
    )

    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Don't update existing messages"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.all and args.offset is not None:
        logger.error("Error: --all and --offset cannot be used together")
        sys.exit(1)

    # Run sync
    if args.all:
        asyncio.run(sync_all(
            batch_size=args.batch_size,
            max_messages=args.max_messages,
            use_cache=not args.no_cache,
        ))
    else:
        asyncio.run(sync_batch(
            limit=args.limit,
            offset=args.offset,
            use_cache=not args.no_cache,
            update_existing=not args.no_update,
        ))


if __name__ == "__main__":
    main()
