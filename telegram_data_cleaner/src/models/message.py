"""
Message model for storing Telegram messages.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import String, Text, BigInteger, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.channel import Channel
    from src.models.tag import Tag
    from src.models.dictionary_word import DictionaryWord


class Message(BaseModel):
    """
    Represents a Telegram message.

    Attributes:
        telegram_message_id: Original Telegram message ID
        channel_id: Foreign key to channel
        text: Original message text
        text_normalized: Normalized text (processed with hazm)
        date: Message publish date
        views: Number of views
        forwards: Number of forwards
        extra_data: Additional metadata as JSON
        channel: Relationship to Channel model
        tags: Relationship to Tag model (many-to-many)
    """

    __tablename__ = "messages"

    api_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="API database message ID",
    )

    telegram_message_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Original Telegram message ID from channel",
    )

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to channel",
    )

    text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Original message text",
    )

    text_normalized: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Normalized message text (processed with hazm)",
    )

    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Message publish date",
    )

    views: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of views",
    )

    forwards: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of forwards",
    )

    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata as JSON",
    )

    # Relationships
    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="messages",
        lazy="selectin",
    )

    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="message_tags",
        back_populates="messages",
        lazy="select",
    )

    dictionary_words: Mapped[list["DictionaryWord"]] = relationship(
        "DictionaryWord",
        secondary="message_dictionaries",
        back_populates="messages",
        lazy="select",
    )

    # Composite index for efficient queries
    __table_args__ = (
        Index("idx_channel_date", "channel_id", "date"),
        Index("idx_channel_telegram_id", "channel_id", "telegram_message_id", unique=True),
    )

    def __repr__(self) -> str:
        """String representation."""
        text_preview = self.text[:50] if self.text else "No text"
        return f"<Message(id={self.id}, channel_id={self.channel_id}, text='{text_preview}...')>"
