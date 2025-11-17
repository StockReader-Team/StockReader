"""
Channel model for storing Telegram channel information.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.category import Category
    from src.models.message import Message


class Channel(BaseModel):
    """
    Represents a Telegram channel.

    Attributes:
        telegram_id: Unique Telegram channel ID
        name: Channel name
        username: Channel username (without @)
        category_id: Foreign key to category
        is_active: Whether channel is currently being monitored
        last_sync: Last time channel was synced
        category: Relationship to Category model
        messages: Relationship to Message model
    """

    __tablename__ = "channels"

    telegram_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique Telegram channel ID",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Channel name",
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Channel username without @",
    )

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foreign key to category",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether channel is currently being monitored",
    )

    last_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time channel was synced",
    )

    # Relationships
    category: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="channels",
        lazy="selectin",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Channel(id={self.id}, name='{self.name}', telegram_id='{self.telegram_id}')>"
