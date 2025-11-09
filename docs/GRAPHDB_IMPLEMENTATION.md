# GraphDB Implementation

## Overview

This document describes the Neo4j GraphDB client implementation for the WanderGenie AI travel assistant.

## Implementation Summary

### GraphDBClient Class

Location: `backend/memory/graphdb.py`

The `GraphDBClient` class provides a clean interface for interacting with Neo4j graph database, supporting:

1. **Connection Management**
   - Neo4j driver initialization with connection pooling (max 100 connections)
   - Authentication and connection verification
   - Proper error handling for auth failures and service unavailability

2. **Core Query Execution**
   - Parameterized Cypher query execution to prevent injection attacks
   - Automatic transaction management
   - Result formatting to dictionaries
   - Comprehensive error handling and logging

3. **Helper Query Methods**
   - `find_pois_in_neighborhood()` - Find all POIs in a specific neighborhood
   - `find_similar_pois()` - Find similar POIs using SIMILAR_TO relationships
   - `find_nearby_pois()` - Find POIs within a radius using NEAR relationships
   - `get_poi_with_booking_info()` - Get POI with ticket provider information

## Usage Examples

### Basic Connection

```python
from backend.memory.graphdb import GraphDBClient

# Initialize client (uses settings from .env by default)
client = GraphDBClient()

# Connect to Neo4j
client.connect()

# Use the client...

# Close connection when done
client.close()
```

### Custom Configuration

```python
client = GraphDBClient(
    uri="neo4j://localhost:7687",
    user="neo4j",
    password="password",
    max_connection_pool_size=50
)
```

### Execute Custom Queries

```python
# Simple query
results = client.execute_query("MATCH (n:POI) RETURN n LIMIT 10")

# Parameterized query (recommended)
cypher = "MATCH (p:POI {id: $poi_id}) RETURN p"
results = client.execute_query(cypher, {"poi_id": "statue-of-liberty"})
```

### Find POIs in Neighborhood

```python
pois = client.find_pois_in_neighborhood("NYC", "Lower Manhattan")

for poi in pois:
    print(f"{poi['name']} - {poi['category']}")
```

### Find Similar POIs

```python
similar = client.find_similar_pois("statue-of-liberty", limit=5)

for poi in similar:
    print(f"{poi['name']} - Similarity: {poi['similarity_score']}")
```

### Find Nearby POIs

```python
# Find POIs within 1km of coordinates
nearby = client.find_nearby_pois(
    lat=40.689,
    lon=-74.044,
    radius_km=1.0
)

for poi in nearby:
    print(f"{poi['name']} - {poi['distance_km']}km away")
```

### Get POI with Booking Information

```python
poi = client.get_poi_with_booking_info("statue-of-liberty")

if poi:
    print(f"Name: {poi['name']}")
    if poi.get('booking_url'):
        print(f"Book at: {poi['booking_url']}")
        print(f"Advance booking: {poi['advance_days']} days")
```

## Graph Schema

### Node Types

- **City**: `{name, country, lat, lon}`
- **Neighborhood**: `{name, city, center_lat, center_lon}`
- **POI**: `{id, name, lat, lon, category, popularity}`
- **TicketProvider**: `{name, url, booking_type}`

### Relationship Types

- **IN_NEIGHBORHOOD**: POI → Neighborhood
- **SIMILAR_TO**: POI → POI `{score}`
- **REQUIRES_TICKET**: POI → TicketProvider `{advance_days}`
- **NEAR**: POI → POI `{distance_km}`

## Testing

All functionality is covered by comprehensive unit tests in `tests/test_graphdb_client.py`:

- Connection management tests (8 tests)
- Query execution tests (5 tests)
- Helper method tests (6 tests)

Run tests:
```bash
python -m pytest tests/test_graphdb_client.py -v
```

## Configuration

Required environment variables in `.env`:

```bash
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

## Error Handling

The client implements robust error handling:

- **AuthError**: Raised when authentication fails
- **ConnectionError**: Raised when Neo4j service is unavailable or connection fails
- **Exception**: Raised for query execution failures with detailed error messages

All errors are logged with context for debugging.

## Performance Considerations

- Connection pooling with configurable max connections (default: 100)
- Parameterized queries for security and performance
- Automatic transaction management
- Efficient result formatting

## Next Steps

The GraphDB client is now ready for:
1. Database seeding with NYC POI data
2. Integration with tool registry functions
3. Use by LangGraph agents for relationship queries

## Requirements Satisfied

✅ Requirement 3.1: Connection management with authentication and verification  
✅ Requirement 3.4: Core query execution with parameterization  
✅ Requirement 3.5: Finding similar POIs via SIMILAR_TO relationships  
✅ Requirement 3.6: Finding POIs with booking information  
✅ Requirement 3.7: Query performance and transaction management
