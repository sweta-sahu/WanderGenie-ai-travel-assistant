"""
Retry utilities with exponential backoff for handling transient failures.
"""

import time
from functools import wraps
from typing import Callable, Type, Tuple
import structlog

logger = structlog.get_logger()


class RetryConfig:
    """Configuration for retry behavior with exponential backoff."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        retryable_exceptions: Tuple[Type[Exception], ...] = (ConnectionError, TimeoutError)
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay in seconds between retries
            exponential_base: Base for exponential backoff calculation
            retryable_exceptions: Tuple of exception types that should trigger retries
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions


def retry_with_exponential_backoff(
    config: RetryConfig = None,
    max_attempts: int = None,
    base_delay: float = None,
    max_delay: float = None,
    exponential_base: float = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = None
) -> Callable:
    """
    Decorator for automatic retry with exponential backoff.
    
    Can be used with a RetryConfig object or individual parameters.
    
    Args:
        config: RetryConfig object (if provided, other params are ignored)
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        retryable_exceptions: Tuple of exception types to retry
        
    Returns:
        Decorated function with retry logic
        
    Example:
        @retry_with_exponential_backoff(max_attempts=3, base_delay=1.0)
        def fetch_data():
            # code that might fail transiently
            pass
    """
    # Use provided config or create one from parameters
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts or 3,
            base_delay=base_delay or 1.0,
            max_delay=max_delay or 10.0,
            exponential_base=exponential_base or 2.0,
            retryable_exceptions=retryable_exceptions or (ConnectionError, TimeoutError)
        )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=config.max_attempts,
                            error=str(e),
                            error_type=type(e).__name__
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    logger.warning(
                        "retry_attempt",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=config.max_attempts,
                        error=str(e),
                        error_type=type(e).__name__,
                        retry_delay_seconds=delay
                    )
                    
                    time.sleep(delay)
                except Exception as e:
                    # Non-retryable exception, fail immediately
                    logger.error(
                        "non_retryable_error",
                        function=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator
