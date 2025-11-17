"""
Custom exceptions for the application.
"""


class TelegramDataCleanerError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, *args: object) -> None:
        """Initialize with message."""
        self.message = message
        super().__init__(message, *args)


class APIError(TelegramDataCleanerError):
    """Base class for API-related errors."""

    pass


class APIConnectionError(APIError):
    """Raised when cannot connect to API."""

    def __init__(self, url: str, original_error: Exception) -> None:
        """Initialize with URL and original error."""
        self.url = url
        self.original_error = original_error
        message = f"Failed to connect to API at {url}: {str(original_error)}"
        super().__init__(message)


class APIRateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, retry_after: int | None = None) -> None:
        """Initialize with retry_after time."""
        self.retry_after = retry_after
        message = "API rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message)


class APITimeoutError(APIError):
    """Raised when API request times out."""

    def __init__(self, url: str, timeout: int) -> None:
        """Initialize with URL and timeout."""
        self.url = url
        self.timeout = timeout
        message = f"API request to {url} timed out after {timeout} seconds"
        super().__init__(message)


class APIResponseError(APIError):
    """Raised when API returns unexpected response."""

    def __init__(self, status_code: int, response_text: str) -> None:
        """Initialize with status code and response."""
        self.status_code = status_code
        self.response_text = response_text
        message = f"API returned error status {status_code}: {response_text[:200]}"
        super().__init__(message)


class DataValidationError(TelegramDataCleanerError):
    """Raised when data validation fails."""

    def __init__(self, field: str, value: object, reason: str) -> None:
        """Initialize with field, value, and reason."""
        self.field = field
        self.value = value
        self.reason = reason
        message = f"Validation failed for field '{field}' with value '{value}': {reason}"
        super().__init__(message)


class DataMappingError(TelegramDataCleanerError):
    """Raised when data mapping fails."""

    def __init__(self, source: str, target: str, reason: str) -> None:
        """Initialize with source, target, and reason."""
        self.source = source
        self.target = target
        self.reason = reason
        message = f"Failed to map {source} to {target}: {reason}"
        super().__init__(message)


class DatabaseError(TelegramDataCleanerError):
    """Base class for database errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when cannot connect to database."""

    pass


class DatabaseOperationError(DatabaseError):
    """Raised when database operation fails."""

    def __init__(self, operation: str, reason: str) -> None:
        """Initialize with operation and reason."""
        self.operation = operation
        self.reason = reason
        message = f"Database {operation} operation failed: {reason}"
        super().__init__(message)


class CacheError(TelegramDataCleanerError):
    """Base class for cache errors."""

    pass


class CacheConnectionError(CacheError):
    """Raised when cannot connect to cache."""

    pass


class SchedulerError(TelegramDataCleanerError):
    """Base class for scheduler errors."""

    pass


class JobExecutionError(SchedulerError):
    """Raised when scheduled job execution fails."""

    def __init__(self, job_name: str, reason: str) -> None:
        """Initialize with job name and reason."""
        self.job_name = job_name
        self.reason = reason
        message = f"Job '{job_name}' execution failed: {reason}"
        super().__init__(message)
