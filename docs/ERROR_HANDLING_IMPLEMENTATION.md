# Error Handling and Resilience Implementation

## Overview

This document describes the error handling and resilience features implemented for the WanderGenie data infrastructure layer. The implementation provides robust error categorization, automatic retry logic, and graceful degradation to ensure the system remains operational even when individual components fail.

## Components

### 1. Retry Decorator (`backend/utils/retry.py`)

A flexible retry decorator with exponential backoff for handling transient failures.

**Features:**
- Configurable retry attempts, delays, and exponential backoff
- Selective exception handling (only retries specified exception types)
- Automatic logging of retry attempts and failures
- Preserves function metadata (name, docstring)

**Usage:**
```python
from backend.utils.retry import retry_with_exponential_backoff

@retry_with_exponential_backoff(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    retryable_exceptions=(ConnectionError, TimeoutError)
)
def fetch_data():
    # Code that might fail transiently
    pass
```

**Configuration:**
- `max_attempts`: Maximum number of retry attempts (default: 3)
- `base_delay`: Initial delay in seconds before first retry (default: 1.0)
- `max_delay`: Maximum delay in seconds between retries (default: 10.0)
- `exponential_base`: Base for exponential backoff calculation (default: 2.0)
- `retryable_exceptions`: Tuple of exception types that should trigger retries

### 2. Custom Exception Classes (`backend/utils/exceptions.py`)

A hierarchy of custom exceptions for proper error categorization.

**Exception Hierarchy:**
```
WanderGenieError (base)
├── TransientError (retryable)
│   ├── ConnectionError
│   ├── TimeoutError
│   └── RateLimitError
├── PermanentError (not retryable)
│   ├── ValidationError
│   └── ConfigurationError
├── DegradedModeError (signals fallback needed)
├── DatabaseError
│   ├── VectorDBError
│   └── GraphDBError
└── APIError
    └── OpenTripMapError
```

**Error Categories:**

1. **Transient Errors** - Should be retried automatically:
   - Network timeouts
   - Database connection failures
   - API rate limiting
   - Temporary service unavailability

2. **Permanent Errors** - Should fail fast without retry:
   - Invalid API keys
   - Malformed queries
   - Schema validation failures
   - Authentication failures

3. **Degraded Mode Errors** - Signal fallback to alternative data sources:
   - API unavailable → use cache
   - VectorDB down → skip enrichment
   - GraphDB down → skip relationship queries

**Usage:**
```python
from backend.utils.exceptions import TransientError, PermanentError

# Raise transient error (will be retried)
raise TransientError(
    "Database connection failed",
    context={"host": "localhost", "port": 5432}
)

# Raise permanent error (will fail immediately)
raise PermanentError(
    "Invalid API key",
    context={"api": "OpenTripMap"}
)
```

### 3. Enhanced Client Error Handling

Both VectorDB and GraphDB clients have been updated with:
- Custom exception types for better error categorization
- Automatic retry logic for transient failures
- Detailed error logging with context
- Proper error propagation

**VectorDBClient Updates:**
- Connection retries with exponential backoff
- Transient error handling for embedding generation
- Detailed error context in exceptions
- Graceful handling of empty text inputs

**GraphDBClient Updates:**
- Connection retries with exponential backoff
- Separate handling for authentication vs. service unavailability
- Query execution retries for transient failures
- Proper error categorization for different failure modes

### 4. Graceful Degradation in Tools

The `poi_search` tool implements graceful degradation:

**Degradation Strategy:**
1. **Primary**: OpenTripMap API (with automatic cache fallback)
2. **Optional**: VectorDB enrichment (skipped if unavailable)
3. **Optional**: GraphDB enrichment (skipped if unavailable)

**Behavior:**
- Returns partial results when some services are unavailable
- Logs degraded mode status for monitoring
- Tracks which enrichments were applied
- Never crashes due to enrichment failures

**Example:**
```python
# Even if VectorDB and GraphDB are down, returns basic POI data
pois = poi_search("NYC", tags=["museum"])
# Returns: POIs from OpenTripMap without enrichment
```

