"""
API routes for dictionary management.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, delete, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import db_manager
from src.models.dictionary import Dictionary
from src.models.dictionary_category import DictionaryCategory
from src.models.dictionary_word import DictionaryWord
from src.models.message_dictionary import MessageDictionary
from src.models.message import Message
from src.models.channel import Channel
from src.core.processing.text_normalizer import TextNormalizer
from src.schemas.dictionary import (
    DictionaryCreateSchema,
    DictionaryUpdateSchema,
    DictionarySchema,
    DictionaryCategoryCreateSchema,
    DictionaryCategoryUpdateSchema,
    DictionaryCategorySchema,
    DictionaryWordCreateSchema,
    DictionaryWordBulkCreateSchema,
    DictionaryWordUpdateSchema,
    DictionaryWordSchema,
    DictionaryStatsSchema,
)

router = APIRouter(prefix="/dictionary", tags=["Dictionary Management"])

# Initialize text normalizer for word normalization
text_normalizer = TextNormalizer()


# ============= Dictionary Endpoints =============

@router.post("/dictionaries", response_model=DictionarySchema, status_code=status.HTTP_201_CREATED)
async def create_dictionary(data: DictionaryCreateSchema):
    """Create a new dictionary."""
    async with db_manager.session() as session:
        # Check if name already exists
        result = await session.execute(
            select(Dictionary).where(Dictionary.name == data.name)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dictionary with name '{data.name}' already exists"
            )

        dictionary = Dictionary(
            name=data.name,
            description=data.description,
            is_active=data.is_active
        )
        session.add(dictionary)
        await session.commit()
        await session.refresh(dictionary)

        return dictionary


@router.get("/dictionaries", response_model=List[DictionarySchema])
async def list_dictionaries(active_only: bool = False):
    """List all dictionaries."""
    async with db_manager.session() as session:
        stmt = select(Dictionary)
        if active_only:
            stmt = stmt.where(Dictionary.is_active == True)
        stmt = stmt.order_by(Dictionary.name)

        result = await session.execute(stmt)
        return list(result.scalars().all())


@router.get("/dictionaries/{dictionary_id}", response_model=DictionarySchema)
async def get_dictionary(dictionary_id: UUID):
    """Get a specific dictionary by ID."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(Dictionary).where(Dictionary.id == dictionary_id)
        )
        dictionary = result.scalar_one_or_none()

        if not dictionary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dictionary {dictionary_id} not found"
            )

        return dictionary


@router.patch("/dictionaries/{dictionary_id}", response_model=DictionarySchema)
async def update_dictionary(dictionary_id: UUID, data: DictionaryUpdateSchema):
    """Update a dictionary."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(Dictionary).where(Dictionary.id == dictionary_id)
        )
        dictionary = result.scalar_one_or_none()

        if not dictionary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dictionary {dictionary_id} not found"
            )

        # Update fields
        if data.name is not None:
            dictionary.name = data.name
        if data.description is not None:
            dictionary.description = data.description
        if data.is_active is not None:
            dictionary.is_active = data.is_active

        await session.commit()
        await session.refresh(dictionary)

        return dictionary


@router.delete("/dictionaries/{dictionary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dictionary(dictionary_id: UUID):
    """Delete a dictionary (cascades to categories and words)."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(Dictionary).where(Dictionary.id == dictionary_id)
        )
        dictionary = result.scalar_one_or_none()

        if not dictionary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dictionary {dictionary_id} not found"
            )

        await session.delete(dictionary)
        await session.commit()


# ============= Category Endpoints =============

@router.post("/categories", response_model=DictionaryCategorySchema, status_code=status.HTTP_201_CREATED)
async def create_category(data: DictionaryCategoryCreateSchema):
    """Create a new dictionary category."""
    async with db_manager.session() as session:
        # Verify dictionary exists
        result = await session.execute(
            select(Dictionary).where(Dictionary.id == data.dictionary_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dictionary {data.dictionary_id} not found"
            )

        # Verify parent exists if provided
        if data.parent_id:
            result = await session.execute(
                select(DictionaryCategory).where(DictionaryCategory.id == data.parent_id)
            )
            if not result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent category {data.parent_id} not found"
                )

        category = DictionaryCategory(
            dictionary_id=data.dictionary_id,
            name=data.name,
            parent_id=data.parent_id,
            description=data.description
        )
        session.add(category)
        await session.commit()
        await session.refresh(category)

        return category


