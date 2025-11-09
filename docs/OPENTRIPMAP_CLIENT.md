# OpenTripMap API Client Implementation

## Overview

The OpenTripMap API client provides a robust interface for searching and retrieving Points of Interest (POIs) with built-in caching, fallback mechanisms, and data enrichment capabilities.

## Features

### 1. API Integration
- Full integration with OpenTripMap API
- Automatic city geocoding to bounding box conversion
- Support for filtering by categories (kinds)
- Configurable result limits
- Proper error handling and retry logic

### 2. Retry Logic with Exponential Backoff
- Automatic retry for transient failures (connection errors, timeouts)
- Configurable retry parameters (max attempts, delays)
- Exponential backoff to avoid overwhelming services
- Detailed logging of retry attempts

### 3. Caching System

#### In-Memory TTL Cache
- 5-minute time-to-live for API responses
- Reduces API calls for repeated queries
- Automatic cache expiration and refresh
- Cache hit/miss logging for monitoring

#### Offline Cache Fallback
- Loads POI data from local JSON files when API is unavailable
- Supports both single POI objects and arrays
- City name normalization for flexible file matching
- Automatic fallback on API failures or rate limiting

### 4. Data Enrichment
- Merges booking requirement data from curated datasets
- Adds booking_required flag and booking_url
- Includes advance booking recommendations
- Automatic deduplication of results

### 5. Response Normalization
- Converts OpenTripMap format to internal POI schema
- Handles multiple API response formats
- Extracts and normalizes coordinates, tags, and metadata
- Consistent data structure for downstream consumers

## Usage

### Basic Search

```python
from backend.tools.poi import OpenTripMapClient
from backend.utils.config import settings

# Initialize client
client = OpenTripMapClient(
    api_key=settings.opentripmap_api_key,
    cache_dir="./data"
)

# Search by city
pois = client.search_pois(
    city="New York City",
    kinds="museums,landmarks",
    limit=20
)

# Search by bounding box
pois = client.search_pois(
    bbox=(-74.1, 40.7, -73.9, 40.8),
    kinds="museums",
    limit=50
)
```

### Get POI Details

```python
# Get detailed information for a specific POI
details = client.get_poi_details("W123456789")
```

### Manual Enrichment

```python
# Enrich POIs with booking information
enriched_pois = client.enrich_pois(pois)
```

## Data Files

### Cache Files
- `data/nyc_pois.json` - Offline POI cache for New York City
- Format: Single POI object or array of POI objects

### Booking Data
- `data/nyc_booking_required.json` - Booking requirements for NYC POIs
- Format: Array of booking information objects

```json
[
  {
    "name": "Statue of Liberty",
    "booking_required": true,
    "booking_url": "https://www.statuecitycruises.com/",
    "advance_days": 7,
    "notes": "Crown tickets sold separately; limited supply"
  }
]
```

## POI Schema

Normalized POI objects follow this structure:

```python
{
    "id": "opentripmap:W123456",
    "name": "Museum of Modern Art",
    "lat": 40.7614,
    "lon": -73.9776,
    "city": "New York",
    "neighborhood": None,
    "tags": ["museums", "art"],
    "duration_min": None,
    "popularity": 0.85,  # 0-1 scale
    "booking_required": True,
    "booking_url": "https://example.com/book",
    "hours": None,
    "notes": ["Book 7 days in advance"],
    "source": "opentripmap",
    "source_id": "W123456"
}
```

## Error Handling

### Automatic Fallback
1. API request fails → Retry with exponential backoff (up to 3 attempts)
2. All retries exhausted → Fall back to offline cache
3. Cache not available → Return empty list with error logging

### Rate Limiting
- Detects HTTP 429 responses
- Automatically falls back to cached data
- Logs warnings for monitoring

### Logging
All operations are logged with structured logging:
- DEBUG: Cache hits/misses, API requests
- INFO: Successful operations, cache loads
- WARNING: Fallbacks, retries, missing data
- ERROR: Failures, exceptions

## Testing

Comprehensive test suite with 29 tests covering:
- Client initialization
- API request handling
- Retry logic
- Rate limiting detection
- City geocoding
- Response normalization
- POI search with various parameters
- Cache loading (single POI and arrays)
- TTL cache behavior
- Booking data loading
- POI enrichment
- Deduplication

Run tests:
```bash
pytest tests/test_poi_client.py -v
```

## Configuration

Required environment variables:
```bash
OPENTRIPMAP_API_KEY=your_api_key_here
REQUEST_TIMEOUT=30  # seconds
CACHE_DIR=./data
```

## Performance

- API requests: < 2 seconds (per requirement)
- Cached requests: < 500ms
- TTL cache: 5 minutes
- Retry delays: 1s, 2s, 4s (exponential backoff)

## Dependencies

- `requests` - HTTP client
- `structlog` - Structured logging
- `pydantic-settings` - Configuration management

## Future Enhancements

- [ ] Support for additional cities beyond NYC
- [ ] Redis-based distributed caching
- [ ] Batch POI detail fetching
- [ ] Real-time availability checking
- [ ] Integration with additional POI data sources
