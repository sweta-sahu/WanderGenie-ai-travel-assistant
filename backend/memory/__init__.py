"""
Memory layer initialization and convenience functions.

This module provides simplified access to VectorDB and GraphDB for agent nodes.
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Global client instances
_vectordb_client: Optional[Any] = None
_graphdb_client: Optional[Any] = None


def vectordb_retrieve(query: str, k: int = 10, collection_name: str = "poi_facts") -> List[Dict[str, Any]]:
    """
    Convenience function to perform vector similarity search.
    
    Args:
        query: Search query text
        k: Number of results to return (default: 10)
        collection_name: Collection to search in (default: "poi_facts")
        
    Returns:
        List of matching documents with similarity scores
        Returns empty list if VectorDB is unavailable or search fails
    """
    global _vectordb_client
    
    try:
        # Lazy import and initialization
        if _vectordb_client is None:
            from backend.memory.vectordb import VectorDBClient
            _vectordb_client = VectorDBClient()
            _vectordb_client.connect()
            logger.info("VectorDBClient initialized")
        
        results = _vectordb_client.similarity_search(collection_name, query, k=k)
        logger.info(f"VectorDB retrieve: found {len(results)} results for query: {query[:50]}")
        return results
        
    except Exception as e:
        # Fail gracefully - VectorDB is optional for MVP
        logger.warning(f"VectorDB retrieve failed, returning empty results: {e}")
        return []


def graphdb_query(city: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Convenience function to query POIs from GraphDB for a given city.
    
    Args:
        city: City name to query POIs for
        limit: Maximum number of POIs to return (default: 20)
        
    Returns:
        List of POI dictionaries with neighborhood relationships
        Returns empty list if GraphDB is unavailable or query fails
    """
    global _graphdb_client
    
    try:
        # Lazy import and initialization
        if _graphdb_client is None:
            from backend.memory.graphdb import GraphDBClient
            _graphdb_client = GraphDBClient()
            _graphdb_client.connect()
            logger.info("GraphDBClient initialized")
        
        # Query for POIs in the specified city with neighborhood relationships
        # Query only fields we know exist to avoid Neo4j warnings about
        # non-existent property keys or relationship types in empty schemas.
        cypher_query = """
        MATCH (p:POI {city: $city})
        WHERE p.lat IS NOT NULL AND p.lon IS NOT NULL
        RETURN p.name AS name,
               p.lat AS lat,
               p.lon AS lon
        LIMIT $limit
        """
        
        params = {"city": city, "limit": limit}
        results = _graphdb_client.execute_query(cypher_query, params)
        
        # Convert Neo4j results to POI dictionaries
        pois = []
        for record in results:
            poi = {
                "name": record.get("name"),
                "lat": record.get("lat"),
                "lon": record.get("lon"),
                # Provide safe defaults for optional fields that may not exist in DB
                "tags": record.get("tags", []),
                "duration_min": record.get("duration_min", 60),
                "booking_required": record.get("booking_required", False),
                "booking_url": record.get("booking_url"),
                "notes": record.get("notes"),
                "neighborhood": record.get("neighborhood")
            }
            pois.append(poi)
        
        logger.info(f"GraphDB query: found {len(pois)} POIs for city: {city}")
        return pois
        
    except Exception as e:
        # Fail gracefully - GraphDB is optional for MVP
        logger.warning(f"GraphDB query failed, returning empty results: {e}")
        return []
