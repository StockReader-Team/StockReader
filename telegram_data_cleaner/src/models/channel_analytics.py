"""
Channel analytics model for storing aggregated channel statistics.
"""
from datetime import datetime, date
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.channel import Channel


class ChannelAnalytics(BaseModel):
    """
    Represents aggregated analytics data for a channel.

    Attributes:
        channel_id: Foreign key to channel
        date: Date of the analytics record
        hour: Hour of day (0-23) for hourly aggregates, NULL for daily
        day_of_week: Day of week (0=Monday, 6=Sunday)
        message_count: Total number of messages
        match_count: Total number of matched messages
        top_symbols: Top 10 symbols mentioned (JSONB)
        top_industries: Top 10 industries mentioned (JSONB)
        top_categories: Top 10 dictionary categories (JSONB)
        channel: Relationship to Channel model
    """

    __tablename__ = "channel_analytics"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to channel",
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of the analytics record",
    )

    hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Hour of day (0-23) for hourly aggregates, NULL for daily",
    )

    time_slot: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="5-minute time slot within hour (0-11), NULL for hourly/daily aggregates",
    )

    jalali_date: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Jalali date string (e.g., '1404-08-25')",
    )

    day_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Day of week (0=Monday, 6=Sunday)",
    )

    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total number of messages",
    )

    match_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total number of matched messages",
    )

    top_symbols: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top 10 symbols mentioned: [{'id': 1, 'word': 'فولاد', 'count': 15}, ...]",
    )

    top_industries: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top 10 industries mentioned: [{'id': 1, 'name': 'فلزات', 'count': 25}, ...]",
    )

    top_categories: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top 10 dictionary categories: [{'id': 1, 'name': 'نمادها', 'count': 50}, ...]",
    )

    # Relationships
    channel: Mapped["Channel"] = relationship(
        "Channel",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("channel_id", "date", "hour", "time_slot", name="uq_channel_date_hour_slot"),
        Index("idx_channel_analytics_channel_date", "channel_id", "date"),
        Index("idx_channel_analytics_date", "date"),
    )

    def __repr__(self) -> str:
        """String representation."""
        hour_str = f", hour={self.hour}" if self.hour is not None else ""
        return f"<ChannelAnalytics(channel_id={self.channel_id}, date={self.date}{hour_str})>"
