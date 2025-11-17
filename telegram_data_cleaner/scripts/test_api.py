#!/usr/bin/env python3
"""
Test external Telegram API to see the data structure.
"""
import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from src.config import settings
from src.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def test_api_connection() -> None:
    """Test API connection and authentication."""
    logger.info("Testing API connection...")
    logger.info(f"API URL: {settings.api_url}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                settings.api_url,
                headers=settings.api_headers
            )

            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response Headers: {dict(response.headers)}")

            if response.status_code == 200:
                logger.info("✓ API connection successful!")
                return response.json()
            else:
                logger.error(f"✗ API returned error: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return None

    except httpx.TimeoutException:
        logger.error("✗ API request timed out")
        return None
    except Exception as e:
        logger.error(f"✗ API request failed: {e}")
        return None


async def analyze_response_structure(data: dict | list) -> None:
    """Analyze the structure of API response."""
    logger.info("\n" + "="*60)
    logger.info("API Response Structure Analysis")
    logger.info("="*60)

    if data is None:
        logger.error("No data to analyze")
        return

    # Check if it's a list or dict
    data_type = type(data).__name__
    logger.info(f"Data Type: {data_type}")

    if isinstance(data, list):
        logger.info(f"Total Items: {len(data)}")

        if len(data) > 0:
            logger.info("\nFirst Item Structure:")
            first_item = data[0]
            logger.info(f"Item Type: {type(first_item).__name__}")

            if isinstance(first_item, dict):
                logger.info("\nAvailable Fields:")
                for key, value in first_item.items():
                    value_type = type(value).__name__
                    value_sample = str(value)[:100] if value else "None"
                    logger.info(f"  • {key}: {value_type} = {value_sample}")

                # Pretty print first 3 items
                logger.info("\n" + "-"*60)
                logger.info("Sample Data (first 3 items):")
                logger.info("-"*60)
                for i, item in enumerate(data[:3], 1):
                    logger.info(f"\nItem {i}:")
                    logger.info(json.dumps(item, indent=2, ensure_ascii=False))

    elif isinstance(data, dict):
        logger.info("\nResponse Fields:")
        for key, value in data.items():
            value_type = type(value).__name__
            if isinstance(value, list):
                logger.info(f"  • {key}: {value_type} (length: {len(value)})")
            else:
                value_sample = str(value)[:100] if value else "None"
                logger.info(f"  • {key}: {value_type} = {value_sample}")

        logger.info("\n" + "-"*60)
        logger.info("Full Response Sample:")
        logger.info("-"*60)
        logger.info(json.dumps(data, indent=2, ensure_ascii=False))


async def check_channel_structure(data: dict | list) -> None:
    """Check for channel information."""
    logger.info("\n" + "="*60)
    logger.info("Channel Information Analysis")
    logger.info("="*60)

    channels_found = set()

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                # Common field names for channel info
                for field in ['channel', 'channel_id', 'chat', 'chat_id', 'from', 'peer_id']:
                    if field in item:
                        channel_info = item[field]
                        if isinstance(channel_info, dict):
                            channel_name = channel_info.get('title') or channel_info.get('name') or channel_info.get('username')
                            if channel_name:
                                channels_found.add(channel_name)
                        elif isinstance(channel_info, (str, int)):
                            channels_found.add(str(channel_info))

    if channels_found:
        logger.info(f"✓ Found {len(channels_found)} unique channels:")
        for i, channel in enumerate(sorted(channels_found)[:10], 1):
            logger.info(f"  {i}. {channel}")
        if len(channels_found) > 10:
            logger.info(f"  ... and {len(channels_found) - 10} more")
    else:
        logger.info("✗ No channel information found in expected fields")


async def main() -> None:
    """Main function."""
    print("\n" + "🔍 Testing External Telegram API" + "\n")

    # Test connection
    data = await test_api_connection()

    if data:
        # Analyze structure
        await analyze_response_structure(data)

        # Check channels
        await check_channel_structure(data)

        logger.info("\n" + "="*60)
        logger.info("✓ API Test Completed Successfully")
        logger.info("="*60)
    else:
        logger.error("\n" + "="*60)
        logger.error("✗ API Test Failed")
        logger.error("="*60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
