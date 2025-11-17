"""
Telegram API client with retry logic, rate limiting, and caching.
"""
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import httpx
import redis.asyncio as aioredis
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.config import settings
from src.core.logging import get_logger
from src.core.exceptions import (
    APIConnectionError,
    APIRateLimitError,
    APITimeoutError,
    APIResponseError,
    CacheConnectionError,
)
from src.schemas.ingestion import APIResponseSchema

logger = get_logger(__name__)


class RateLimiter:
    """
    Simple rate limiter using token bucket algorithm.
    """

    def __init__(self, max_requests: int = 60, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.

        Blocks if rate limit is exceeded.
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.time_window)

            # Remove old requests outside time window
            self.requests = [req_time for req_time in self.requests if req_time > cutoff]

            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_until = oldest_request + timedelta(seconds=self.time_window)
                wait_seconds = (wait_until - now).total_seconds()

                if wait_seconds > 0:
                    logger.warning(
                        f"Rate limit reached. Waiting {wait_seconds:.2f} seconds..."
                    )
                    await asyncio.sleep(wait_seconds)

                    # Clean up again after waiting
                    now = datetime.now()
                    cutoff = now - timedelta(seconds=self.time_window)
                    self.requests = [
                        req_time for req_time in self.requests if req_time > cutoff
                    ]

            # Add current request
            self.requests.append(now)


