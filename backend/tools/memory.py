"""Memory tools for VectorDB and GraphDB operations."""

from typing import Optional, Any
from ..memory.vectordb import VectorDBClient
from ..memory.graphdb import GraphDBClient
from ..utils.logger import get_logger

logger = get_logger(__name__)


def vectordb_retrieve(
    query: str,
    k: int = 10,
    collection: str = "poi_facts"
) -> list[dict]:
    """
    Perform semantic search on vector database.
    
    Use this tool to find contextually relevant information about POIs,
    booking tips, travel advice, and constraints. The tool performs
    semantic similarity search using embeddings to find documents that
    are conceptually related to your query, not just keyword matches.
    
    Args:
        query: Natural language query describing what you're looking for
        k: Number of results to return (default: 10)
        collection: Collection name to search (default: "poi_facts")
        
    Returns:
        List of documents with similarity scores, sorted by relevance.
        Each document contains the original fields plus a 'similarity_score'.
        Returns empty list if VectorDB is unavailable.
        
    Example:
        # Find booking information
        tips = vectordb_retrieve("statue of liberty booking tips", k=5)
        
        # Find accessibility information
        access = vectordb_retrieve("wheelchair accessible museums NYC", k=3)
        
        # Find seasonal information
        seasonal = vectordb_retrieve("best time to visit central park", k=5)
    """
    try:
        # Validate parameters
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if k <= 0:
            raise ValueError("k must be a positive integer")
        
        if not collection or not collection.strip():
            raise ValueError("Collection name cannot be empty")
        
        # Initialize VectorDB client
        vectordb_client = VectorDBClient()
        
        # Connect to database
        vectordb_client.connect()
        
        logger.info(
            "vectordb_retrieve_started",
            query=query[:100],
            k=k,
            collection=collection
        )
        
        # Perform similarity search
        results = vectordb_client.similarity_search(
            collection_name=collection,
            query=query,
            k=k,
            filters=None
        )
        
        logger.info(
            "vectordb_retrieve_completed",
            query=query[:100],
            results_count=len(results),
            collection=collection
        )
        
        return results
        
    except ValueError as e:
        logger.error(
            "vectordb_retrieve_validation_error",
            error=str(e),
            query=query,
            k=k,
            collection=collection
        )
        raise
    
    except Exception as e:
        logger.error(
            "vectordb_retrieve_failed",
            error=str(e),
            query=query,
            k=k,
            collection=collection
        )
        # Return empty list for graceful degradation
        return []


def graphdb_query(cypher: str, parameters: Optional[dict] = None) -> list[dict]:
    """
    Execute a Cypher query on the graph database.
    
    Use this for relationship queries like finding POIs in neighborhoods,
    similar attractions, nearby locations, or booking requirements.
    Always use parameterized queries for safety.
    
    Args:
        cypher: Cypher query string with parameter placeholders ($param_name)
        parameters: Query parameters for safe execution (default: None)
        
    Returns:
        List of result records as dictionaries.
        Returns empty list if GraphDB is unavailable.
        
    Example:
        # Find POIs in a neighborhood
        query = '''
        MATCH (p:POI)-[:IN_NEIGHBORHOOD]->(n:Neighborhood {name: $name})
        RETURN p.id AS id, p.name AS name, p.lat AS lat, p.lon AS lon
        '''
        pois = graphdb_query(query, {"name": "Lower Manhattan"})
        
        # Find similar POIs
        query = '''
        MATCH (p:POI {id: $poi_id})-[r:SIMILAR_TO]->(similar:POI)
        RETURN similar.name AS name, r.score AS similarity_score
        ORDER BY r.score DESC
        LIMIT 5
        '''
        similar = graphdb_query(query, {"poi_id": "opentripmap:N123"})
        
        # Find POIs requiring tickets
        query = '''
        MATCH (p:POI)-[r:REQUIRES_TICKET]->(tp:TicketProvider)
        WHERE p.city = $city
        RETURN p.name AS poi_name, tp.url AS booking_url, r.advance_days AS advance_days
        '''
        bookings = graphdb_query(query, {"city": "NYC"})
    """
    try:
        # Validate parameters
        if not cypher or not cypher.strip():
            raise ValueError("Cypher query cannot be empty")
        
        # Basic Cypher validation - check for dangerous operations
        cypher_upper = cypher.upper()
        dangerous_keywords = ["DELETE", "DETACH DELETE", "REMOVE", "SET", "CREATE", "MERGE"]
        
        for keyword in dangerous_keywords:
            if keyword in cypher_upper:
                logger.warning(
                    "graphdb_query_dangerous_operation",
                    keyword=keyword,
                    query=cypher[:100]
                )
                # Allow but log warning - in production, you might want to block these
        
        # Initialize GraphDB client
        graphdb_client = GraphDBClient()
        
        # Connect to database
        graphdb_client.connect()
        
        logger.info(
            "graphdb_query_started",
            query=cypher[:100],
            has_parameters=parameters is not None
        )
        
        # Execute query
        results = graphdb_client.execute_query(
            cypher=cypher,
            parameters=parameters
        )
        
        # Close connection
        graphdb_client.close()
        
        logger.info(
            "graphdb_query_completed",
            query=cypher[:100],
            results_count=len(results)
        )
        
        return results
        
    except ValueError as e:
        logger.error(
            "graphdb_query_validation_error",
            error=str(e),
            query=cypher[:100] if cypher else None
        )
        raise
    
    except Exception as e:
        logger.error(
            "graphdb_query_failed",
            error=str(e),
            query=cypher[:100] if cypher else None
        )
        # Return empty list for graceful degradation
        return []