@router.get("/categories", response_model=List[DictionaryCategorySchema])
async def list_categories(dictionary_id: UUID = None):
    """List all categories, optionally filtered by dictionary."""
    async with db_manager.session() as session:
        stmt = select(DictionaryCategory)
        if dictionary_id:
            stmt = stmt.where(DictionaryCategory.dictionary_id == dictionary_id)
        stmt = stmt.order_by(DictionaryCategory.name)

        result = await session.execute(stmt)
        return list(result.scalars().all())


@router.get("/categories/{category_id}", response_model=DictionaryCategorySchema)
async def get_category(category_id: UUID):
    """Get a specific category by ID."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(DictionaryCategory).where(DictionaryCategory.id == category_id)
        )
        category = result.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category {category_id} not found"
            )

        return category


@router.patch("/categories/{category_id}", response_model=DictionaryCategorySchema)
async def update_category(category_id: UUID, data: DictionaryCategoryUpdateSchema):
    """Update a category."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(DictionaryCategory).where(DictionaryCategory.id == category_id)
        )
        category = result.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category {category_id} not found"
            )

        # Update fields
        if data.name is not None:
            category.name = data.name
        if data.parent_id is not None:
            category.parent_id = data.parent_id
        if data.description is not None:
            category.description = data.description

        await session.commit()
        await session.refresh(category)

        return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID):
    """Delete a category (cascades to words)."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(DictionaryCategory).where(DictionaryCategory.id == category_id)
        )
        category = result.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category {category_id} not found"
            )

        await session.delete(category)
        await session.commit()


# ============= Word Endpoints =============

@router.post("/words", response_model=DictionaryWordSchema, status_code=status.HTTP_201_CREATED)
async def create_word(data: DictionaryWordCreateSchema):
    """Create a new dictionary word."""
    async with db_manager.session() as session:
        # Verify category exists
        result = await session.execute(
            select(DictionaryCategory).where(DictionaryCategory.id == data.category_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category {data.category_id} not found"
            )

        # Auto-normalize word if not provided
        normalized_word = data.normalized_word or text_normalizer.normalize(data.word)

        word = DictionaryWord(
            category_id=data.category_id,
            word=data.word,
            normalized_word=normalized_word,
            is_active=data.is_active,
            extra_data=data.extra_data
        )
        session.add(word)
        await session.commit()
        await session.refresh(word)

        return word


@router.post("/words/bulk", response_model=List[DictionaryWordSchema], status_code=status.HTTP_201_CREATED)
async def create_words_bulk(data: DictionaryWordBulkCreateSchema):
    """Create multiple dictionary words at once."""
    async with db_manager.session() as session:
        # Verify category exists
        result = await session.execute(
            select(DictionaryCategory).where(DictionaryCategory.id == data.category_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category {data.category_id} not found"
            )

        created_words = []
        for word_text in data.words:
            normalized_word = text_normalizer.normalize(word_text)
            word = DictionaryWord(
                category_id=data.category_id,
                word=word_text,
                normalized_word=normalized_word,
                is_active=data.is_active
            )
            session.add(word)
            created_words.append(word)

        await session.commit()

        # Refresh all words
        for word in created_words:
            await session.refresh(word)

        return created_words


@router.get("/words", response_model=List[DictionaryWordSchema])
async def list_words(category_id: UUID = None, active_only: bool = False):
    """List all words, optionally filtered by category."""
    async with db_manager.session() as session:
        stmt = select(DictionaryWord)
        if category_id:
            stmt = stmt.where(DictionaryWord.category_id == category_id)
        if active_only:
            stmt = stmt.where(DictionaryWord.is_active == True)
        stmt = stmt.order_by(DictionaryWord.word)

        result = await session.execute(stmt)
        return list(result.scalars().all())


@router.get("/words/{word_id}", response_model=DictionaryWordSchema)
async def get_word(word_id: UUID):
    """Get a specific word by ID."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(DictionaryWord).where(DictionaryWord.id == word_id)
        )
        word = result.scalar_one_or_none()

        if not word:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Word {word_id} not found"
            )

        return word


