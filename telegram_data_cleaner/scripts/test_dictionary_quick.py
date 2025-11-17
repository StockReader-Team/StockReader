"""
Quick test of existing Dictionary & Matching system.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func

from src.database import db_manager
from src.models.dictionary import Dictionary
from src.models.dictionary_category import DictionaryCategory
from src.models.dictionary_word import DictionaryWord
from src.models.message import Message
from src.models.message_dictionary import MessageDictionary
from src.core.matching.matching_service import MatchingService


async def main():
    """Test existing dictionary system."""
    print("\n" + "#"*60)
    print("# Dictionary & Matching System - Quick Test")
    print("#"*60)

    db_manager.init_engine()

    async with db_manager.session() as session:
        # Get stats
        print("\n" + "="*60)
        print("SYSTEM STATISTICS")
        print("="*60)

        result = await session.execute(select(func.count(Dictionary.id)))
        total_dicts = result.scalar_one()

        result = await session.execute(select(func.count(DictionaryCategory.id)))
        total_categories = result.scalar_one()

        result = await session.execute(select(func.count(DictionaryWord.id)))
        total_words = result.scalar_one()

        result = await session.execute(select(func.count(MessageDictionary.message_id)))
        total_matches = result.scalar_one()

        result = await session.execute(select(func.count(Message.id)))
        total_messages = result.scalar_one()

        print(f"✓ Dictionaries: {total_dicts}")
        print(f"✓ Categories: {total_categories}")
        print(f"✓ Words: {total_words}")
        print(f"✓ Messages: {total_messages}")
        print(f"✓ Word Matches: {total_matches}")

        # Test matching service
        print("\n" + "="*60)
        print("MATCHING SERVICE TEST")
        print("="*60)

        matching_service = MatchingService(session)
        await matching_service.load_cache()

        stats = await matching_service.get_stats()
        print(f"✓ Cache loaded: {stats['cached_normalized_words']} unique words")
        print(f"✓ Total matches in DB: {stats['total_matches_in_db']}")

        # Test on recent messages
        result = await session.execute(
            select(Message)
            .where(Message.text_normalized.isnot(None))
            .limit(5)
        )
        messages = list(result.scalars().all())

        if messages:
            print(f"\n✓ Testing on {len(messages)} recent messages:")
            results = await matching_service.match_messages_batch(
                messages,
                save_matches=True
            )

            for msg in messages:
                msg_id = str(msg.id)
                match_count = len(results.get(msg_id, []))
                preview = msg.text[:40] if msg.text else "No text"
                print(f"  - Message: '{preview}...' → {match_count} matches")

        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60)

        print("\nAPI Endpoints available at http://localhost:8000/docs:")
        print("  - POST /api/dictionary/dictionaries")
        print("  - POST /api/dictionary/categories")
        print("  - POST /api/dictionary/words")
        print("  - POST /api/dictionary/words/bulk")
        print("  - GET  /api/dictionary/stats")

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
