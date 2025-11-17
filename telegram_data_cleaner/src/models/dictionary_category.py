"""
Dictionary category model for organizing words.
"""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.dictionary import Dictionary
    from src.models.dictionary_word import DictionaryWord


class DictionaryCategory(BaseModel):
    """
    Represents a category within a dictionary (زیردسته لغت‌نامه).

    Supports hierarchical structure with parent-child relationships.

    Examples:
    - Dictionary: "لغت‌نامه سیاسی"
      ├─ Category: "مثبت" (توافق، صلح)
      └─ Category: "منفی" (جنگ، تحریم)

    - Dictionary: "لغت‌نامه نمادها"
      ├─ Category: "نماد"
      ├─ Category: "صنعت"
      └─ Category: "اسم شرکت"

    Attributes:
        dictionary_id: Foreign key to dictionary
        name: Category name
        parent_id: Foreign key to parent category (self-referential)
        description: Category description
        dictionary: Relationship to Dictionary
        parent: Relationship to parent category
        children: Relationship to child categories
        words: Relationship to words in this category
    """

    __tablename__ = "dictionary_categories"

    dictionary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to dictionary",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Category name (e.g., مثبت، منفی، نماد)",
    )

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dictionary_categories.id", ondelete="CASCADE"),
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
    dictionary: Mapped["Dictionary"] = relationship(
        "Dictionary",
        back_populates="categories",
        lazy="selectin",
    )

    parent: Mapped[Optional["DictionaryCategory"]] = relationship(
        "DictionaryCategory",
        remote_side="DictionaryCategory.id",
        back_populates="children",
        lazy="selectin",
    )

    children: Mapped[list["DictionaryCategory"]] = relationship(
        "DictionaryCategory",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="select",
    )

    words: Mapped[list["DictionaryWord"]] = relationship(
        "DictionaryWord",
        back_populates="category",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<DictionaryCategory(id={self.id}, name='{self.name}')>"