class TelegramAPIClient:
    """
    Async HTTP client for Telegram data API.

    Features:
    - Automatic retry with exponential backoff
    - Rate limiting
    - Redis caching
    - Pagination support
    - Comprehensive error handling
    """

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        cache_ttl: int = 120,  # 2 minutes default
        max_requests_per_minute: int = 60,
    ):
        """
        Initialize API client.

        Args:
            redis_client: Redis client for caching (optional)
            cache_ttl: Cache TTL in seconds
            max_requests_per_minute: Max requests per minute
        """
        self.base_url = settings.api_url
        self.headers = settings.api_headers
        self.timeout = settings.api_timeout
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.rate_limiter = RateLimiter(
            max_requests=max_requests_per_minute, time_window=60
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers=self.headers,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _generate_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate cache key for request.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Cache key string
        """
        cache_parts = [endpoint]
        if params:
            # Sort params for consistent cache keys
            sorted_params = sorted(params.items())
            cache_parts.append(urlencode(sorted_params))

        cache_string = "|".join(cache_parts)
        # Hash to keep key length manageable
        cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
        return f"telegram_api:{cache_hash}"

    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get data from Redis cache.

        Args:
            cache_key: Cache key

        Returns:
            Cached data or None
        """
        if not self.redis_client:
            return None

        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit: {cache_key}")
                return json.loads(cached_data)
            else:
                logger.debug(f"Cache miss: {cache_key}")
                return None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    async def _set_in_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Set data in Redis cache.

        Args:
            cache_key: Cache key
            data: Data to cache
        """
        if not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data, default=str)  # Handle datetime serialization
            )
            logger.debug(f"Cached data: {cache_key} (TTL: {self.cache_ttl}s)")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, "WARNING"),
    )
    async def _make_request(
        self,
        method: str = "GET",
        endpoint: str = "",
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method
            endpoint: API endpoint (empty for base URL)
            params: Query parameters
            use_cache: Whether to use cache

        Returns:
            Response JSON data

        Raises:
            APIConnectionError: Connection failed
            APITimeoutError: Request timed out
            APIRateLimitError: Rate limit exceeded
            APIResponseError: API returned error
        """
        if not self._client:
            raise APIConnectionError(
                self.base_url,
                Exception("Client not initialized. Use async context manager.")
            )

        # Construct full URL
        url = self.base_url if not endpoint else f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # Check cache first
        cache_key = self._generate_cache_key(endpoint or self.base_url, params)
        if use_cache:
            cached_data = await self._get_from_cache(cache_key)
            if cached_data:
                return cached_data

        # Apply rate limiting
        await self.rate_limiter.acquire()

        try:
            logger.info(f"Making {method} request to {url}")
            if params:
                logger.debug(f"Parameters: {params}")

            response = await self._client.request(
                method=method,
                url=url,
                params=params,
            )

            # Handle rate limiting from server
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_seconds = int(retry_after) if retry_after else None
                raise APIRateLimitError(retry_after=retry_seconds)

            # Handle error responses
            if response.status_code >= 400:
                raise APIResponseError(
                    status_code=response.status_code,
                    response_text=response.text
                )

            data = response.json()

            # Cache successful response
            if use_cache and response.status_code == 200:
                await self._set_in_cache(cache_key, data)

            logger.info(f"Request successful: {response.status_code}")
            return data

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {url}")
            raise APITimeoutError(url=url, timeout=self.timeout) from e

        except (httpx.ConnectError, httpx.NetworkError) as e:
            logger.error(f"Connection error: {url}")
            raise APIConnectionError(url=url, original_error=e) from e

        except (APIRateLimitError, APIResponseError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            logger.error(f"Unexpected error during request: {e}")
            raise APIConnectionError(url=url, original_error=e) from e

    async def fetch_messages(
        self,
        limit: int = 100,
        offset: Optional[int] = None,
        use_cache: bool = True,
    ) -> APIResponseSchema:
        """
        Fetch messages from API with pagination.

        Args:
            limit: Number of messages to fetch (default: 100)
            offset: Offset for pagination (default: None)
            use_cache: Whether to use cache (default: True)

        Returns:
            Validated API response

        Raises:
            APIConnectionError: Connection failed
            APITimeoutError: Request timed out
            APIRateLimitError: Rate limit exceeded
            APIResponseError: API returned error
            DataValidationError: Response validation failed
        """
        params = {"limit": limit}
        if offset is not None:
            params["offset"] = offset

        logger.info(f"Fetching messages (limit={limit}, offset={offset})")

        try:
            data = await self._make_request(
                method="GET",
                params=params,
                use_cache=use_cache,
            )

            # Validate response with Pydantic
            response = APIResponseSchema(**data)

            logger.info(
                f"Fetched {len(response.messages)} messages "
                f"(total available: {response.total})"
            )

            return response

        except Exception as e:
            logger.error(f"Failed to fetch messages: {e}")
            raise

    async def fetch_all_messages(
        self,
        batch_size: int = 100,
        max_messages: Optional[int] = None,
        use_cache: bool = True,
    ) -> list[APIResponseSchema]:
        """
        Fetch all messages using pagination.

        Args:
            batch_size: Messages per request
            max_messages: Maximum total messages to fetch (None = all)
            use_cache: Whether to use cache

        Returns:
            List of API responses

        Raises:
            Same as fetch_messages
        """
        all_responses: list[APIResponseSchema] = []
        offset = 0
        total_fetched = 0

        logger.info(
            f"Starting batch fetch (batch_size={batch_size}, max={max_messages or 'all'})"
        )

        while True:
            # Check if we've reached the limit
            if max_messages and total_fetched >= max_messages:
                logger.info(f"Reached max messages limit: {max_messages}")
                break

            # Fetch batch
            response = await self.fetch_messages(
                limit=batch_size,
                offset=offset,
                use_cache=use_cache,
            )

            all_responses.append(response)
            total_fetched += len(response.messages)

            logger.info(f"Progress: {total_fetched}/{response.total} messages")

            # Check if we've fetched all available messages
            if len(response.messages) < batch_size or total_fetched >= response.total:
                logger.info("Reached end of available messages")
                break

            # Move to next batch
            offset += batch_size

        logger.info(
            f"Batch fetch complete: {total_fetched} messages in {len(all_responses)} batches"
        )

        return all_responses

    async def get_channels(self, use_cache: bool = True) -> set[Dict[str, Any]]:
        """
        Extract unique channels from messages.

        Args:
            use_cache: Whether to use cache

        Returns:
            Set of unique channel info dicts

        Note:
            This fetches the first page of messages and extracts channels.
            For complete channel list, use fetch_all_messages().
        """
        logger.info("Fetching channel information...")

        response = await self.fetch_messages(limit=100, use_cache=use_cache)

        channels: Dict[int, Dict[str, Any]] = {}
        for message in response.messages:
            channel_id = message.channel.id
            if channel_id not in channels:
                channels[channel_id] = {
                    "id": message.channel.id,
                    "name": message.channel.name,
                    "username": message.channel.username,
                }

        logger.info(f"Found {len(channels)} unique channels")

        return set(tuple(sorted(ch.items())) for ch in channels.values())

    async def health_check(self) -> bool:
        """
        Check if API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            logger.info("Performing API health check...")
            await self.fetch_messages(limit=1, use_cache=False)
            logger.info("API health check: OK")
            return True
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False
