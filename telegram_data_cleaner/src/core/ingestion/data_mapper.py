"""
Data mapper for converting API schemas to database models.
"""
from datetime import datetime, timezone as tz
from typing import Optional, Dict, Any
from uuid import UUID

import jdatetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.exceptions import DataMappingError, DataValidationError
from src.schemas.ingestion import APIMessageSchema, APIChannelInfoSchema
from src.models.channel import Channel
from src.models.message import Message
from src.models.category import Category

logger = get_logger(__name__)


def parse_jalali_to_utc(jalali_str: str) -> datetime:
    """
    Parse Jalali date string to UTC datetime.

    Args:
        jalali_str: Jalali date in format "1404-08-25 17:39:54"

    Returns:
        UTC datetime object

    Example:
        >>> parse_jalali_to_utc("1404-08-25 17:39:54")
        datetime(2025, 11, 16, 17, 39, 54, tzinfo=timezone.utc)
    """
    try:
        # Parse format: "1404-08-25 17:39:54"
        parts = jalali_str.strip().split()
        date_part = parts[0]  # "1404-08-25"
        time_part = parts[1] if len(parts) > 1 else "00:00:00"  # "17:39:54"

        # Split date
        year, month, day = map(int, date_part.split('-'))

        # Split time
        hour, minute, second = map(int, time_part.split(':'))

        # Create Jalali datetime
        j_dt = jdatetime.datetime(year, month, day, hour, minute, second)

        # Convert to Gregorian
        g_dt = j_dt.togregorian()

        # Make timezone-aware (assume Tehran timezone, then convert to UTC)
        # Tehran is UTC+3:30
        from datetime import timedelta
        tehran_offset = timedelta(hours=3, minutes=30)

        # Create UTC datetime by subtracting Tehran offset
        utc_dt = g_dt - tehran_offset

        # Make it timezone-aware
        utc_dt = utc_dt.replace(tzinfo=tz.utc)

        return utc_dt

    except Exception as e:
        logger.warning(f"Failed to parse Jalali date '{jalali_str}': {e}")
        # Fallback to current UTC time
        return datetime.now(tz.utc)


