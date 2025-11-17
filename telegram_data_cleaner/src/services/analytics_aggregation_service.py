"""
Service for aggregating analytics data into channel_analytics table.

This service runs periodically to calculate and store analytics for each channel
based on 5-minute time slots.
"""
from datetime import datetime, timezone as tz, timedelta, date
from typing import Optional, List, Dict, Any
import uuid

import jdatetime
from sqlalchemy import select, func, and_, or_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.models.channel import Channel
from src.models.message import Message
from src.models.channel_analytics import ChannelAnalytics
from src.models.message_dictionary import MessageDictionary
from src.models.dictionary_word import DictionaryWord
from src.models.dictionary_category import DictionaryCategory

logger = get_logger(__name__)


def calculate_time_slot(minute: int) -> int:
    """
    Calculate 5-minute time slot from minute (0-59).

    Args:
        minute: Minute of the hour (0-59)

    Returns:
        Time slot (0-11)

    Examples:
        0-4 -> 0
        5-9 -> 1
        10-14 -> 2
        ...
        55-59 -> 11
    """
    return minute // 5


def datetime_to_jalali_date(dt: datetime) -> str:
    """
    Convert datetime to Jalali date string.

    Args:
        dt: DateTime object (timezone-aware)

    Returns:
        Jalali date string in format "1404-08-25"
    """
    # Convert UTC to Tehran time (UTC+3:30)
    tehran_offset = timedelta(hours=3, minutes=30)
    tehran_dt = dt + tehran_offset

    # Convert to Jalali
    j_date = jdatetime.date.fromgregorian(date=tehran_dt.date())

    return j_date.strftime('%Y-%m-%d')


