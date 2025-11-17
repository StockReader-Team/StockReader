"""
Base model with common fields for all database models.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all database models.

    Provides declarative base for SQLAlchemy models.
    """

    pass


class UUIDMixin:
    """
    Mixin that adds a UUID primary key to a model.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamps to a model.

    Timestamps are automatically managed:
        - created_at: Set on insert
        - updated_at: Updated on every update
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Base model with UUID primary key and timestamps.

    All models should inherit from this class to get:
        - id: UUID primary key
        - created_at: Timestamp of creation
        - updated_at: Timestamp of last update
    """

    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """
        Convert model instance to dictionary.

        Returns:
            dict: Dictionary representation of the model
        """
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value
        return result

    def __repr__(self) -> str:
        """String representation of the model."""
        class_name = self.__class__.__name__
        return f"<{class_name}(id={self.id})>"
