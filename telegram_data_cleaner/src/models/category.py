"""
Category model for organizing channels.
"""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.channel import Channel


class Category(BaseModel):
    """
    Represents a category for organizing channels.

    Supports hierarchical structure with parent-child relationships.

    Attributes:
        name: Category name (unique)
        parent_id: Foreign key to parent category (self-referential)
        description: Category description
        parent: Relationship to parent category
        children: Relationship to child categories
        channels: Relationship to channels in this category
    """

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Category name",
    )

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Foreign key to parent category",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Category description",
    )

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
        lazy="selectin",
    )

    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="select",
    )

    channels: Mapped[list["Channel"]] = relationship(
        "Channel",
        back_populates="category",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Category(id={self.id}, name='{self.name}')>"
