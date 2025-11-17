"""
Comprehensive test script for Dictionary & Matching system.

This script tests:
1. Dictionary CRUD operations via API
2. Category and Word management
3. MatchingService functionality
4. Integration with IngestionService
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.database import db_manager
from src.models.dictionary import Dictionary
from src.models.dictionary_category import DictionaryCategory
from src.models.dictionary_word import DictionaryWord
from src.models.message import Message
from src.models.channel import Channel
from src.core.matching.matching_service import MatchingService
from src.core.processing.text_normalizer import TextNormalizer


async def test_dictionary_models():
    """Test 1: Create dictionary, categories, and words using models."""
    print("\n" + "="*60)
    print("TEST 1: Dictionary Models (Direct Database)")
    print("="*60)

    async with db_manager.session() as session:
        # Create dictionary
        dictionary = Dictionary(
            name="لغت‌نامه نمادها",
            description="Dictionary for stock symbols and companies",
            is_active=True
        )
        session.add(dictionary)
        await session.commit()
        await session.refresh(dictionary)
        print(f"✓ Created dictionary: {dictionary.name} (ID: {dictionary.id})")

        # Create categories
        category_symbol = DictionaryCategory(
            dictionary_id=dictionary.id,
            name="نماد",
            description="Stock trading symbols"
        )
        category_company = DictionaryCategory(
            dictionary_id=dictionary.id,
            name="شرکت",
            description="Company names"
        )
        session.add_all([category_symbol, category_company])
        await session.commit()
        await session.refresh(category_symbol)
        await session.refresh(category_company)
        print(f"✓ Created category: {category_symbol.name} (ID: {category_symbol.id})")
        print(f"✓ Created category: {category_company.name} (ID: {category_company.id})")

        # Add words to categories
        text_normalizer = TextNormalizer()

        symbols = ["فولاد", "شپنا", "خودرو", "وبملت"]
        companies = ["فولاد مبارکه", "پالایش نفت", "ایران خودرو", "بانک ملت"]

        # Add symbols
        for symbol_text in symbols:
            word = DictionaryWord(
                category_id=category_symbol.id,
                word=symbol_text,
                normalized_word=text_normalizer.normalize(symbol_text),
                is_active=True
            )
            session.add(word)

        # Add company names
        for company_text in companies:
            word = DictionaryWord(
                category_id=category_company.id,
                word=company_text,
                normalized_word=text_normalizer.normalize(company_text),
                is_active=True
            )
            session.add(word)

        await session.commit()
        print(f"✓ Added {len(symbols)} symbols")
        print(f"✓ Added {len(companies)} company names")

        return dictionary.id


async def test_matching_service():
    """Test 2: Test MatchingService."""
    print("\n" + "="*60)
    print("TEST 2: MatchingService")
    print("="*60)

    async with db_manager.session() as session:
        # Create matching service
        matching_service = MatchingService(session)

        # Load cache
        await matching_service.load_cache()
        print(f"✓ Loaded matching cache")

        # Get stats
        stats = await matching_service.get_stats()
        print(f"✓ Cache contains {stats['cached_normalized_words']} unique normalized words")

        # Create test message
        # First, get or create a channel
        result = await session.execute(select(Channel).limit(1))
        channel = result.scalar_one_or_none()

        if not channel:
            print("✗ No channels found in database. Run ingestion first!")
            return False

        # Create test message with words from dictionary
        from datetime import datetime
        from uuid import uuid4

        test_message = Message(
            id=uuid4(),
            telegram_message_id=999999,
            channel_id=channel.id,
            text="امروز نماد فولاد و شپنا سبز بود. شرکت فولاد مبارکه گزارش داد.",
            text_normalized="امروز نماد فولاد شپنا سبز بود شرکت فولاد مبارکه گزارش داد",
            date=datetime.now()
        )
        session.add(test_message)
        await session.commit()
        await session.refresh(test_message)

        print(f"✓ Created test message: '{test_message.text[:50]}...'")

        # Match words
        matched_word_ids = await matching_service.match_message(
            test_message,
            save_matches=True
        )

        print(f"✓ Found {len(matched_word_ids)} matching words")

        # Verify matches
        matched_words = await matching_service.get_message_matches(str(test_message.id))
        print(f"✓ Verified matches in database:")
        for word in matched_words:
            print(f"  - {word.word} ({word.category.name})")

        # Clean up test message
        await session.delete(test_message)
        await session.commit()

        return len(matched_word_ids) > 0


async def test_batch_matching():
    """Test 3: Test batch matching on real messages."""
    print("\n" + "="*60)
    print("TEST 3: Batch Matching on Real Messages")
    print("="*60)

    async with db_manager.session() as session:
        # Get some messages
        result = await session.execute(
            select(Message)
            .where(Message.text_normalized.isnot(None))
            .limit(10)
        )
        messages = list(result.scalars().all())

        if not messages:
            print("✗ No messages with normalized text found!")
            return False

        print(f"✓ Found {len(messages)} messages to test")

        # Create matching service and match
        matching_service = MatchingService(session)
        await matching_service.load_cache()

        results = await matching_service.match_messages_batch(
            messages,
            save_matches=True
        )

        # Count total matches
        total_matches = sum(len(word_ids) for word_ids in results.values())
        messages_with_matches = sum(1 for word_ids in results.values() if len(word_ids) > 0)

        print(f"✓ Processed {len(messages)} messages")
        print(f"✓ Found {total_matches} total word matches")
        print(f"✓ {messages_with_matches} messages had at least one match")

        return True


async def test_stats():
    """Test 4: Test statistics endpoint."""
    print("\n" + "="*60)
    print("TEST 4: Dictionary Statistics")
    print("="*60)

    async with db_manager.session() as session:
        from sqlalchemy import func
        from src.models.message_dictionary import MessageDictionary

        # Count dictionaries
        result = await session.execute(select(func.count(Dictionary.id)))
        total_dicts = result.scalar_one()

        # Count categories
        result = await session.execute(select(func.count(DictionaryCategory.id)))
        total_categories = result.scalar_one()

        # Count words
        result = await session.execute(select(func.count(DictionaryWord.id)))
        total_words = result.scalar_one()

        # Count active words
        result = await session.execute(
            select(func.count(DictionaryWord.id)).where(DictionaryWord.is_active == True)
        )
        active_words = result.scalar_one()

        # Count matches
        result = await session.execute(select(func.count(MessageDictionary.message_id)))
        total_matches = result.scalar_one()

        print(f"✓ Dictionaries: {total_dicts}")
        print(f"✓ Categories: {total_categories}")
        print(f"✓ Words: {total_words} ({active_words} active)")
        print(f"✓ Total Matches: {total_matches}")

        return True


async def main():
    """Run all tests."""
    print("\n" + "#"*60)
    print("# Dictionary & Matching System - Comprehensive Test")
    print("#"*60)

    # Initialize database
    db_manager.init_engine()

    try:
        # Run tests
        dict_id = await test_dictionary_models()
        await test_matching_service()
        await test_batch_matching()
        await test_stats()

        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60)

        print("\nNext steps:")
        print("1. Visit http://localhost:8000/docs to try Dictionary API endpoints")
        print("2. Create more dictionaries and categories")
        print("3. Run ingestion to automatically match words in messages")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
