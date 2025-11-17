"""
Tests for database models.
"""
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Category, Channel, Message, Tag, TagType, MessageTag


@pytest.mark.asyncio
async def test_create_category(session: AsyncSession) -> None:
    """
    Test creating a category.

    Args:
        session: Test database session fixture
    """
    category = Category(
        name="Test Category",
        description="Test description",
    )

    session.add(category)
    await session.commit()
    await session.refresh(category)

    assert category.id is not None
    assert isinstance(category.id, uuid.UUID)
    assert category.name == "Test Category"
    assert category.description == "Test description"
    assert category.created_at is not None
    assert category.updated_at is not None


@pytest.mark.asyncio
async def test_create_category_with_parent(session: AsyncSession) -> None:
    """
    Test creating a category with parent-child relationship.

    Args:
        session: Test database session fixture
    """
    parent = Category(name="Parent Category")
    session.add(parent)
    await session.commit()
    await session.refresh(parent)

    child = Category(
        name="Child Category",
        parent_id=parent.id,
    )
    session.add(child)
    await session.commit()
    await session.refresh(child)

    assert child.parent_id == parent.id
    assert child.parent.name == "Parent Category"


@pytest.mark.asyncio
async def test_create_channel(session: AsyncSession) -> None:
    """
    Test creating a channel.

    Args:
        session: Test database session fixture
    """
    category = Category(name="News")
    session.add(category)
    await session.commit()
    await session.refresh(category)

    channel = Channel(
        telegram_id="123456",
        name="Test Channel",
        username="testchannel",
        category_id=category.id,
        is_active=True,
    )

    session.add(channel)
    await session.commit()
    await session.refresh(channel)

    assert channel.id is not None
    assert isinstance(channel.id, uuid.UUID)
    assert channel.telegram_id == "123456"
    assert channel.name == "Test Channel"
    assert channel.username == "testchannel"
    assert channel.category_id == category.id
    assert channel.is_active is True
    assert channel.category.name == "News"


@pytest.mark.asyncio
async def test_create_message(session: AsyncSession) -> None:
    """
    Test creating a message.

    Args:
        session: Test database session fixture
    """
    channel = Channel(
        telegram_id="123456",
        name="Test Channel",
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)

    message = Message(
        telegram_message_id=1001,
        channel_id=channel.id,
        text="This is a test message",
        text_normalized="this is a test message",
        date=datetime.now(timezone.utc),
        views=100,
        forwards=5,
        metadata={"lang": "en"},
    )

    session.add(message)
    await session.commit()
    await session.refresh(message)

    assert message.id is not None
    assert isinstance(message.id, uuid.UUID)
    assert message.telegram_message_id == 1001
    assert message.channel_id == channel.id
    assert message.text == "This is a test message"
    assert message.text_normalized == "this is a test message"
    assert message.views == 100
    assert message.forwards == 5
    assert message.metadata == {"lang": "en"}
    assert message.channel.name == "Test Channel"


@pytest.mark.asyncio
async def test_create_tag(session: AsyncSession) -> None:
    """
    Test creating a tag.

    Args:
        session: Test database session fixture
    """
    tag = Tag(
        name="Long Message",
        tag_type=TagType.CHARACTER_COUNT,
        condition={"min": 1000, "max": 5000},
        description="Messages with 1000-5000 characters",
        is_active=True,
    )

    session.add(tag)
    await session.commit()
    await session.refresh(tag)

    assert tag.id is not None
    assert isinstance(tag.id, uuid.UUID)
    assert tag.name == "Long Message"
    assert tag.tag_type == TagType.CHARACTER_COUNT
    assert tag.condition == {"min": 1000, "max": 5000}
    assert tag.description == "Messages with 1000-5000 characters"
    assert tag.is_active is True


@pytest.mark.asyncio
async def test_message_tag_relationship(session: AsyncSession) -> None:
    """
    Test many-to-many relationship between messages and tags.

    Args:
        session: Test database session fixture
    """
    # Create channel
    channel = Channel(telegram_id="123456", name="Test Channel")
    session.add(channel)
    await session.commit()
    await session.refresh(channel)

    # Create message
    message = Message(
        telegram_message_id=1001,
        channel_id=channel.id,
        text="Test message",
        date=datetime.now(timezone.utc),
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    # Create tags
    tag1 = Tag(name="Tag 1", tag_type=TagType.CUSTOM)
    tag2 = Tag(name="Tag 2", tag_type=TagType.CUSTOM)
    session.add_all([tag1, tag2])
    await session.commit()
    await session.refresh(tag1)
    await session.refresh(tag2)

    # Create associations
    message_tag1 = MessageTag(message_id=message.id, tag_id=tag1.id)
    message_tag2 = MessageTag(message_id=message.id, tag_id=tag2.id)
    session.add_all([message_tag1, message_tag2])
    await session.commit()

    # Verify relationships
    result = await session.execute(
        select(Message).where(Message.id == message.id)
    )
    fetched_message = result.scalar_one()

    assert len(fetched_message.tags) == 2
    tag_names = {tag.name for tag in fetched_message.tags}
    assert tag_names == {"Tag 1", "Tag 2"}


@pytest.mark.asyncio
async def test_channel_cascade_delete(session: AsyncSession) -> None:
    """
    Test that deleting a channel cascades to messages.

    Args:
        session: Test database session fixture
    """
    # Create channel with messages
    channel = Channel(telegram_id="123456", name="Test Channel")
    session.add(channel)
    await session.commit()
    await session.refresh(channel)

    message1 = Message(
        telegram_message_id=1001,
        channel_id=channel.id,
        text="Message 1",
        date=datetime.now(timezone.utc),
    )
    message2 = Message(
        telegram_message_id=1002,
        channel_id=channel.id,
        text="Message 2",
        date=datetime.now(timezone.utc),
    )
    session.add_all([message1, message2])
    await session.commit()

    # Delete channel
    await session.delete(channel)
    await session.commit()

    # Verify messages are also deleted
    result = await session.execute(
        select(Message).where(Message.channel_id == channel.id)
    )
    messages = result.scalars().all()
    assert len(messages) == 0


@pytest.mark.asyncio
async def test_model_to_dict(session: AsyncSession) -> None:
    """
    Test model to_dict method.

    Args:
        session: Test database session fixture
    """
    category = Category(name="Test Category", description="Test")
    session.add(category)
    await session.commit()
    await session.refresh(category)

    category_dict = category.to_dict()

    assert isinstance(category_dict, dict)
    assert "id" in category_dict
    assert "name" in category_dict
    assert category_dict["name"] == "Test Category"
    assert "created_at" in category_dict
    assert "updated_at" in category_dict
