#!/usr/bin/env python3
"""
Initialize database with tables and initial data.

This script creates all database tables and optionally seeds with sample data.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from src.config import settings
from src.models import Base, Category, Channel, Tag, TagType
from src.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def create_tables() -> None:
    """Create all database tables."""
    logger.info("Creating database tables...")

    engine = create_async_engine(
        settings.database_url_str,
        echo=True,
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✓ All tables created successfully")
    except Exception as e:
        logger.error(f"✗ Failed to create tables: {e}")
        raise
    finally:
        await engine.dispose()


async def seed_initial_data() -> None:
    """Seed database with initial data."""
    from src.database import db_manager

    logger.info("Seeding initial data...")

    db_manager.init_engine()

    try:
        async with db_manager.session() as session:
            # Create categories
            categories = [
                Category(name="اخبار", description="کانال‌های خبری"),
                Category(name="فناوری", description="کانال‌های فناوری و تکنولوژی"),
                Category(name="اقتصاد", description="کانال‌های اقتصادی و بورس"),
                Category(name="ورزش", description="کانال‌های ورزشی"),
                Category(name="سرگرمی", description="کانال‌های سرگرمی"),
            ]
            session.add_all(categories)
            await session.flush()

            logger.info(f"✓ Created {len(categories)} categories")

            # Create sample tags
            tags = [
                Tag(
                    name="پیام کوتاه",
                    tag_type=TagType.CHARACTER_COUNT,
                    condition={"max": 100},
                    description="پیام‌های کوتاه با کمتر از 100 کاراکتر",
                ),
                Tag(
                    name="پیام متوسط",
                    tag_type=TagType.CHARACTER_COUNT,
                    condition={"min": 100, "max": 500},
                    description="پیام‌های متوسط با 100-500 کاراکتر",
                ),
                Tag(
                    name="پیام بلند",
                    tag_type=TagType.CHARACTER_COUNT,
                    condition={"min": 500},
                    description="پیام‌های بلند با بیش از 500 کاراکتر",
                ),
                Tag(
                    name="کلمات کم",
                    tag_type=TagType.WORD_COUNT,
                    condition={"max": 20},
                    description="پیام‌ها با کمتر از 20 کلمه",
                ),
                Tag(
                    name="کلمات زیاد",
                    tag_type=TagType.WORD_COUNT,
                    condition={"min": 50},
                    description="پیام‌ها با بیش از 50 کلمه",
                ),
            ]
            session.add_all(tags)
            await session.flush()

            logger.info(f"✓ Created {len(tags)} tags")

            await session.commit()
            logger.info("✓ Initial data seeded successfully")

    except Exception as e:
        logger.error(f"✗ Failed to seed data: {e}")
        raise
    finally:
        await db_manager.close()


async def main() -> None:
    """Main function to initialize database."""
    try:
        logger.info("=" * 60)
        logger.info("Database Initialization Started")
        logger.info("=" * 60)

        # Create tables
        await create_tables()

        # Seed initial data
        await seed_initial_data()

        logger.info("=" * 60)
        logger.info("Database Initialization Completed Successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
