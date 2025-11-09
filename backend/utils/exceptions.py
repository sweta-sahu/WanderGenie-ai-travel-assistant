"""
Custom exception classes for error categorization in WanderGenie data layer.
"""


class WanderGenieError(Exception):
    """Base exception for all WanderGenie errors."""
    
    def __init__(self, message: str, context: dict = None):
        """
        Initialize exception with message and optional context.
        
        Args:
            message: Error message
            context: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}


class TransientError(WanderGenieError):
    """
    Exception for transient errors that should be retried.
    
    Examples:
        - Network timeouts
        - Database connection failures
        - Temporary API unavailability
    """
    pass


class PermanentError(WanderGenieError):
    """
    Exception for permanent errors that should not be retried.
    
    Examples:
        - Invalid API keys
        - Malformed queries
        - Schema validation failures
        - Authentication failures
    """
    pass


class DegradedModeError(WanderGenieError):
    """
    Exception indicating system is operating in degraded mode.
    
    This signals that a fallback or partial result should be used.
    
    Examples:
        - API unavailable, using cache
        - VectorDB down, skipping enrichment
        - GraphDB down, skipping relationship queries
    """
    pass


# Specific error types for different components

class DatabaseError(WanderGenieError):
    """Base exception for database-related errors."""
    pass


class VectorDBError(DatabaseError):
    """Exception for VectorDB (Supabase) errors."""
    pass


class GraphDBError(DatabaseError):
    """Exception for GraphDB (Neo4j) errors."""
    pass


class APIError(WanderGenieError):
    """Base exception for external API errors."""
    pass


class OpenTripMapError(APIError):
    """Exception for OpenTripMap API errors."""
    pass


class RateLimitError(TransientError):
    """Exception for API rate limiting."""
    
    def __init__(self, message: str, retry_after: int = None, context: dict = None):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
            context: Additional error context
        """
        super().__init__(message, context)
        self.retry_after = retry_after


class ValidationError(PermanentError):
    """Exception for data validation failures."""
    
    def __init__(self, message: str, validation_errors: list = None, context: dict = None):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            validation_errors: List of specific validation errors
            context: Additional error context
        """
        super().__init__(message, context)
        self.validation_errors = validation_errors or []


class ConnectionError(TransientError):
    """Exception for connection failures."""
    pass


class TimeoutError(TransientError):
    """Exception for operation timeouts."""
    pass


class ConfigurationError(PermanentError):
    """Exception for configuration errors."""
    pass
