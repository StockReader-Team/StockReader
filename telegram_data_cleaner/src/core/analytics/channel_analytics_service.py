"""
Channel analytics service for computing and retrieving channel statistics.
"""
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import uuid
from collections import Counter

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.channel_analytics import ChannelAnalytics
from src.models.message import Message
from src.models.message_dictionary import MessageDictionary
from src.models.dictionary_word import DictionaryWord
from src.models.dictionary_category import DictionaryCategory
from src.models.channel import Channel
from src.core.logging import get_logger

logger = get_logger(__name__)


class ChannelAnalyticsService:
    """Service for computing and managing channel analytics."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the analytics service.

        Args:
            session: Database session
        """
        self.session = session

    async def compute_aggregates(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        granularity: str = "hourly"
    ) -> int:
        """
        Compute analytics aggregates for a time range.

        Args:
            start_datetime: Start of time range
            end_datetime: End of time range
            granularity: "hourly" or "daily"

        Returns:
            Number of analytics records created/updated
        """
        logger.info(
            f"Computing {granularity} aggregates from {start_datetime} to {end_datetime}"
        )

        # Get all active channels
        result = await self.session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels = result.scalars().all()

        records_created = 0

        for channel in channels:
            if granularity == "hourly":
                records_created += await self._compute_hourly_aggregates(
                    channel, start_datetime, end_datetime
                )
            elif granularity == "daily":
                records_created += await self._compute_daily_aggregates(
                    channel, start_datetime.date(), end_datetime.date()
                )

        await self.session.commit()
        logger.info(f"Created/updated {records_created} analytics records")
        return records_created

    async def _compute_hourly_aggregates(
        self,
        channel: Channel,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> int:
        """Compute hourly aggregates for a channel."""
        records_created = 0

        # Generate all hours in the range
        current = start_datetime.replace(minute=0, second=0, microsecond=0)

        while current < end_datetime:
            next_hour = current + timedelta(hours=1)

            # Get messages in this hour
            result = await self.session.execute(
                select(Message)
                .where(
                    and_(
                        Message.channel_id == channel.id,
                        Message.created_at >= current,
                        Message.created_at < next_hour
                    )
                )
            )
            messages = result.scalars().all()

            if messages:
                # Compute statistics for this hour
                analytics_data = await self._compute_statistics(
                    channel.id,
                    current.date(),
                    current.hour,
                    messages
                )

                # Create or update analytics record
                existing = await self.session.execute(
                    select(ChannelAnalytics).where(
                        and_(
                            ChannelAnalytics.channel_id == channel.id,
                            ChannelAnalytics.date == current.date(),
                            ChannelAnalytics.hour == current.hour
                        )
                    )
                )
                analytics = existing.scalar_one_or_none()

                if analytics:
                    # Update existing
                    for key, value in analytics_data.items():
                        setattr(analytics, key, value)
                    analytics.updated_at = datetime.utcnow()
                else:
                    # Create new
                    analytics = ChannelAnalytics(**analytics_data)
                    self.session.add(analytics)
                    records_created += 1

            current = next_hour

        return records_created

    async def _compute_daily_aggregates(
        self,
        channel: Channel,
        start_date: date,
        end_date: date
    ) -> int:
        """Compute daily aggregates for a channel."""
        records_created = 0
        current_date = start_date

        while current_date <= end_date:
            # Get messages for this day
            next_date = current_date + timedelta(days=1)

            result = await self.session.execute(
                select(Message)
                .where(
                    and_(
                        Message.channel_id == channel.id,
                        func.date(Message.created_at) == current_date
                    )
                )
            )
            messages = result.scalars().all()

            if messages:
                # Compute statistics for this day
                analytics_data = await self._compute_statistics(
                    channel.id,
                    current_date,
                    None,  # hour=None for daily
                    messages
                )

                # Create or update analytics record
                existing = await self.session.execute(
                    select(ChannelAnalytics).where(
                        and_(
                            ChannelAnalytics.channel_id == channel.id,
                            ChannelAnalytics.date == current_date,
                            ChannelAnalytics.hour.is_(None)
                        )
                    )
                )
                analytics = existing.scalar_one_or_none()

                if analytics:
                    # Update existing
                    for key, value in analytics_data.items():
                        setattr(analytics, key, value)
                    analytics.updated_at = datetime.utcnow()
                else:
                    # Create new
                    analytics = ChannelAnalytics(**analytics_data)
                    self.session.add(analytics)
                    records_created += 1

            current_date = next_date

        return records_created

    async def _compute_statistics(
        self,
        channel_id: uuid.UUID,
        analysis_date: date,
        hour: Optional[int],
        messages: List[Message]
    ) -> Dict[str, Any]:
        """
        Compute statistics for a set of messages.

        Args:
            channel_id: Channel ID
            analysis_date: Date being analyzed
            hour: Hour being analyzed (None for daily)
            messages: List of messages

        Returns:
            Dictionary of analytics data
        """
        message_ids = [msg.id for msg in messages]

        # Count matches
        result = await self.session.execute(
            select(func.count(func.distinct(MessageDictionary.message_id)))
            .where(MessageDictionary.message_id.in_(message_ids))
        )
        match_count = result.scalar() or 0

        # Get top symbols (category "نمادها")
        top_symbols = await self._get_top_words_by_category(
            message_ids, "نمادها", limit=10
        )

        # Get top industries - assume there's an industry field in extra_data
        top_industries = await self._get_top_industries(message_ids, limit=10)

        # Get top categories
        top_categories = await self._get_top_categories(message_ids, limit=10)

        return {
            "channel_id": channel_id,
            "date": analysis_date,
            "hour": hour,
            "day_of_week": analysis_date.weekday(),
            "message_count": len(messages),
            "match_count": match_count,
            "top_symbols": top_symbols,
            "top_industries": top_industries,
            "top_categories": top_categories,
        }

    async def _get_top_words_by_category(
        self,
        message_ids: List[uuid.UUID],
        category_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top words from a specific category."""
        if not message_ids:
            return []

        # Get category
        result = await self.session.execute(
            select(DictionaryCategory).where(DictionaryCategory.name == category_name)
        )
        category = result.scalar_one_or_none()

        if not category:
            return []

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

        top_words = []
        for row in result:
            top_words.append({
                "id": str(row.id),
                "word": row.word,
                "count": row.count
            })

        return top_words

    async def _get_top_industries(
        self,
        message_ids: List[uuid.UUID],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top industries from symbol extra_data."""
        if not message_ids:
            return []

        # Use literal_column for JSONB extraction in GROUP BY
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

        # Get top industries
        top_industries = []
        for row in result:
            top_industries.append({
                "name": row.industry_name,
                "count": row.count
            })

        return top_industries

    async def _get_top_categories(
        self,
        message_ids: List[uuid.UUID],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top dictionary categories."""
        if not message_ids:
            return []

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
                "id": str(row.id),
                "name": row.name,
                "count": row.count
            })

        return top_categories

    async def get_realtime_stats(
        self,
        channel_id: uuid.UUID,
        minutes: int
    ) -> Dict[str, Any]:
        """
        Get real-time statistics for the last N minutes.

        Args:
            channel_id: Channel ID
            minutes: Number of minutes to look back

        Returns:
            Statistics dictionary
        """
        from datetime import timezone as tz
        cutoff_time = datetime.now(tz.utc) - timedelta(minutes=minutes)

        # Get messages
        result = await self.session.execute(
            select(Message)
            .where(
                and_(
                    Message.channel_id == channel_id,
                    Message.created_at >= cutoff_time
                )
            )
        )
        messages = result.scalars().all()

        if not messages:
            return {
                "channel_id": str(channel_id),
                "time_range_minutes": minutes,
                "message_count": 0,
                "match_count": 0,
                "top_symbols": [],
                "top_industries": [],
                "top_categories": []
            }

        # Compute statistics
        message_ids = [msg.id for msg in messages]

        result = await self.session.execute(
            select(func.count(func.distinct(MessageDictionary.message_id)))
            .where(MessageDictionary.message_id.in_(message_ids))
        )
        match_count = result.scalar() or 0

        top_symbols = await self._get_top_words_by_category(message_ids, "نمادها", limit=10)
        top_industries = await self._get_top_industries(message_ids, limit=10)
        top_categories = await self._get_top_categories(message_ids, limit=10)

        return {
            "channel_id": str(channel_id),
            "time_range_minutes": minutes,
            "message_count": len(messages),
            "match_count": match_count,
            "top_symbols": top_symbols,
            "top_industries": top_industries,
            "top_categories": top_categories,
            "timeline": self._generate_timeline(messages, minutes)
        }

    def _generate_timeline(
        self,
        messages: List[Message],
        minutes: int
    ) -> List[Dict[str, Any]]:
        """Generate a timeline of message counts."""
        # Create buckets (5-minute intervals)
        bucket_size = 5  # minutes
        num_buckets = (minutes // bucket_size) + 1

        from datetime import timezone as tz
        cutoff_time = datetime.now(tz.utc) - timedelta(minutes=minutes)

        buckets = []
        for i in range(num_buckets):
            bucket_start = cutoff_time + timedelta(minutes=i * bucket_size)
            bucket_end = bucket_start + timedelta(minutes=bucket_size)

            # Count messages in this bucket
            count = sum(
                1 for msg in messages
                if bucket_start <= msg.created_at < bucket_end
            )

            buckets.append({
                "timestamp": bucket_start.isoformat(),
                "message_count": count
            })

        return buckets

    async def get_channel_content_profile(
        self,
        channel_id: uuid.UUID,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get content profile for a channel over the last N days.

        Args:
            channel_id: Channel ID
            days: Number of days to analyze

        Returns:
            Content profile dictionary
        """
        cutoff_date = date.today() - timedelta(days=days)

        # Get aggregated statistics
        result = await self.session.execute(
            select(ChannelAnalytics)
            .where(
                and_(
                    ChannelAnalytics.channel_id == channel_id,
                    ChannelAnalytics.date >= cutoff_date,
                    ChannelAnalytics.hour.is_(None)  # Daily aggregates only
                )
            )
            .order_by(ChannelAnalytics.date.desc())
        )
        analytics_records = result.scalars().all()

        if not analytics_records:
            return {
                "channel_id": str(channel_id),
                "days": days,
                "total_messages": 0,
                "total_matches": 0,
                "categories": [],
                "primary_focus": None
            }

        # Aggregate category counts
        category_counter = Counter()
        total_messages = 0
        total_matches = 0

        for record in analytics_records:
            total_messages += record.message_count
            total_matches += record.match_count

            if record.top_categories:
                for cat in record.top_categories:
                    category_counter[cat['name']] += cat['count']

        # Build category list
        categories = []
        total_category_matches = sum(category_counter.values())

        for cat_name, count in category_counter.most_common(10):
            percentage = (count / total_category_matches * 100) if total_category_matches > 0 else 0
            categories.append({
                "name": cat_name,
                "count": count,
                "percentage": round(percentage, 2)
            })

        primary_focus = categories[0]['name'] if categories else None

        return {
            "channel_id": str(channel_id),
            "days": days,
            "total_messages": total_messages,
            "total_matches": total_matches,
            "categories": categories,
            "primary_focus": primary_focus,
            "focus_percentage": categories[0]['percentage'] if categories else 0
        }

    async def get_global_overview(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get global overview analytics across all channels.

        Reads directly from messages and message_dictionaries tables.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with global analytics including totals, top items, and channel breakdown
        """
        logger.info(f"Getting global overview for last {days} days")

        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Get all channels
        result = await self.session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        all_channels = list(result.scalars().all())

        # Get total messages and matches for each channel
        channel_stats = []
        most_active_channel = None
        max_messages = 0

        for channel in all_channels:
            # Count messages
            result = await self.session.execute(
                select(func.count(Message.id))
                .where(
                    and_(
                        Message.channel_id == channel.id,
                        Message.created_at >= start_datetime,
                        Message.created_at <= end_datetime
                    )
                )
            )
            total_messages = result.scalar() or 0

            # Count matches
            result = await self.session.execute(
                select(func.count(MessageDictionary.message_id))
                .select_from(MessageDictionary)
                .join(Message, MessageDictionary.message_id == Message.id)
                .where(
                    and_(
                        Message.channel_id == channel.id,
                        Message.created_at >= start_datetime,
                        Message.created_at <= end_datetime
                    )
                )
            )
            total_matches = result.scalar() or 0

            channel_stats.append({
                "id": str(channel.id),
                "name": channel.name,
                "username": channel.username,
                "total_messages": total_messages,
                "total_matches": total_matches,
            })

            # Track most active
            if total_messages > max_messages:
                max_messages = total_messages
                most_active_channel = {
                    "id": str(channel.id),
                    "name": channel.name,
                    "username": channel.username,
                    "message_count": total_messages
                }

        # Sort channels by activity
        channel_stats.sort(key=lambda x: x['total_messages'], reverse=True)

        # Calculate global totals
        total_messages_global = sum(c['total_messages'] for c in channel_stats)
        total_matches_global = sum(c['total_matches'] for c in channel_stats)

        # Get top symbols (نمادها)
        result = await self.session.execute(
            select(
                DictionaryWord.word,
                func.count(MessageDictionary.message_id).label('count')
            )
            .select_from(MessageDictionary)
            .join(Message, MessageDictionary.message_id == Message.id)
            .join(DictionaryWord, MessageDictionary.word_id == DictionaryWord.id)
            .join(DictionaryCategory, DictionaryWord.category_id == DictionaryCategory.id)
            .where(
                and_(
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime,
                    DictionaryCategory.name == 'نمادها'
                )
            )
            .group_by(DictionaryWord.word)
            .order_by(func.count(MessageDictionary.message_id).desc())
            .limit(10)
        )
        top_symbols = [
            {"word": row.word, "count": row.count, "top_channels": []}
            for row in result
        ]

        # Get top industries from extra_data->>'industry_name'
        # Use literal_column to properly handle JSONB extraction in GROUP BY
        from sqlalchemy import literal_column

        industry_expr = literal_column("dictionary_words.extra_data->>'industry_name'")

        result = await self.session.execute(
            select(
                industry_expr.label('industry'),
                func.count(func.distinct(MessageDictionary.message_id)).label('count')
            )
            .select_from(MessageDictionary)
            .join(Message, MessageDictionary.message_id == Message.id)
            .join(DictionaryWord, MessageDictionary.word_id == DictionaryWord.id)
            .join(DictionaryCategory, DictionaryWord.category_id == DictionaryCategory.id)
            .where(
                and_(
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime,
                    DictionaryCategory.name == 'نمادها',
                    industry_expr.isnot(None)
                )
            )
            .group_by(industry_expr)
            .order_by(func.count(func.distinct(MessageDictionary.message_id)).desc())
            .limit(10)
        )
        top_industries = [
            {"name": row.industry, "count": row.count, "top_channels": []}
            for row in result
        ]

        # Get top categories (لغت‌نامه)
        result = await self.session.execute(
            select(
                DictionaryCategory.name,
                func.count(MessageDictionary.message_id).label('count')
            )
            .select_from(MessageDictionary)
            .join(Message, MessageDictionary.message_id == Message.id)
            .join(DictionaryWord, MessageDictionary.word_id == DictionaryWord.id)
            .join(DictionaryCategory, DictionaryWord.category_id == DictionaryCategory.id)
            .where(
                and_(
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime
                )
            )
            .group_by(DictionaryCategory.name)
            .order_by(func.count(MessageDictionary.message_id).desc())
            .limit(10)
        )
        top_categories = [
            {"name": row.name, "count": row.count, "top_channels": []}
            for row in result
        ]

        # Find busiest day (based on jalali_date)
        result = await self.session.execute(
            select(
                func.date(Message.created_at).label('day'),
                func.count(Message.id).label('count')
            )
            .where(
                and_(
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime
                )
            )
            .group_by(func.date(Message.created_at))
            .order_by(func.count(Message.id).desc())
            .limit(1)
        )
        busiest_day_row = result.first()
        busiest_day = None
        if busiest_day_row:
            busiest_day = {
                "date": busiest_day_row.day.isoformat(),
                "message_count": busiest_day_row.count
            }

        # Find busiest hour from message date
        result = await self.session.execute(
            select(
                func.extract('hour', Message.date).label('hour'),
                func.count(Message.id).label('count')
            )
            .where(
                and_(
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime
                )
            )
            .group_by(func.extract('hour', Message.date))
            .order_by(func.count(Message.id).desc())
            .limit(1)
        )
        busiest_hour_row = result.first()
        busiest_hour = None
        if busiest_hour_row:
            hour = int(busiest_hour_row.hour)
            busiest_hour = {
                "hour": hour,
                "hour_label": f"{hour:02d}:00 - {hour:02d}:59",
                "message_count": busiest_hour_row.count
            }

        return {
            "days": days,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "totals": {
                "messages": total_messages_global,
                "matches": total_matches_global,
                "channels": len(all_channels),
            },
            "most_active_channel": most_active_channel,
            "busiest_day": busiest_day,
            "busiest_hour": busiest_hour,
            "top_symbols": top_symbols,
            "top_industries": top_industries,
            "top_categories": top_categories,
            "all_channels": channel_stats
        }

    async def get_channel_dictionary_words(
        self,
        channel_id: uuid.UUID,
        dictionary_name: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get dictionary words used by a specific channel.

        Args:
            channel_id: Channel UUID
            dictionary_name: Name of the dictionary category
            days: Number of days to analyze

        Returns:
            List of words with their counts and extra data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Get the dictionary category ID
        result = await self.session.execute(
            select(DictionaryCategory)
            .where(DictionaryCategory.name == dictionary_name)
        )
        category = result.scalar_one_or_none()

        if not category:
            return []

        # Get all words from this category
        result = await self.session.execute(
            select(DictionaryWord)
            .where(DictionaryWord.category_id == category.id)
        )
        category_words = list(result.scalars().all())

        if not category_words:
            return []

        # Get word IDs
        word_ids = [word.id for word in category_words]

        # Query message_dictionary to find matches for this channel and these words
        result = await self.session.execute(
            select(
                DictionaryWord.word,
                DictionaryWord.extra_data,
                func.count(MessageDictionary.id).label('count')
            )
            .select_from(MessageDictionary)
            .join(Message, MessageDictionary.message_id == Message.id)
            .join(DictionaryWord, MessageDictionary.word_id == DictionaryWord.id)
            .where(
                and_(
                    Message.channel_id == channel_id,
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime,
                    DictionaryWord.id.in_(word_ids)
                )
            )
            .group_by(DictionaryWord.id, DictionaryWord.word, DictionaryWord.extra_data)
            .order_by(func.count(MessageDictionary.id).desc())
        )

        words_data = []
        for row in result:
            words_data.append({
                "word": row.word,
                "count": row.count,
                "extra_data": row.extra_data
            })

        return words_data

    async def get_channel_timeline(
        self,
        channel_id: uuid.UUID,
        days: int = 15
    ) -> Dict[str, Any]:
        """
        Get timeline analytics for a channel showing daily stats over time.

        Args:
            channel_id: Channel UUID
            days: Number of days to analyze (default 15)

        Returns:
            Timeline data with daily breakdown of messages, matches, symbols, industries, categories
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)  # Include today

        # Get analytics records for this channel and date range
        result = await self.session.execute(
            select(ChannelAnalytics)
            .where(
                and_(
                    ChannelAnalytics.channel_id == channel_id,
                    ChannelAnalytics.date >= start_date,
                    ChannelAnalytics.date <= end_date
                )
            )
            .order_by(ChannelAnalytics.date)
        )
        analytics_records = list(result.scalars().all())

        # Build timeline data
        timeline = []
        daily_symbols = {}  # {date: {symbol: count}}
        daily_industries = {}  # {date: {industry: count}}
        daily_categories = {}  # {date: {category: count}}

        # Create a record for each day (even if no data)
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()

            # Find record for this date
            record = next((r for r in analytics_records if r.date == current_date), None)

            if record:
                timeline.append({
                    "date": date_str,
                    "message_count": record.message_count,
                    "match_count": record.match_count,
                })

                # Track symbols for this day
                if record.top_symbols:
                    daily_symbols[date_str] = {s['word']: s['count'] for s in record.top_symbols[:10]}

                # Track industries for this day
                if record.top_industries:
                    daily_industries[date_str] = {i['name']: i['count'] for i in record.top_industries[:10]}

                # Track categories for this day
                if record.top_categories:
                    daily_categories[date_str] = {c['name']: c['count'] for c in record.top_categories[:10]}
            else:
                # No data for this day
                timeline.append({
                    "date": date_str,
                    "message_count": 0,
                    "match_count": 0,
                    "match_percentage": 0
                })

            current_date += timedelta(days=1)

        # Calculate aggregate stats
        total_messages = sum(day['message_count'] for day in timeline)
        total_matches = sum(day['match_count'] for day in timeline)
        avg_messages_per_day = total_messages / days if days > 0 else 0

        # Find busiest day
        busiest_day = max(timeline, key=lambda x: x['message_count']) if timeline else None

        # Aggregate symbols across all days
        all_symbols = Counter()
        for day_symbols in daily_symbols.values():
            all_symbols.update(day_symbols)

        # Aggregate industries across all days
        all_industries = Counter()
        for day_industries in daily_industries.values():
            all_industries.update(day_industries)

        # Aggregate categories across all days
        all_categories = Counter()
        for day_categories in daily_categories.values():
            all_categories.update(day_categories)

        # Build symbol timeline (top 5 symbols)
        top_symbols_list = [s[0] for s in all_symbols.most_common(5)]
        symbol_timeline = {}
        for symbol in top_symbols_list:
            symbol_timeline[symbol] = []
            for day in timeline:
                count = daily_symbols.get(day['date'], {}).get(symbol, 0)
                symbol_timeline[symbol].append({
                    "date": day['date'],
                    "count": count
                })

        # Build industry timeline (top 5 industries)
        top_industries_list = [i[0] for i in all_industries.most_common(5)]
        industry_timeline = {}
        for industry in top_industries_list:
            industry_timeline[industry] = []
            for day in timeline:
                count = daily_industries.get(day['date'], {}).get(industry, 0)
                industry_timeline[industry].append({
                    "date": day['date'],
                    "count": count
                })

        # Build category timeline (top 5 categories)
        top_categories_list = [c[0] for c in all_categories.most_common(5)]
        category_timeline = {}
        for category in top_categories_list:
            category_timeline[category] = []
            for day in timeline:
                count = daily_categories.get(day['date'], {}).get(category, 0)
                category_timeline[category].append({
                    "date": day['date'],
                    "count": count
                })

        return {
            "days": days,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_messages": total_messages,
                "total_matches": total_matches,
                "avg_messages_per_day": round(avg_messages_per_day, 2),
                "busiest_day": busiest_day
            },
            "timeline": timeline,
            "symbol_timeline": symbol_timeline,
            "industry_timeline": industry_timeline,
            "category_timeline": category_timeline
        }

    async def get_channel_hourly_activity(
        self,
        channel_id: uuid.UUID,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get hourly activity pattern for a channel.

        Args:
            channel_id: Channel UUID
            days: Number of days to analyze

        Returns:
            Hourly activity data with message counts per hour and heatmap data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Query messages grouped by hour of day
        result = await self.session.execute(
            select(
                func.extract('hour', Message.created_at).label('hour'),
                func.count(Message.id).label('count')
            )
            .where(
                and_(
                    Message.channel_id == channel_id,
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime
                )
            )
            .group_by(func.extract('hour', Message.created_at))
            .order_by(func.extract('hour', Message.created_at))
        )

        # Build hourly counts (0-23)
        hourly_counts = {i: 0 for i in range(24)}
        for row in result:
            hour = int(row.hour)
            hourly_counts[hour] = row.count

        # Build hourly data for bar chart
        hourly_data = []
        for hour in range(24):
            hourly_data.append({
                "hour": hour,
                "hour_label": f"{hour:02d}:00",
                "count": hourly_counts[hour]
            })

        # Build heatmap data (day x hour matrix)
        # Query messages grouped by date and hour
        result = await self.session.execute(
            select(
                func.date(Message.created_at).label('day'),
                func.extract('hour', Message.created_at).label('hour'),
                func.count(Message.id).label('count')
            )
            .where(
                and_(
                    Message.channel_id == channel_id,
                    Message.created_at >= start_datetime,
                    Message.created_at <= end_datetime
                )
            )
            .group_by(
                func.date(Message.created_at),
                func.extract('hour', Message.created_at)
            )
        )

        # Build heatmap matrix
        heatmap_data = {}
        for row in result:
            day_str = row.day.isoformat()
            hour = int(row.hour)
            if day_str not in heatmap_data:
                heatmap_data[day_str] = {i: 0 for i in range(24)}
            heatmap_data[day_str][hour] = row.count

        # Convert to array format for frontend
        heatmap_array = []
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            day_data = heatmap_data.get(date_str, {i: 0 for i in range(24)})
            heatmap_array.append({
                "date": date_str,
                "hours": [day_data.get(i, 0) for i in range(24)]
            })
            current_date += timedelta(days=1)

        # Find busiest hour overall
        busiest_hour = max(hourly_data, key=lambda x: x['count']) if hourly_data else None

        return {
            "days": days,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "busiest_hour": busiest_hour,
            "hourly_data": hourly_data,
            "heatmap_data": heatmap_array
        }
