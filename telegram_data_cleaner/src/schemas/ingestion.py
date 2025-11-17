"""
Pydantic schemas for API ingestion.
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator


class APIChannelInfoSchema(BaseModel):
    """
    Schema for channel info nested in message.
    """

    id: int = Field(..., description="Channel ID")
    name: str = Field(..., min_length=1, max_length=255, description="Channel name")
    username: Optional[str] = Field(None, max_length=255, description="Channel username")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Trim and validate name."""
        return v.strip()

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Clean username (remove @ if present)."""
        if v is not None:
            v = v.strip()
            if v.startswith('@'):
                v = v[1:]
            if not v:
                return None
        return v


class APIMessageSchema(BaseModel):
    """
    Schema for a single message from API response.

    Maps to the actual external API structure.
    """

    id: int = Field(..., description="Message record ID")
    message_id: int = Field(..., description="Telegram message ID")
    channel: APIChannelInfoSchema = Field(..., description="Channel information")
    text: Optional[str] = Field(None, description="Message text")
    date: datetime = Field(..., description="Message date (ISO format)")
    jalali_date: Optional[str] = Field(None, description="Jalali date string")
    views_count: Optional[int] = Field(None, ge=0, description="View count")
    forwards_count: Optional[int] = Field(None, ge=0, description="Forward count")
    replies_count: Optional[int] = Field(None, ge=0, description="Replies count")

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: Optional[str]) -> Optional[str]:
        """Trim and validate text."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class APIResponseSchema(BaseModel):
    """
    Complete API response schema.

    Matches actual API structure:
    {
      "limit": 100,
      "offset": null,
      "total": 25089,
      "messages": [...]
    }
    """

    limit: int = Field(100, ge=1, description="Number of items per page")
    offset: Optional[int] = Field(None, ge=0, description="Offset for pagination")
    total: int = Field(0, ge=0, description="Total messages available")
    messages: List[APIMessageSchema] = Field(default_factory=list, description="Messages list")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "channels": [
                    {
                        "id": 123,
                        "name": "کانال تست",
                        "username": "test_channel",
                        "category": "اخبار",
                        "messages": [
                            {
                                "id": 456,
                                "text": "متن پیام",
                                "date": "2025-11-15T10:30:00Z",
                                "views": 1000,
                                "forwards": 50
                            }
                        ]
                    }
                ],
                "total": 100,
                "page": 1
            }
        }


class IngestionStatsSchema(BaseModel):
    """
    Statistics for an ingestion operation.
    """

    channels_processed: int = Field(0, ge=0)
    channels_inserted: int = Field(0, ge=0)
    channels_updated: int = Field(0, ge=0)
    messages_processed: int = Field(0, ge=0)
    messages_inserted: int = Field(0, ge=0)
    messages_updated: int = Field(0, ge=0)
    messages_skipped: int = Field(0, ge=0)
    duration_seconds: float = Field(0.0, ge=0.0)
    errors: int = Field(0, ge=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "channels": {
                "processed": self.channels_processed,
                "inserted": self.channels_inserted,
                "updated": self.channels_updated,
            },
            "messages": {
                "processed": self.messages_processed,
                "inserted": self.messages_inserted,
                "updated": self.messages_updated,
                "skipped": self.messages_skipped,
            },
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
        }


class SyncStatusSchema(BaseModel):
    """
    Current sync status.
    """

    is_running: bool = Field(False)
    last_sync: Optional[datetime] = Field(None)
    last_success: Optional[datetime] = Field(None)
    last_error: Optional[str] = Field(None)
    last_stats: Optional[IngestionStatsSchema] = Field(None)
    next_scheduled: Optional[datetime] = Field(None)
