"""
Matching service for detecting dictionary words in messages.
"""
import logging
from typing import Dict, List, Set, Optional
from datetime import datetime
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dictionary import Dictionary
from src.models.dictionary_word import DictionaryWord
from src.models.message import Message
from src.models.message_dictionary import MessageDictionary
from src.core.processing.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


class MatchingService:
    """
    Service for matching dictionary words against message text.

    Features:
    - In-memory caching of active dictionary words
    - Fast text matching using normalized text
    - Batch processing support
    - Automatic cache refresh
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the matching service.

        Args:
            session: Database session
        """
        self.session = session
        self.text_normalizer = TextNormalizer()

        # Cache structure: {normalized_word: [word_id1, word_id2, ...]}
        # Multiple word_ids can map to same normalized form
        self._word_cache: Dict[str, List[str]] = {}
        self._cache_loaded = False

    async def load_cache(self, force_reload: bool = False) -> None:
        """
        Load active dictionary words into memory cache.

        Args:
            force_reload: If True, reload even if cache already loaded
        """
        if self._cache_loaded and not force_reload:
            return

        logger.info("Loading dictionary words into cache...")

        # Query all active words from active dictionaries
        stmt = (
            select(DictionaryWord)
            .join(DictionaryWord.category)
            .join(Dictionary)
            .where(
                DictionaryWord.is_active == True,
                Dictionary.is_active == True
            )
        )

        result = await self.session.execute(stmt)
        words = result.scalars().all()

        # Build cache
        word_cache = defaultdict(list)
        for word in words:
            word_cache[word.normalized_word].append(str(word.id))

        self._word_cache = dict(word_cache)
        self._cache_loaded = True

        logger.info(f"Loaded {len(words)} dictionary words ({len(self._word_cache)} unique normalized forms)")

    async def match_message(
        self,
        message: Message,
        save_matches: bool = True
    ) -> List[str]:
        """
        Match dictionary words in a single message.

        Args:
            message: Message to match
            save_matches: If True, save matches to database

        Returns:
            List of matched word IDs
        """
        if not self._cache_loaded:
            await self.load_cache()

        if not message.text_normalized:
            return []

        # Find matching words
        matched_word_ids = set()

        # Split normalized text into tokens
        tokens = message.text_normalized.split()

        for token in tokens:
            if token in self._word_cache:
                # Add all word IDs that match this normalized form
                matched_word_ids.update(self._word_cache[token])

        if not matched_word_ids:
            return []

        logger.debug(f"Message {message.id}: Found {len(matched_word_ids)} matching words")

        # Save matches to database
        if save_matches:
            await self._save_matches(message.id, list(matched_word_ids))

        return list(matched_word_ids)

    async def match_messages_batch(
        self,
        messages: List[Message],
        save_matches: bool = True
    ) -> Dict[str, List[str]]:
        """
        Match dictionary words in multiple messages (batch processing).

        Args:
            messages: List of messages to match
            save_matches: If True, save matches to database

        Returns:
            Dict mapping message_id to list of matched word IDs
        """
        if not self._cache_loaded:
            await self.load_cache()

        results = {}
        all_matches = []

        for message in messages:
            if not message.text_normalized:
                results[str(message.id)] = []
                continue

            matched_word_ids = set()
            tokens = message.text_normalized.split()

            for token in tokens:
                if token in self._word_cache:
                    matched_word_ids.update(self._word_cache[token])

            results[str(message.id)] = list(matched_word_ids)

            # Prepare batch insert data
            for word_id in matched_word_ids:
                all_matches.append({
                    "message_id": str(message.id),
                    "word_id": word_id
                })

        logger.info(
            f"Batch matched {len(messages)} messages: "
            f"Found {len(all_matches)} total matches"
        )

        # Save all matches in one go
        if save_matches and all_matches:
            await self._save_matches_batch(all_matches)

        return results

    async def _save_matches(
        self,
        message_id: str,
        word_ids: List[str]
    ) -> None:
        """
        Save word matches for a single message.

        Args:
            message_id: Message UUID
            word_ids: List of matched word UUIDs
        """
        # Delete existing matches
        delete_stmt = select(MessageDictionary).where(
            MessageDictionary.message_id == message_id
        )
        result = await self.session.execute(delete_stmt)
        existing = result.scalars().all()

        for match in existing:
            await self.session.delete(match)

        # Insert new matches
        for word_id in word_ids:
            match = MessageDictionary(
                message_id=UUID(message_id) if isinstance(message_id, str) else message_id,
                word_id=UUID(word_id) if isinstance(word_id, str) else word_id
            )
            self.session.add(match)

        await self.session.commit()

    async def _save_matches_batch(
        self,
        matches: List[Dict[str, str]]
    ) -> None:
        """
        Save word matches for multiple messages in batch.

        Args:
            matches: List of dicts with message_id and word_id
        """
        # Get unique message IDs
        message_ids = list(set(m["message_id"] for m in matches))

        # Delete existing matches for these messages
        delete_stmt = select(MessageDictionary).where(
            MessageDictionary.message_id.in_(message_ids)
        )
        result = await self.session.execute(delete_stmt)
        existing = result.scalars().all()

        for match in existing:
            await self.session.delete(match)

        # Insert new matches
        for match_data in matches:
            msg_id = match_data["message_id"]
            w_id = match_data["word_id"]
            match = MessageDictionary(
                message_id=UUID(msg_id) if isinstance(msg_id, str) else msg_id,
                word_id=UUID(w_id) if isinstance(w_id, str) else w_id
            )
            self.session.add(match)

        await self.session.commit()

    async def get_message_matches(
        self,
        message_id: str
    ) -> List[DictionaryWord]:
        """
        Get all dictionary words matched for a message.

        Args:
            message_id: Message UUID

        Returns:
            List of matched DictionaryWord objects
        """
        stmt = (
            select(DictionaryWord)
            .join(MessageDictionary)
            .where(MessageDictionary.message_id == message_id)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self) -> Dict:
        """
        Get matching statistics.

        Returns:
            Dict with cache and matching stats
        """
        # Count total matches
        stmt = select(MessageDictionary)
        result = await self.session.execute(stmt)
        total_matches = len(result.scalars().all())

        return {
            "cache_loaded": self._cache_loaded,
            "cached_normalized_words": len(self._word_cache),
            "total_matches_in_db": total_matches
        }

    def clear_cache(self) -> None:
        """Clear the in-memory word cache."""
        self._word_cache.clear()
        self._cache_loaded = False
        logger.info("Matching cache cleared")