class DataMapper:
    """
    Maps API response schemas to database models.

    Handles conversion from Pydantic schemas to SQLAlchemy models,
    including relationship management and data validation.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize data mapper.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self._channel_cache: Dict[str, UUID] = {}  # telegram_id -> UUID
        self._category_cache: Dict[str, UUID] = {}  # category_name -> UUID

    async def get_or_create_category(
        self, category_name: Optional[str]
    ) -> Optional[UUID]:
        """
        Get existing category or create new one.

        Args:
            category_name: Category name from API

        Returns:
            Category UUID or None
        """
        if not category_name:
            return None

        # Check cache first
        if category_name in self._category_cache:
            return self._category_cache[category_name]

        try:
            # Try to find existing category
            result = await self.session.execute(
                select(Category).where(Category.name == category_name)
            )
            category = result.scalar_one_or_none()

            if not category:
                # Create new category
                category = Category(
                    name=category_name,
                    description=f"Auto-created from API data"
                )
                self.session.add(category)
                await self.session.flush()  # Get the ID
                logger.info(f"Created new category: {category_name}")

            # Cache the result
            self._category_cache[category_name] = category.id
            return category.id

        except Exception as e:
            logger.error(f"Failed to get/create category '{category_name}': {e}")
            raise DataMappingError(
                source="API category",
                target="Category model",
                reason=str(e)
            ) from e

    async def get_or_create_channel(
        self, channel_info: APIChannelInfoSchema, category_name: Optional[str] = None
    ) -> UUID:
        """
        Get existing channel or create new one.

        Args:
            channel_info: Channel info from API
            category_name: Category name (optional)

        Returns:
            Channel UUID

        Raises:
            DataMappingError: If channel creation/retrieval fails
        """
        telegram_id = str(channel_info.id)

        # Check cache first
        if telegram_id in self._channel_cache:
            return self._channel_cache[telegram_id]

        try:
            # Try to find existing channel
            result = await self.session.execute(
                select(Channel).where(Channel.telegram_id == telegram_id)
            )
            channel = result.scalar_one_or_none()

            if channel:
                # Update channel info if changed
                updated = False
                if channel.name != channel_info.name:
                    channel.name = channel_info.name
                    updated = True
                if channel.username != channel_info.username:
                    channel.username = channel_info.username
                    updated = True

                # Update last_sync
                channel.last_sync = datetime.now()
                updated = True

                if updated:
                    logger.debug(f"Updated channel: {channel_info.name}")

            else:
                # Get or create category
                category_id = await self.get_or_create_category(category_name)

                # Create new channel
                channel = Channel(
                    telegram_id=telegram_id,
                    name=channel_info.name,
                    username=channel_info.username,
                    category_id=category_id,
                    is_active=True,
                    last_sync=datetime.now(),
                )
                self.session.add(channel)
                await self.session.flush()  # Get the ID
                logger.info(f"Created new channel: {channel_info.name} ({telegram_id})")

            # Cache the result
            self._channel_cache[telegram_id] = channel.id
            return channel.id

        except Exception as e:
            logger.error(f"Failed to get/create channel '{channel_info.name}': {e}")
            raise DataMappingError(
                source="API channel",
                target="Channel model",
                reason=str(e)
            ) from e

    async def map_message_to_model(
        self, api_message: APIMessageSchema
    ) -> Message:
        """
        Convert API message schema to Message model.

        Args:
            api_message: Message from API

        Returns:
            Message model instance (not yet saved)

        Raises:
            DataMappingError: If mapping fails
            DataValidationError: If data validation fails
        """
        try:
            # Validate message_id
            if api_message.message_id <= 0:
                raise DataValidationError(
                    field="message_id",
                    value=api_message.message_id,
                    reason="Message ID must be positive"
                )

            # Get or create channel
            channel_id = await self.get_or_create_channel(api_message.channel)

            # Parse jalali_date if available, otherwise use API date
            message_date = api_message.date
            if api_message.jalali_date:
                try:
                    # Convert Jalali to UTC
                    message_date = parse_jalali_to_utc(api_message.jalali_date)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse jalali_date for message {api_message.message_id}, "
                        f"using API date instead: {e}"
                    )

            # Build extra_data with additional fields
            extra_data: Dict[str, Any] = {}
            if api_message.jalali_date:
                extra_data["jalali_date"] = api_message.jalali_date
            if api_message.replies_count is not None:
                extra_data["replies_count"] = api_message.replies_count

            # Create Message model
            message = Message(
                api_message_id=api_message.id,  # API database ID
                telegram_message_id=api_message.message_id,  # Telegram message ID
                channel_id=channel_id,
                text=api_message.text,
                text_normalized=None,  # Will be set by TextNormalizer later
                date=message_date,  # Use parsed Jalali date or API date
                views=api_message.views_count,
                forwards=api_message.forwards_count,
                extra_data=extra_data if extra_data else None,
            )

            return message

        except (DataValidationError, DataMappingError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            logger.error(f"Failed to map message {api_message.message_id}: {e}")
            raise DataMappingError(
                source="API message",
                target="Message model",
                reason=str(e)
            ) from e

    async def check_message_exists(
        self, channel_id: UUID, telegram_message_id: int
    ) -> Optional[Message]:
        """
        Check if message already exists in database.

        Args:
            channel_id: Channel UUID
            telegram_message_id: Telegram message ID

        Returns:
            Existing message or None
        """
        try:
            result = await self.session.execute(
                select(Message).where(
                    Message.channel_id == channel_id,
                    Message.telegram_message_id == telegram_message_id
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to check message existence: {e}")
            return None

    async def upsert_message(
        self, api_message: APIMessageSchema, update_existing: bool = True
    ) -> tuple[Message, bool]:
        """
        Insert or update message in database.

        Args:
            api_message: Message from API
            update_existing: Whether to update existing messages (default: True)

        Returns:
            Tuple of (message, is_new)
            - message: Message model instance
            - is_new: True if newly created, False if updated

        Raises:
            DataMappingError: If upsert fails
        """
        try:
            # Map to model
            message = await self.map_message_to_model(api_message)

            # Check if message exists
            existing = await self.check_message_exists(
                message.channel_id, message.telegram_message_id
            )

            if existing:
                if update_existing:
                    # Update existing message
                    existing.api_message_id = message.api_message_id
                    existing.text = message.text
                    existing.date = message.date
                    existing.views = message.views
                    existing.forwards = message.forwards
                    existing.extra_data = message.extra_data
                    # Note: text_normalized is NOT updated (preserve processing)
                    logger.debug(
                        f"Updated message: {message.telegram_message_id} "
                        f"in channel {message.channel_id}"
                    )
                    return existing, False
                else:
                    # Skip update
                    logger.debug(
                        f"Skipped existing message: {message.telegram_message_id}"
                    )
                    return existing, False
            else:
                # Insert new message
                self.session.add(message)
                logger.debug(
                    f"Inserted new message: {message.telegram_message_id} "
                    f"in channel {message.channel_id}"
                )
                return message, True

        except Exception as e:
            logger.error(f"Failed to upsert message: {e}")
            raise DataMappingError(
                source="API message",
                target="Message model",
                reason=f"Upsert failed: {str(e)}"
            ) from e

    async def bulk_upsert_messages(
        self, api_messages: list[APIMessageSchema], update_existing: bool = True
    ) -> Dict[str, int]:
        """
        Bulk insert/update messages.

        Args:
            api_messages: List of messages from API
            update_existing: Whether to update existing messages

        Returns:
            Statistics dict with counts:
            - inserted: Number of new messages
            - updated: Number of updated messages
            - skipped: Number of skipped messages
            - failed: Number of failed messages

        Note:
            This method commits the transaction on success.
        """
        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
        }

        logger.info(f"Starting bulk upsert of {len(api_messages)} messages...")

        for api_message in api_messages:
            try:
                message, is_new = await self.upsert_message(
                    api_message, update_existing=update_existing
                )

                if is_new:
                    stats["inserted"] += 1
                elif update_existing:
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1

            except Exception as e:
                stats["failed"] += 1
                logger.error(
                    f"Failed to upsert message {api_message.message_id}: {e}"
                )
                # Continue processing other messages

        # Commit all changes
        try:
            await self.session.commit()
            logger.info(
                f"Bulk upsert complete: "
                f"{stats['inserted']} inserted, "
                f"{stats['updated']} updated, "
                f"{stats['skipped']} skipped, "
                f"{stats['failed']} failed"
            )
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to commit bulk upsert: {e}")
            raise DataMappingError(
                source="Bulk messages",
                target="Database",
                reason=f"Commit failed: {str(e)}"
            ) from e

        return stats

    def clear_cache(self) -> None:
        """Clear internal caches."""
        self._channel_cache.clear()
        self._category_cache.clear()
        logger.debug("DataMapper cache cleared")

    async def get_channel_stats(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a channel.

        Args:
            telegram_id: Channel telegram ID

        Returns:
            Stats dict or None if channel not found
        """
        try:
            # Get channel
            result = await self.session.execute(
                select(Channel).where(Channel.telegram_id == telegram_id)
            )
            channel = result.scalar_one_or_none()

            if not channel:
                return None

            # Count messages
            from sqlalchemy import func
            result = await self.session.execute(
                select(func.count(Message.id)).where(
                    Message.channel_id == channel.id
                )
            )
            message_count = result.scalar_one()

            return {
                "channel_id": str(channel.id),
                "telegram_id": channel.telegram_id,
                "name": channel.name,
                "username": channel.username,
                "message_count": message_count,
                "is_active": channel.is_active,
                "last_sync": channel.last_sync,
            }

        except Exception as e:
            logger.error(f"Failed to get channel stats: {e}")
            return None
