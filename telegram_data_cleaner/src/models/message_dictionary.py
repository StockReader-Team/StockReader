"""
Association table between messages and dictionary words.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class MessageDictionary(Base):
    """
    Association table linking messages to matched dictionary words.

    This is a many-to-many relationship table that stores which
    dictionary words were found in which messages.

    Attributes:
        message_id: Foreign key to message
        word_id: Foreign key to dictionary word
        matched_at: When the match was made
    """

    __tablename__ = "message_dictionaries"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to message",
    )

    word_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dictionary_words.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to dictionary word",
    )

    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the match was made",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<MessageDictionary(message_id={self.message_id}, word_id={self.word_id})>"