@router.patch("/words/{word_id}", response_model=DictionaryWordSchema)
async def update_word(word_id: UUID, data: DictionaryWordUpdateSchema):
    """Update a word."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(DictionaryWord).where(DictionaryWord.id == word_id)
        )
        word = result.scalar_one_or_none()

        if not word:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Word {word_id} not found"
            )

        # Update fields
        if data.word is not None:
            word.word = data.word
            # Re-normalize if word changed
            word.normalized_word = text_normalizer.normalize(data.word)
        if data.normalized_word is not None:
            word.normalized_word = data.normalized_word
        if data.is_active is not None:
            word.is_active = data.is_active
        if data.extra_data is not None:
            word.extra_data = data.extra_data

        await session.commit()
        await session.refresh(word)

        return word


@router.delete("/words/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_word(word_id: UUID):
    """Delete a word."""
    async with db_manager.session() as session:
        result = await session.execute(
            select(DictionaryWord).where(DictionaryWord.id == word_id)
        )
        word = result.scalar_one_or_none()

        if not word:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Word {word_id} not found"
            )

        await session.delete(word)
        await session.commit()


# ============= Statistics Endpoint =============

@router.get("/stats", response_model=DictionaryStatsSchema)
async def get_dictionary_stats():
    """Get dictionary system statistics."""
    async with db_manager.session() as session:
        # Total dictionaries
        result = await session.execute(select(func.count(Dictionary.id)))
        total_dictionaries = result.scalar_one()

        # Active dictionaries
        result = await session.execute(
            select(func.count(Dictionary.id)).where(Dictionary.is_active == True)
        )
        active_dictionaries = result.scalar_one()

        # Total categories
        result = await session.execute(select(func.count(DictionaryCategory.id)))
        total_categories = result.scalar_one()

        # Total words
        result = await session.execute(select(func.count(DictionaryWord.id)))
        total_words = result.scalar_one()

        # Active words
        result = await session.execute(
            select(func.count(DictionaryWord.id)).where(DictionaryWord.is_active == True)
        )
        active_words = result.scalar_one()

        # Total matches
        result = await session.execute(select(func.count(MessageDictionary.message_id)))
        total_matches = result.scalar_one()

        return DictionaryStatsSchema(
            total_dictionaries=total_dictionaries,
            active_dictionaries=active_dictionaries,
            total_categories=total_categories,
            total_words=total_words,
            active_words=active_words,
            total_matches=total_matches
        )

# ============= Matching Results Endpoints =============

@router.get("/matches/stats")
async def get_match_stats():
    """Get matching statistics."""
    async with db_manager.session() as session:
        # Total messages
        result = await session.execute(select(func.count(Message.id)))
        total_messages = result.scalar_one()

        # Messages with matches
        result = await session.execute(
            select(func.count(distinct(MessageDictionary.message_id)))
        )
        matched_messages = result.scalar_one()

        # Total matches
        result = await session.execute(select(func.count()).select_from(MessageDictionary))
        total_matches = result.scalar_one()

        # Unique words matched
        result = await session.execute(
            select(func.count(distinct(MessageDictionary.word_id)))
        )
        unique_words = result.scalar_one()

        return {
            "total_messages": total_messages,
            "matched_messages": matched_messages,
            "total_matches": total_matches,
            "unique_words": unique_words
        }


@router.get("/matches")
async def get_matches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    dictionary_id: Optional[UUID] = None,
    word: Optional[str] = None
):
    """Get messages with matched words."""
    async with db_manager.session() as session:
        # First, get unique message IDs that have matches
        subquery = select(distinct(MessageDictionary.message_id))

        # Apply filters on subquery
        if dictionary_id or word:
            subquery = subquery.join(DictionaryWord, MessageDictionary.word_id == DictionaryWord.id)
            if dictionary_id:
                subquery = subquery.join(DictionaryCategory, DictionaryWord.category_id == DictionaryCategory.id)
                subquery = subquery.where(DictionaryCategory.dictionary_id == dictionary_id)
            if word:
                subquery = subquery.where(DictionaryWord.word.ilike(f'%{word}%'))

        subquery = subquery.subquery()

        # Count total
        count_result = await session.execute(select(func.count()).select_from(subquery))
        total = count_result.scalar_one()

        # Get paginated messages
        offset = (page - 1) * page_size
        query = (
            select(Message, Channel)
            .join(Channel, Message.channel_id == Channel.id)
            .where(Message.id.in_(select(subquery)))
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await session.execute(query)
        messages_with_channels = result.all()

        # Get words for each message
        items = []
        for message, channel in messages_with_channels:
            # Get all matched words for this message
            words_query = (
                select(DictionaryWord)
                .join(MessageDictionary, DictionaryWord.id == MessageDictionary.word_id)
                .where(MessageDictionary.message_id == message.id)
            )
            words_result = await session.execute(words_query)
            matched_words = words_result.scalars().all()

            items.append({
                "message_id": str(message.id),
                "text": message.text or message.text_normalized,
                "channel_name": channel.name,
                "created_at": message.created_at.isoformat(),
                "words": [
                    {
                        "id": str(word.id),
                        "word": word.word,
                        "extra_data": word.extra_data
                    }
                    for word in matched_words
                ]
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
