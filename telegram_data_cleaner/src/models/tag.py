"""
Tag model for categorizing and filtering messages.
"""
import enum
from typing import TYPE_CHECKING, Optional, Any

from sqlalchemy import String, Text, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.message import Message


class TagType(str, enum.Enum):
    """
    Enum for different types of tags.
    """

    CHARACTER_COUNT = "CHARACTER_COUNT"
    WORD_COUNT = "WORD_COUNT"
    CUSTOM = "CUSTOM"


class Tag(BaseModel):
    """
    Represents a tag for categorizing messages.

    Tags can be used to filter and categorize messages based on various criteria.

    Attributes:
        name: Tag name (unique)
        tag_type: Type of tag (CHARACTER_COUNT, WORD_COUNT, CUSTOM)
        condition: JSON condition for matching messages
        description: Tag description
        is_active: Whether tag is currently active
        messages: Relationship to Message model (many-to-many)
    """

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Tag name",
    )

    tag_type: Mapped[TagType] = mapped_column(
        SQLEnum(TagType, name="tag_type_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Type of tag",
    )

    condition: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON condition for matching messages",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Tag description",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether tag is currently active",
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        secondary="message_tags",
        back_populates="tags",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Tag(id={self.id}, name='{self.name}', type={self.tag_type})>"
