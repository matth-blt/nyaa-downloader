from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


class NyaaError(Exception):
    """Base exception for nyaa_downloader errors."""
    pass


class NetworkError(NyaaError):
    """Network-related errors (timeout, connection failed)."""
    pass


class DownloadError(NyaaError):
    """Error during torrent file download."""
    pass


class ParseError(NyaaError):
    """Error parsing RSS feed or anime metadata."""
    pass


class RateLimitError(NyaaError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: Optional[float] = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s" if retry_after else "Rate limit exceeded")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple = (
        NetworkError,
        RateLimitError,
    )

    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


def retry_with_backoff(
    func: Callable[[], T],
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> T:
    """
    Execute function with exponential backoff retry.
    
    :param func: Function to execute
    :param config: Retry configuration
    :param on_retry: Callback called on each retry with (attempt, exception)
    :return: Function result
    :raises: Last exception if all retries failed
    """
    config = config or RetryConfig()
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt < config.max_retries:
                delay = config.get_delay(attempt)
                if isinstance(e, RateLimitError) and e.retry_after:
                    delay = max(delay, e.retry_after)
                if on_retry:
                    on_retry(attempt, e)
                time.sleep(delay)
            else:
                raise
        except Exception:
            raise
    
    raise last_exception or NyaaError("Unknown error")
