#!/usr/bin/env python3
"""
Check system setup and verify all components are working.

This script validates:
    - PostgreSQL connection
    - Redis connection
    - Model imports
    - Configuration loading
    - Alembic migrations
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import redis
from alembic.config import Config
from alembic.script import ScriptDirectory

from src.config import settings
from src.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def print_header(title: str) -> None:
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(check: str, success: bool, message: str = "") -> None:
    """Print check result."""
    status = "✓" if success else "✗"
    color = "\033[32m" if success else "\033[31m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} {check}")
    if message:
        print(f"  └─ {message}")


async def check_postgresql() -> bool:
    """Check PostgreSQL connection."""
    logger.info("Checking PostgreSQL connection...")

    try:
        engine = create_async_engine(settings.database_url_str)

        async with engine.connect() as conn:
            # Test basic query
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()

            # Get database size
            result = await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            db_size = result.scalar()

        await engine.dispose()

        print_result("PostgreSQL Connection", True, f"Version: {version[:50]}...")
        print_result("Database Size", True, db_size)
        return True

    except Exception as e:
        print_result("PostgreSQL Connection", False, str(e))
        return False


def check_redis() -> bool:
    """Check Redis connection."""
    logger.info("Checking Redis connection...")

    try:
        # Parse Redis URL
        redis_client = redis.from_url(
            settings.redis_url_str,
            decode_responses=True,
        )

        # Test connection
        redis_client.ping()

        # Get Redis info
        info = redis_client.info()
        version = info.get("redis_version", "Unknown")
        used_memory = info.get("used_memory_human", "Unknown")

        redis_client.close()

        print_result("Redis Connection", True, f"Version: {version}")
        print_result("Redis Memory Usage", True, used_memory)
        return True

    except Exception as e:
        print_result("Redis Connection", False, str(e))
        return False


def check_models() -> bool:
    """Check if all models can be imported."""
    logger.info("Checking model imports...")

    try:
        from src.models import (
            Base,
            Category,
            Channel,
            Message,
            Tag,
            TagType,
            MessageTag,
        )

        models = [Category, Channel, Message, Tag, MessageTag]
        print_result("Model Imports", True, f"{len(models)} models loaded")

        # Check model tables
        tables = list(Base.metadata.tables.keys())
        print_result("Database Tables", True, f"{len(tables)} tables defined")
        for table in tables:
            print(f"    • {table}")

        return True

    except Exception as e:
        print_result("Model Imports", False, str(e))
        return False


def check_config() -> bool:
    """Check configuration loading."""
    logger.info("Checking configuration...")

    try:
        print_result("Configuration Loading", True)
        print(f"    • Environment: {settings.environment}")
        print(f"    • Log Level: {settings.log_level}")
        print(f"    • Polling Interval: {settings.polling_interval}s")
        print(f"    • History Days: {settings.history_days}")
        print(f"    • Database Pool Size: {settings.database_pool_size}")
        print(f"    • API URL: {settings.api_url}")
        return True

    except Exception as e:
        print_result("Configuration Loading", False, str(e))
        return False


def check_alembic() -> bool:
    """Check Alembic migrations."""
    logger.info("Checking Alembic setup...")

    try:
        alembic_ini = Path(__file__).parent.parent / "alembic.ini"
        if not alembic_ini.exists():
            print_result("Alembic Config", False, "alembic.ini not found")
            return False

        config = Config(str(alembic_ini))
        script = ScriptDirectory.from_config(config)

        # Get migration heads
        heads = script.get_heads()
        revisions = list(script.walk_revisions())

        print_result("Alembic Setup", True)
        print(f"    • Migration heads: {len(heads)}")
        print(f"    • Total revisions: {len(revisions)}")

        return True

    except Exception as e:
        print_result("Alembic Setup", False, str(e))
        return False


def check_file_structure() -> bool:
    """Check project file structure."""
    logger.info("Checking file structure...")

    project_root = Path(__file__).parent.parent
    required_paths = [
        "src/config.py",
        "src/database.py",
        "src/models/__init__.py",
        "src/core/logging.py",
        "alembic/env.py",
        "alembic.ini",
        "pyproject.toml",
        ".env.example",
        "docker/docker-compose.yml",
    ]

    all_exist = True
    for path in required_paths:
        full_path = project_root / path
        exists = full_path.exists()
        if not exists:
            all_exist = False
        print_result(f"  {path}", exists)

    return all_exist


async def main() -> None:
    """Run all checks."""
    print("\n" + "🔍 System Setup Verification" + "\n")

    checks = []

    # Check file structure
    print_header("File Structure")
    checks.append(check_file_structure())

    # Check configuration
    print_header("Configuration")
    checks.append(check_config())

    # Check models
    print_header("Models")
    checks.append(check_models())

    # Check PostgreSQL
    print_header("PostgreSQL")
    checks.append(await check_postgresql())

    # Check Redis
    print_header("Redis")
    checks.append(check_redis())

    # Check Alembic
    print_header("Alembic Migrations")
    checks.append(check_alembic())

    # Summary
    print_header("Summary")
    total = len(checks)
    passed = sum(checks)
    failed = total - passed

    if all(checks):
        print(f"\n✓ All {total} checks passed! System is ready.")
        sys.exit(0)
    else:
        print(f"\n✗ {failed} of {total} checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
