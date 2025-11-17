"""
Pydantic schemas for dictionary management.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# Dictionary Schemas
class DictionaryCreateSchema(BaseModel):
    """Schema for creating a new dictionary."""
    name: str = Field(..., min_length=1, max_length=255, description="Dictionary name")
    description: Optional[str] = Field(None, description="Dictionary description")
    is_active: bool = Field(True, description="Whether dictionary is active")


class DictionaryUpdateSchema(BaseModel):
    """Schema for updating a dictionary."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DictionarySchema(BaseModel):
    """Schema for dictionary response."""
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Dictionary Category Schemas
class DictionaryCategoryCreateSchema(BaseModel):
    """Schema for creating a dictionary category."""
    dictionary_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[UUID] = None
    description: Optional[str] = None


class DictionaryCategoryUpdateSchema(BaseModel):
    """Schema for updating a dictionary category."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[UUID] = None
    description: Optional[str] = None


class DictionaryCategorySchema(BaseModel):
    """Schema for dictionary category response."""
    id: UUID
    dictionary_id: UUID
    name: str
    parent_id: Optional[UUID]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Dictionary Word Schemas
class DictionaryWordCreateSchema(BaseModel):
    """Schema for creating a dictionary word."""
    category_id: UUID
    word: str = Field(..., min_length=1, max_length=255, description="Original word")
    normalized_word: Optional[str] = Field(None, description="Normalized word (auto-generated if not provided)")
    is_active: bool = Field(True, description="Whether word is active for matching")
    extra_data: Optional[dict] = Field(None, description="Additional data (e.g., symbol_name, company_name, industry_name)")


class DictionaryWordBulkCreateSchema(BaseModel):
    """Schema for bulk creating dictionary words."""
    category_id: UUID
    words: List[str] = Field(..., min_items=1, description="List of words to add")
    is_active: bool = Field(True, description="Whether words are active for matching")


class DictionaryWordUpdateSchema(BaseModel):
    """Schema for updating a dictionary word."""
    word: Optional[str] = Field(None, min_length=1, max_length=255)
    normalized_word: Optional[str] = None
    is_active: Optional[bool] = None
    extra_data: Optional[dict] = None


class DictionaryWordSchema(BaseModel):
    """Schema for dictionary word response."""
    id: UUID
    category_id: UUID
    word: str
    normalized_word: str
    is_active: bool
    extra_data: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Stats Schema
class DictionaryStatsSchema(BaseModel):
    """Schema for dictionary statistics."""
    total_dictionaries: int
    active_dictionaries: int
    total_categories: int
    total_words: int
    active_words: int
    total_matches: int
