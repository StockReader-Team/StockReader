"""
Sync state model for tracking message synchronization progress.
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SyncState(Base):
    """Model for tracking synchronization state."""

    __tablename__ = "sync_states"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Sync direction: 'forward' (new messages) or 'backward' (historical)
    direction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )

    # Current offset position
    current_offset: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # Total messages available at API
    total_available: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # Messages synced in this direction
    messages_synced: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # Is sync currently running
    is_running: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # Is sync completed
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # Last successful sync time
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    # Last error message
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Created timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    # Updated timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<SyncState(id={self.id}, direction={self.direction}, "
            f"offset={self.current_offset}, synced={self.messages_synced})>"
        )
