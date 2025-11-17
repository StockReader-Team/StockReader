#!/usr/bin/env python3
"""
Simple test for Phase 2 components.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logging import setup_logging, get_logger
from src.config import settings

setup_logging()
logger = get_logger(__name__)


async def test_api_client():
    """Test TelegramAPIClient."""
    logger.info("="*60)
    logger.info("Test 1: TelegramAPIClient")
    logger.info("="*60)

    try:
        from src.core.ingestion.api_client import TelegramAPIClient

        async with TelegramAPIClient() as client:
            # Test fetch_messages
            response = await client.fetch_messages(limit=5, use_cache=False)

            logger.info(f"✓ API Client works!")
            logger.info(f"  - Fetched {len(response.messages)} messages")
            logger.info(f"  - Total available: {response.total}")

            if response.messages:
                msg = response.messages[0]
                logger.info(f"  - First message: {msg.text[:50] if msg.text else 'No text'}...")
                logger.info(f"  - Channel: {msg.channel.name}")

        return True

    except Exception as e:
        logger.error(f"✗ API Client failed: {e}")
        return False


async def test_text_normalizer():
    """Test TextNormalizer."""
    logger.info("\n" + "="*60)
    logger.info("Test 2: TextNormalizer")
    logger.info("="*60)

    try:
        from src.core.processing.text_normalizer import TextNormalizer

        normalizer = TextNormalizer(use_hazm=False)  # Use fallback mode

        test_text = "سلام! این یک متن تست است. با ك و ي عربی."
        normalized = normalizer.normalize(test_text)
        stats = normalizer.get_stats(test_text)

        logger.info(f"✓ TextNormalizer works!")
        logger.info(f"  - Original: {test_text}")
        logger.info(f"  - Normalized: {normalized}")
        logger.info(f"  - Word count: {stats['word_count']}")
        logger.info(f"  - Hazm available: {normalizer.is_hazm_available()}")

        return True

    except Exception as e:
        logger.error(f"✗ TextNormalizer failed: {e}")
        return False


async def test_data_mapper():
    """Test DataMapper with sample data."""
    logger.info("\n" + "="*60)
    logger.info("Test 3: DataMapper")
    logger.info("="*60)

    try:
        from src.database import DatabaseManager
        from src.core.ingestion.data_mapper import DataMapper
        from src.schemas.ingestion import APIMessageSchema, APIChannelInfoSchema
        from datetime import datetime

        # Initialize database
        db_manager = DatabaseManager()
        db_manager.init_engine()

        async with db_manager.session() as session:
            mapper = DataMapper(session)

            # Create sample API message
            sample_message = APIMessageSchema(
                id=999999,
                message_id=123456,
                channel=APIChannelInfoSchema(
                    id=999,
                    name="Test Channel",
                    username="test_channel"
                ),
                text="این یک پیام تست است",
                date=datetime.now(),
                views_count=100,
                forwards_count=5,
            )

            # Test mapping
            message, is_new = await mapper.upsert_message(sample_message)
            await session.commit()

            logger.info(f"✓ DataMapper works!")
            logger.info(f"  - Message ID: {message.id}")
            logger.info(f"  - Is new: {is_new}")
            logger.info(f"  - Channel ID: {message.channel_id}")

            # Clean up test data
            await session.delete(message)
            await session.commit()

        await db_manager.close()
        return True

    except Exception as e:
        logger.error(f"✗ DataMapper failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_ingestion_service():
    """Test IngestionService."""
    logger.info("\n" + "="*60)
    logger.info("Test 4: IngestionService")
    logger.info("="*60)

    try:
        from src.database import DatabaseManager
        from src.services.ingestion_service import IngestionService
        import redis.asyncio as aioredis

        # Initialize database
        db_manager = DatabaseManager()
        db_manager.init_engine()

        # Initialize Redis
        redis_client = None
        try:
            redis_client = aioredis.from_url(settings.redis_url_str)
            await redis_client.ping()
            logger.info("  - Redis connected")
        except:
            logger.warning("  - Redis not available, continuing without cache")

        async with db_manager.session() as session:
            service = IngestionService(
                session=session,
                redis_client=redis_client,
                normalize_text=True
            )

            # Test stats
            stats = await service.get_stats()
            logger.info(f"✓ IngestionService works!")
            logger.info(f"  - Total messages: {stats['total_messages']}")
            logger.info(f"  - Total channels: {stats['total_channels']}")
            logger.info(f"  - Active channels: {stats['active_channels']}")

            # Test health check
            health = await service.health_check()
            logger.info(f"  - Database: {'✓' if health['database'] else '✗'}")
            logger.info(f"  - API: {'✓' if health['api'] else '✗'}")
            logger.info(f"  - Redis: {'✓' if health['redis'] else '✗' if health['redis'] is not None else 'N/A'}")

        if redis_client:
            await redis_client.aclose()
        await db_manager.close()
        return True

    except Exception as e:
        logger.error(f"✗ IngestionService failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    logger.info("\n" + "🧪 Starting Phase 2 Component Tests" + "\n")

    results = {}

    # Run tests
    results["API Client"] = await test_api_client()
    results["TextNormalizer"] = await test_text_normalizer()
    results["DataMapper"] = await test_data_mapper()
    results["IngestionService"] = await test_ingestion_service()

    # Summary
    logger.info("\n" + "="*60)
    logger.info("Test Summary")
    logger.info("="*60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status:8} - {test_name}")

    logger.info("="*60)

    total = len(results)
    passed = sum(results.values())

    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        logger.info("✓ All tests passed! 🎉")
        sys.exit(0)
    else:
        logger.error(f"✗ {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
