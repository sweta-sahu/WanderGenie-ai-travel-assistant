# Tool Registry Implementation

This document describes the implementation of the tool registry functions for the WanderGenie AI travel assistant.

## Overview

The tool registry provides a unified interface for AI agents to access POI data, perform semantic searches, query graph relationships, and use utility functions. All tools are designed with graceful degradation, comprehensive error handling, and detailed logging.

## Implemented Tools

### 1. POI Tools (`backend/tools/poi.py`)

#### `poi_search(city, tags, bbox, center, radius)`

Orchestrates multiple data sources to search for points of interest:

- **Primary Source**: OpenTripMap API with automatic fallback to cached data
- **Enrichment**: VectorDB for semantic context (optional, graceful degradation)
- **Enrichment**: GraphDB for booking information (optional, graceful degradation)

**Features**:
- Parameter validation (city or bbox required)
- Center/radius to bbox conversion
- Automatic deduplication by POI ID
- Comprehensive error handling
- Performance logging

**Example**:
```python
# Search museums in NYC
pois = poi_search("NYC", tags=["museum", "art"])

# Search with bounding box
pois = poi_search("NYC", bbox=(-74.0, 40.7, -73.9, 40.8))

# Search with center and radius
pois = poi_search("NYC", center=(40.7589, -73.9851), radius=2.0)
```

#### `get_open_hours(poi_id_or_name, city)`

Retrieves opening hours for a specific POI from curated data files.

**Features**:
- Supports both POI ID and name lookup
- Case-insensitive matching
- Partial name matching
- Handles both list and dict data formats
- Fallback to "hours not available" message

**Example**:
```python
# Get hours by name
hours = get_open_hours("Statue of Liberty", "NYC")

# Get hours by ID
hours = get_open_hours("opentripmap:N123456", "NYC")
```

### 2. Memory Tools (`backend/tools/memory.py`)

#### `vectordb_retrieve(query, k, collection)`

Performs semantic similarity search on the vector database.

**Features**:
- Natural language query support
- Configurable result count (k)
- Collection selection
- Graceful degradation (returns empty list on failure)
- Parameter validation

**Example**:
```python
# Find booking tips
tips = vectordb_retrieve("statue of liberty booking tips", k=5)

# Find accessibility information
access = vectordb_retrieve("wheelchair accessible museums NYC", k=3)
```

#### `graphdb_query(cypher, parameters)`

Executes Cypher queries on the Neo4j graph database.

**Features**:
- Parameterized query support for safety
- Automatic connection management
- Warning logging for dangerous operations
- Graceful degradation (returns empty list on failure)
- Query validation

**Example**:
```python
# Find POIs in a neighborhood
query = """
MATCH (p:POI)-[:IN_NEIGHBORHOOD]->(n:Neighborhood {name: $name})
RETURN p.id AS id, p.name AS name
"""
pois = graphdb_query(query, {"name": "Lower Manhattan"})

# Find similar POIs
query = """
MATCH (p:POI {id: $poi_id})-[r:SIMILAR_TO]->(similar:POI)
RETURN similar.name AS name, r.score AS similarity_score
ORDER BY r.score DESC LIMIT 5
"""
similar = graphdb_query(query, {"poi_id": "opentripmap:N123"})
```

### 3. Utility Tools (`backend/tools/utils.py`)

#### `distance_calc(coord1, coord2)`

Calculates distance between two coordinates using the Haversine formula.

**Features**:
- Accurate great-circle distance calculation
- Coordinate validation (lat: -90 to 90, lon: -180 to 180)
- Returns distance in kilometers
- Comprehensive error messages

**Example**:
```python
# Calculate distance between two POIs
distance = distance_calc((40.6892, -74.0445), (40.7484, -73.9857))
# Returns approximately 8.8 km

# Check if within walking distance
if distance_calc((poi1_lat, poi1_lon), (poi2_lat, poi2_lon)) < 1.0:
    print("Within walking distance")
```

