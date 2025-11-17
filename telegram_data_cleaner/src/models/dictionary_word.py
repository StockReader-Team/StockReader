"""
Dictionary word model for storing individual words.
"""
import uuid
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import String, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.dictionary_category import DictionaryCategory
    from src.models.message import Message


class DictionaryWord(BaseModel):
    """
    Represents a word in a dictionary category.

    Attributes:
        category_id: Foreign key to dictionary category
        word: Original word
        normalized_word: Normalized word for matching
        is_active: Whether word is active for matching
        category: Relationship to DictionaryCategory
        messages: Relationship to messages containing this word
    """

    __tablename__ = "dictionary_words"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dictionary_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to dictionary category",
    )

    word: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Original word (e.g., خودروسازی، توافق)",
    )

    normalized_word: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Normalized word for matching (e.g., خودروساز, توافق)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether word is active for matching",
    )

    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional data (e.g., symbol_name, company_name, industry_name)",
    )

    # Relationships
    category: Mapped["DictionaryCategory"] = relationship(
        "DictionaryCategory",
        back_populates="words",
        lazy="selectin",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        secondary="message_dictionaries",
        back_populates="dictionary_words",
        lazy="select",
    )

    # Composite index for efficient lookup
    __table_args__ = (
        Index("idx_category_word", "category_id", "normalized_word"),
        Index("idx_word_active", "normalized_word", "is_active"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<DictionaryWord(id={self.id}, word='{self.word}')>"