class AnalyticsAggregationService:
    """
    Service for aggregating message data into analytics records.

    Calculates statistics for each channel based on 5-minute time slots.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize analytics aggregation service.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def aggregate_time_slot(
        self,
        channel_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[ChannelAnalytics]:
        """
        Aggregate analytics for a specific time slot.

        Args:
            channel_id: Channel UUID
            start_time: Start of time slot (inclusive)
            end_time: End of time slot (exclusive)

        Returns:
            ChannelAnalytics record or None if no messages
        """
        # Get all messages in this time slot
        result = await self.session.execute(
            select(Message.id)
            .where(
                and_(
                    Message.channel_id == channel_id,
                    Message.date >= start_time,
                    Message.date < end_time
                )
            )
        )
        message_ids = [row[0] for row in result.all()]

        if not message_ids:
            return None

        # Count total messages
        message_count = len(message_ids)

        # Count messages with dictionary matches
        result = await self.session.execute(
            select(func.count(distinct(MessageDictionary.message_id)))
            .where(MessageDictionary.message_id.in_(message_ids))
        )
        match_count = result.scalar() or 0

        # Get top symbols (نمادها category)
        top_symbols = await self._get_top_symbols(message_ids)

        # Get top industries
        top_industries = await self._get_top_industries(message_ids)

        # Get top categories
        top_categories = await self._get_top_categories(message_ids)

        # Extract date/time information from start_time
        # Convert to Tehran time for jalali date
        tehran_offset = timedelta(hours=3, minutes=30)
        tehran_dt = start_time + tehran_offset

        analytics_date = tehran_dt.date()
        hour = tehran_dt.hour
        time_slot = calculate_time_slot(tehran_dt.minute)
        jalali_date = datetime_to_jalali_date(start_time)
        day_of_week = tehran_dt.weekday()  # 0=Monday, 6=Sunday

        # Create or update analytics record
        analytics = ChannelAnalytics(
            channel_id=channel_id,
            date=analytics_date,
            hour=hour,
            time_slot=time_slot,
            jalali_date=jalali_date,
            day_of_week=day_of_week,
            message_count=message_count,
            match_count=match_count,
            top_symbols=top_symbols,
            top_industries=top_industries,
            top_categories=top_categories
        )

        return analytics

    async def _get_top_symbols(
        self,
        message_ids: List[uuid.UUID],
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """Get top symbols from نمادها category."""
        if not message_ids:
            return None

        # Find نمادها category
        result = await self.session.execute(
            select(DictionaryCategory).where(DictionaryCategory.name == 'نمادها')
        )
        category = result.scalar_one_or_none()

        if not category:
            return None

        # Get word counts (DISTINCT messages per word)
        result = await self.session.execute(
            select(
                DictionaryWord.id,
                DictionaryWord.word,
                func.count(func.distinct(MessageDictionary.message_id)).label('count')
            )
            .join(MessageDictionary, MessageDictionary.word_id == DictionaryWord.id)
            .where(
                and_(
                    MessageDictionary.message_id.in_(message_ids),
                    DictionaryWord.category_id == category.id
                )
            )
            .group_by(DictionaryWord.id, DictionaryWord.word)
            .order_by(func.count(func.distinct(MessageDictionary.message_id)).desc())
            .limit(limit)
        )

        top_symbols = []
        for row in result:
            top_symbols.append({
                'id': str(row.id),
                'word': row.word,
                'count': row.count
            })

        return top_symbols if top_symbols else None

    async def _get_top_industries(
        self,
        message_ids: List[uuid.UUID],
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """Get top industries from symbols' extra_data."""
        if not message_ids:
            return None

        from sqlalchemy import literal_column

        industry_expr = literal_column("dictionary_words.extra_data->>'industry_name'")

        # Get industry counts (DISTINCT messages per industry)
        result = await self.session.execute(
            select(
                industry_expr.label('industry_name'),
                func.count(func.distinct(MessageDictionary.message_id)).label('count')
            )
            .select_from(MessageDictionary)
            .join(DictionaryWord, MessageDictionary.word_id == DictionaryWord.id)
            .where(
                and_(
                    MessageDictionary.message_id.in_(message_ids),
                    industry_expr.isnot(None)
                )
            )
            .group_by(industry_expr)
            .order_by(func.count(func.distinct(MessageDictionary.message_id)).desc())
            .limit(limit)
        )

        top_industries = []
        for row in result:
            top_industries.append({
                'name': row.industry_name,
                'count': row.count
            })

        return top_industries if top_industries else None

    async def _get_top_categories(
        self,
        message_ids: List[uuid.UUID],
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """Get top dictionary categories."""
        if not message_ids:
            return None

        # Get category counts (DISTINCT messages per category)
        result = await self.session.execute(
            select(
                DictionaryCategory.id,
                DictionaryCategory.name,
                func.count(func.distinct(MessageDictionary.message_id)).label('count')
            )
            .join(DictionaryWord, DictionaryWord.category_id == DictionaryCategory.id)
            .join(MessageDictionary, MessageDictionary.word_id == DictionaryWord.id)
            .where(MessageDictionary.message_id.in_(message_ids))
            .group_by(DictionaryCategory.id, DictionaryCategory.name)
            .order_by(func.count(func.distinct(MessageDictionary.message_id)).desc())
            .limit(limit)
        )

        top_categories = []
        for row in result:
            top_categories.append({
                'id': str(row.id),
                'name': row.name,
                'count': row.count
            })

        return top_categories if top_categories else None

    async def aggregate_last_5_minutes(self) -> Dict[str, Any]:
        """
        Aggregate analytics for the last completed 5-minute slot.

        This should be called every 5 minutes by the scheduler.

        Returns:
            Statistics about the aggregation
        """
        # Calculate the last completed 5-minute slot
        now = datetime.now(tz.utc)

        # Round down to the last 5-minute boundary
        current_minute = now.minute
        slot_start_minute = (current_minute // 5) * 5

        # Get start of current slot
        slot_start = now.replace(minute=slot_start_minute, second=0, microsecond=0)

        # We want to aggregate the PREVIOUS slot (last completed)
        end_time = slot_start
        start_time = end_time - timedelta(minutes=5)

        logger.info(f"Aggregating analytics for time slot: {start_time} to {end_time}")

        # Get all active channels
        result = await self.session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels = result.scalars().all()

        stats = {
            'channels_processed': 0,
            'channels_with_data': 0,
            'records_created': 0,
            'records_updated': 0,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
        }

        for channel in channels:
            stats['channels_processed'] += 1

            # Aggregate data for this channel and time slot
            analytics = await self.aggregate_time_slot(
                channel_id=channel.id,
                start_time=start_time,
                end_time=end_time
            )

            if analytics:
                stats['channels_with_data'] += 1

                # Check if record already exists
                result = await self.session.execute(
                    select(ChannelAnalytics).where(
                        and_(
                            ChannelAnalytics.channel_id == channel.id,
                            ChannelAnalytics.date == analytics.date,
                            ChannelAnalytics.hour == analytics.hour,
                            ChannelAnalytics.time_slot == analytics.time_slot
                        )
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing record
                    existing.message_count = analytics.message_count
                    existing.match_count = analytics.match_count
                    existing.top_symbols = analytics.top_symbols
                    existing.top_industries = analytics.top_industries
                    existing.top_categories = analytics.top_categories
                    existing.jalali_date = analytics.jalali_date
                    stats['records_updated'] += 1
                    logger.debug(f"Updated analytics for {channel.name}: {analytics.message_count} messages")
                else:
                    # Insert new record
                    self.session.add(analytics)
                    stats['records_created'] += 1
                    logger.debug(f"Created analytics for {channel.name}: {analytics.message_count} messages")

        # Commit all changes
        await self.session.commit()

        logger.info(
            f"Analytics aggregation complete: "
            f"{stats['records_created']} created, "
            f"{stats['records_updated']} updated, "
            f"{stats['channels_with_data']}/{stats['channels_processed']} channels had data"
        )

        return stats

    async def backfill_all_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Backfill analytics for all historical messages.

        This method aggregates all messages into 5-minute time slots
        and creates analytics records for the entire history.

        Args:
            start_date: Start date for backfill (default: earliest message)
            end_date: End date for backfill (default: now)

        Returns:
            Statistics about the backfill operation
        """
        logger.info("Starting analytics backfill...")

        # Get date range from messages if not provided
        if not start_date or not end_date:
            result = await self.session.execute(
                select(
                    func.min(Message.date).label('min_date'),
                    func.max(Message.date).label('max_date')
                )
            )
            row = result.first()

            if not row or not row.min_date:
                logger.warning("No messages found for backfill")
                return {
                    'status': 'no_data',
                    'message': 'No messages found'
                }

            start_date = start_date or row.min_date
            end_date = end_date or datetime.now(tz.utc)

        logger.info(f"Backfilling analytics from {start_date} to {end_date}")

        # Get all active channels
        result = await self.session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels = result.scalars().all()

        stats = {
            'channels_processed': 0,
            'total_slots_processed': 0,
            'records_created': 0,
            'records_updated': 0,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        }

        # Process each channel
        for channel in channels:
            stats['channels_processed'] += 1
            logger.info(f"Processing channel: {channel.name} ({stats['channels_processed']}/{len(channels)})")

            # Generate all 5-minute slots between start and end
            current_slot_start = start_date.replace(minute=(start_date.minute // 5) * 5, second=0, microsecond=0)

            while current_slot_start < end_date:
                slot_end = current_slot_start + timedelta(minutes=5)

                # Aggregate this time slot
                analytics = await self.aggregate_time_slot(
                    channel_id=channel.id,
                    start_time=current_slot_start,
                    end_time=slot_end
                )

                if analytics:
                    # Check if record already exists
                    result = await self.session.execute(
                        select(ChannelAnalytics).where(
                            and_(
                                ChannelAnalytics.channel_id == channel.id,
                                ChannelAnalytics.date == analytics.date,
                                ChannelAnalytics.hour == analytics.hour,
                                ChannelAnalytics.time_slot == analytics.time_slot
                            )
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update existing record
                        existing.message_count = analytics.message_count
                        existing.match_count = analytics.match_count
                        existing.top_symbols = analytics.top_symbols
                        existing.top_industries = analytics.top_industries
                        existing.top_categories = analytics.top_categories
                        existing.jalali_date = analytics.jalali_date
                        stats['records_updated'] += 1
                    else:
                        # Insert new record
                        self.session.add(analytics)
                        stats['records_created'] += 1

                stats['total_slots_processed'] += 1

                # Commit every 100 slots to avoid memory issues
                if stats['total_slots_processed'] % 100 == 0:
                    await self.session.commit()
                    logger.info(
                        f"Progress: {stats['total_slots_processed']} slots, "
                        f"{stats['records_created']} created, {stats['records_updated']} updated"
                    )

                # Move to next slot
                current_slot_start = slot_end

        # Final commit
        await self.session.commit()

        logger.info(
            f"Analytics backfill complete: "
            f"{stats['channels_processed']} channels, "
            f"{stats['total_slots_processed']} slots processed, "
            f"{stats['records_created']} created, "
            f"{stats['records_updated']} updated"
        )

        stats['status'] = 'success'
        return stats