#### `validate_schema(data, schema_name)`

Validates data against Pydantic schemas.

**Features**:
- POI schema validation (currently supported)
- Detailed error messages with field locations
- Default value application
- Returns validated and cleaned data

**Example**:
```python
# Validate POI data
poi_data = {
    "id": "opentripmap:N123",
    "name": "Statue of Liberty",
    "lat": 40.6892,
    "lon": -74.0445,
    "city": "NYC",
    "tags": ["landmark"],
    "source": "opentripmap",
    "source_id": "N123"
}

result = validate_schema(poi_data, "poi")
if result["valid"]:
    validated_poi = result["validated_data"]
else:
    print(f"Errors: {result['errors']}")
```

## Error Handling Strategy

All tools implement a consistent error handling approach:

1. **Parameter Validation**: Validate inputs before processing
2. **Graceful Degradation**: Return empty results instead of crashing when optional services fail
3. **Detailed Logging**: Log all operations with context for debugging
4. **Clear Error Messages**: Provide actionable error messages for validation failures

## Testing

Comprehensive test coverage includes:

- **Unit Tests**: 67 tests covering all functions
- **Integration Tests**: End-to-end tests for poi_search with all data sources
- **Edge Cases**: Boundary values, invalid inputs, error conditions
- **Graceful Degradation**: Tests for service unavailability

### Test Files

- `tests/test_get_open_hours.py` - 11 tests for get_open_hours
- `tests/test_memory_tools.py` - 19 tests for vectordb_retrieve and graphdb_query
- `tests/test_utils_tools.py` - 26 tests for distance_calc and validate_schema
- `tests/integration/test_poi_search_tool.py` - 11 integration tests for poi_search

### Running Tests

```bash
# Run all tool tests
python -m pytest tests/test_get_open_hours.py tests/test_memory_tools.py tests/test_utils_tools.py tests/integration/test_poi_search_tool.py -v

# Run specific test file
python -m pytest tests/test_memory_tools.py -v

# Run with coverage
python -m pytest tests/ --cov=backend/tools --cov-report=html
```

## Performance Considerations

- **Caching**: poi_search uses 5-minute TTL cache for identical queries
- **Connection Pooling**: Database clients reuse connections
- **Batch Processing**: VectorDB operations process in batches
- **Lazy Loading**: Database clients only connect when needed

## Future Enhancements

1. **Additional Schemas**: Implement Trip schema validation
2. **Advanced Filtering**: Add more filter options to vectordb_retrieve
3. **Query Builder**: Helper functions for common Cypher patterns
4. **Caching Layer**: Implement Redis for distributed caching
5. **Rate Limiting**: Add rate limiting for external API calls

## Dependencies

- `pydantic`: Schema validation
- `supabase`: VectorDB client
- `neo4j`: GraphDB client
- `openai`: Embedding generation
- `requests`: HTTP client for OpenTripMap API

## Integration with LangGraph

All tools are designed to be registered with LangGraph agents:

```python
from backend.tools.poi import poi_search, get_open_hours
from backend.tools.memory import vectordb_retrieve, graphdb_query
from backend.tools.utils import distance_calc, validate_schema

# Register tools with LangGraph
tools = [
    poi_search,
    get_open_hours,
    vectordb_retrieve,
    graphdb_query,
    distance_calc,
    validate_schema
]
```

Each tool includes comprehensive docstrings that LangGraph can use to understand when and how to use the tool.

## Logging

All tools use structured logging with the following levels:

- **DEBUG**: Cache hits/misses, detailed operation info
- **INFO**: Tool calls, successful operations, result counts
- **WARNING**: Fallbacks, degraded mode, retries
- **ERROR**: Failures, validation errors

Example log output:
```
INFO: poi_search_completed city=NYC tags=['museum'] results_count=15 duration_ms=1234
WARNING: vectordb_enrichment_unavailable error="Connection timeout"
ERROR: graphdb_query_failed query="MATCH (p:POI)..." error="Authentication failed"
```
