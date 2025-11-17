"""
Association table for many-to-many relationship between Message and Tag.
"""
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class MessageTag(Base):
    """
    Association table linking messages to tags.

    Attributes:
        message_id: Foreign key to message
        tag_id: Foreign key to tag
        matched_at: Timestamp when tag was matched to message
    """

    __tablename__ = "message_tags"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to message",
    )

    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to tag",
    )

    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when tag was matched",
    )

    __table_args__ = (
        UniqueConstraint("message_id", "tag_id", name="uq_message_tag"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<MessageTag(message_id={self.message_id}, tag_id={self.tag_id})>"
