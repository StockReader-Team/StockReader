"""
Dictionary model for storing word lists.
"""
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel

if TYPE_CHECKING:
    from src.models.dictionary_category import DictionaryCategory


class Dictionary(BaseModel):
    """
    Represents a dictionary (لغت‌نامه).

    Examples:
    - لغت‌نامه سیاسی
    - لغت‌نامه نمادها
    - لغت‌نامه مالی

    Attributes:
        name: Dictionary name
        description: Dictionary description
        is_active: Whether dictionary is active
        categories: Relationship to DictionaryCategory
    """

    __tablename__ = "dictionaries"

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Dictionary name (e.g., لغت‌نامه سیاسی)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Dictionary description",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether dictionary is active",
    )

    # Relationships
    categories: Mapped[list["DictionaryCategory"]] = relationship(
        "DictionaryCategory",
        back_populates="dictionary",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Dictionary(id={self.id}, name='{self.name}')>"