**Memory Tools Degradation:**
- `vectordb_retrieve()`: Returns empty list if VectorDB unavailable
- `graphdb_query()`: Returns empty list if GraphDB unavailable
- Both log errors for debugging but don't crash

## Testing

### Test Coverage

**Unit Tests:**
- `tests/test_retry.py`: 14 tests for retry decorator
- `tests/test_error_handling.py`: 26 tests for exception classes

**Integration Tests:**
- `tests/integration/test_degraded_mode.py`: 13 tests for graceful degradation

**Total: 53 tests, all passing**

### Test Scenarios

1. **Retry Logic:**
   - Success on first attempt
   - Success after retries
   - Exhausted retries
   - Non-retryable exceptions
   - Exponential backoff timing
   - Max delay cap
   - Custom retryable exceptions
   - Logging behavior

2. **Error Categorization:**
   - Exception hierarchy
   - Error context handling
   - Transient vs. permanent classification
   - Degraded mode signaling

3. **Graceful Degradation:**
   - POI search without VectorDB
   - POI search without GraphDB
   - POI search without both databases
   - Partial VectorDB failures
   - Partial results with mixed availability
   - Degraded mode logging

## Logging

All error handling includes structured logging:

**Log Levels:**
- `DEBUG`: Cache hits/misses, query details
- `INFO`: Tool calls, data source switches, successful operations
- `WARNING`: Fallbacks, retries, degraded mode
- `ERROR`: Failures, validation errors
- `CRITICAL`: System-wide failures

**Log Context:**
- Function name
- Error type
- Retry attempt number
- Error context (parameters, state)
- Degraded mode status

**Example Log Output:**
```json
{
  "event": "retry_attempt",
  "function": "connect",
  "attempt": 2,
  "max_attempts": 3,
  "error": "Connection timeout",
  "error_type": "TimeoutError",
  "retry_delay_seconds": 2.0
}
```

## Performance Impact

**Retry Overhead:**
- Minimal for successful operations (no retries)
- Configurable delays for failed operations
- Max delay cap prevents excessive waiting

**Degradation Overhead:**
- Negligible - only try-catch blocks
- No performance impact when all services available
- Faster response when services are down (fail fast)

## Best Practices

1. **Use Appropriate Exception Types:**
   - Transient errors for temporary failures
   - Permanent errors for configuration/validation issues
   - Specific error types (VectorDBError, GraphDBError) for clarity

2. **Include Error Context:**
   - Always provide context dictionary with relevant information
   - Include operation parameters, state, and error details
   - Makes debugging much easier

3. **Log at Appropriate Levels:**
   - DEBUG for normal operation details
   - WARNING for degraded mode
   - ERROR for failures that need attention

4. **Design for Degradation:**
   - Make enrichments optional
   - Return partial results when possible
   - Never crash due to optional features

5. **Test Failure Scenarios:**
   - Test with mocked failures
   - Verify graceful degradation
   - Check logging output

## Monitoring Recommendations

Monitor these metrics in production:

1. **Retry Rates:**
   - Track retry attempts per function
   - Alert on high retry rates (indicates systemic issues)

2. **Degraded Mode Frequency:**
   - Track how often services are unavailable
   - Alert on prolonged degraded mode

3. **Error Types:**
   - Monitor distribution of error types
   - Permanent errors may indicate configuration issues

4. **Response Times:**
   - Track latency with and without retries
   - Monitor impact of degraded mode on performance

## Future Enhancements

Potential improvements:

1. **Circuit Breaker Pattern:**
   - Temporarily disable failing services
   - Prevent cascading failures
   - Automatic recovery detection

2. **Adaptive Retry:**
   - Adjust retry parameters based on error patterns
   - Faster retries for quick failures
   - Longer delays for persistent issues

3. **Health Checks:**
   - Proactive service health monitoring
   - Preemptive degraded mode activation
   - Faster recovery detection

4. **Metrics Collection:**
   - Structured metrics for monitoring
   - Integration with monitoring systems
   - Real-time dashboards

## References

- Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
- Design Document: `docs/design.md` - Error Handling section
- Implementation: Task 6 in `tasks.md`
