"""GraphDB client for Neo4j operations."""

import logging
from typing import Optional, Any
from neo4j import GraphDatabase, Driver, Session, Result
from neo4j.exceptions import ServiceUnavailable, AuthError
from backend.utils.config import settings
from backend.utils.exceptions import (
    GraphDBError,
    TransientError,
    PermanentError,
    ConnectionError as WGConnectionError,
    TimeoutError as WGTimeoutError
)
from backend.utils.retry import retry_with_exponential_backoff

logger = logging.getLogger(__name__)


class GraphDBClient:
    """Client for Neo4j graph database operations."""
    
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        max_connection_pool_size: int = 100
    ):
        """
        Initialize Neo4j driver.
        
        Args:
            uri: Neo4j connection URI (defaults to settings)
            user: Neo4j username (defaults to settings)
            password: Neo4j password (defaults to settings)
            max_connection_pool_size: Maximum number of connections in pool
        """
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.max_connection_pool_size = max_connection_pool_size
        self.driver: Optional[Driver] = None
        
        logger.info(
            "GraphDBClient initialized",
            extra={
                "uri": self.uri[:30] + "..." if self.uri else None,
                "user": self.user,
                "max_pool_size": self.max_connection_pool_size
            }
        )
    
    @retry_with_exponential_backoff(
        max_attempts=3,
        base_delay=1.0,
        retryable_exceptions=(TransientError, WGConnectionError, ServiceUnavailable)
    )
    def connect(self) -> bool:
        """
        Verify connection to Neo4j with authentication.
        
        The Neo4j driver automatically manages a connection pool with the specified
        max_connection_pool_size. Connections are reused efficiently across sessions.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            PermanentError: If authentication fails
            TransientError: If connection fails transiently (will be retried)
            GraphDBError: If connection fails permanently
        """
        try:
            # Create Neo4j driver with connection pooling
            # The driver maintains a pool of connections that are reused across sessions
            # max_connection_pool_size controls the maximum number of connections
            # Note: Don't set encrypted=True when using bolt+s:// or neo4j+s:// URI schemes
            # as encryption is already implied by the URI scheme
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                # Additional connection pool settings for optimization
                connection_acquisition_timeout=60.0,  # seconds
                max_transaction_retry_time=30.0  # seconds
            )
            
            # Verify connectivity by running a simple query
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                record = result.single()
                if record and record["test"] == 1:
                    logger.info(
                        "Successfully connected to Neo4j with connection pooling",
                        extra={"max_pool_size": self.max_connection_pool_size}
                    )
                    return True
                else:
                    raise WGConnectionError(
                        "Connection verification failed",
                        context={"uri": self.uri[:30] + "..."}
                    )
            
        except AuthError as e:
            error_msg = f"Neo4j authentication failed: {str(e)}"
            logger.error(error_msg, extra={"error_type": "AuthError"})
            # Authentication errors are permanent
            raise PermanentError(
                error_msg,
                context={"uri": self.uri[:30] + "...", "user": self.user}
            ) from e
            
        except ServiceUnavailable as e:
            error_msg = f"Neo4j service unavailable: {str(e)}"
            logger.error(error_msg, extra={"error_type": "ServiceUnavailable"})
            # Service unavailable is transient
            raise TransientError(
                error_msg,
                context={"uri": self.uri[:30] + "..."}
            ) from e
            
        except (TransientError, PermanentError, WGConnectionError):
            raise
            
        except Exception as e:
            error_msg = f"Failed to connect to Neo4j: {str(e)}"
            logger.error(error_msg, extra={"error_type": type(e).__name__})
            # Treat unknown errors as transient for retry
            raise TransientError(
                error_msg,
                context={"uri": self.uri[:30] + "...", "original_error": str(e)}
            ) from e
    
    @retry_with_exponential_backoff(
        max_attempts=2,
        base_delay=0.5,
        retryable_exceptions=(TransientError, ServiceUnavailable)
    )
    def execute_query(
        self,
        cypher: str,
        parameters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query with parameters.
        
        Uses parameterized queries to prevent injection attacks.
        Manages transactions automatically.
        
        Args:
            cypher: Cypher query string
            parameters: Query parameters for safe parameterization
            
        Returns:
            List of result records as dictionaries
            
        Raises:
            WGConnectionError: If not connected to Neo4j
            GraphDBError: If query execution fails
            TransientError: If query fails transiently (will be retried)
        """
        if not self.driver:
            raise WGConnectionError(
                "Not connected to Neo4j. Call connect() first.",
                context={"query_preview": cypher[:100]}
            )
        
        try:
            with self.driver.session() as session:
                # Execute query within a transaction
                result = session.run(cypher, parameters or {})
                
                # Convert results to list of dictionaries
                records = []
                for record in result:
                    # Convert Record to dictionary
                    record_dict = dict(record)
                    records.append(record_dict)
                
                logger.debug(
                    "Query executed successfully",
                    extra={
                        "query_preview": cypher[:100],
                        "parameters": parameters,
                        "results_count": len(records)
                    }
                )
                
                return records
                
        except ServiceUnavailable as e:
            error_msg = f"Neo4j service unavailable during query: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "query": cypher[:200],
                    "parameters": parameters,
                    "error_type": "ServiceUnavailable"
                }
            )
            raise TransientError(
                error_msg,
                context={"query_preview": cypher[:200], "parameters": parameters}
            ) from e
            
        except (TransientError, WGConnectionError):
            raise
            
        except Exception as e:
            error_msg = f"Failed to execute query: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "query": cypher[:200],
                    "parameters": parameters,
                    "error_type": type(e).__name__
                }
            )
            raise GraphDBError(
                error_msg,
                context={
                    "query_preview": cypher[:200],
                    "parameters": parameters,
                    "original_error": str(e)
                }
            ) from e
    
    def find_pois_in_neighborhood(
        self,
        city: str,
        neighborhood: str
    ) -> list[dict[str, Any]]:
        """
        Find all POIs in a specific neighborhood.
        
        Args:
            city: City name
            neighborhood: Neighborhood name
            
        Returns:
            List of POI dictionaries with properties
            
        Raises:
            ConnectionError: If not connected to Neo4j
            Exception: If query fails
        """
        cypher = """
        MATCH (p:POI)-[:IN_NEIGHBORHOOD]->(n:Neighborhood)
        WHERE n.name = $neighborhood AND n.city = $city
        RETURN p.id AS id, p.name AS name, p.lat AS lat, p.lon AS lon,
               p.category AS category, p.popularity AS popularity
        """
        
        parameters = {"city": city, "neighborhood": neighborhood}
        
        try:
            results = self.execute_query(cypher, parameters)
            logger.info(
                f"Found {len(results)} POIs in {neighborhood}, {city}",
                extra={"city": city, "neighborhood": neighborhood}
            )
            return results
        except Exception as e:
            logger.error(
                f"Failed to find POIs in neighborhood: {str(e)}",
                extra={"city": city, "neighborhood": neighborhood}
            )
            raise
    
    def find_similar_pois(
        self,
        poi_id: str,
        limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Find similar POIs using SIMILAR_TO relationships.
        
        Args:
            poi_id: POI identifier
            limit: Maximum number of similar POIs to return
            
        Returns:
            List of similar POI dictionaries with similarity scores
            
        Raises:
            ConnectionError: If not connected to Neo4j
            Exception: If query fails
        """
        cypher = """
        MATCH (p:POI {id: $poi_id})-[r:SIMILAR_TO]->(similar:POI)
        RETURN similar.id AS id, similar.name AS name, similar.lat AS lat,
               similar.lon AS lon, similar.category AS category,
               similar.popularity AS popularity, r.score AS similarity_score
        ORDER BY r.score DESC
        LIMIT $limit
        """
        
        parameters = {"poi_id": poi_id, "limit": limit}
        
        try:
            results = self.execute_query(cypher, parameters)
            logger.info(
                f"Found {len(results)} similar POIs for {poi_id}",
                extra={"poi_id": poi_id, "limit": limit}
            )
            return results
        except Exception as e:
            logger.error(
                f"Failed to find similar POIs: {str(e)}",
                extra={"poi_id": poi_id}
            )
            raise
    
    def find_nearby_pois(
        self,
        lat: float,
        lon: float,
        radius_km: float
    ) -> list[dict[str, Any]]:
        """
        Find POIs within radius using NEAR relationships.
        
        Args:
            lat: Latitude of center point
            lon: Longitude of center point
            radius_km: Search radius in kilometers
            
        Returns:
            List of nearby POI dictionaries with distances
            
        Raises:
            ConnectionError: If not connected to Neo4j
            Exception: If query fails
        """
        cypher = """
        MATCH (center:POI)
        WHERE center.lat = $lat AND center.lon = $lon
        MATCH (center)-[r:NEAR]->(nearby:POI)
        WHERE r.distance_km <= $radius_km
        RETURN nearby.id AS id, nearby.name AS name, nearby.lat AS lat,
               nearby.lon AS lon, nearby.category AS category,
               nearby.popularity AS popularity, r.distance_km AS distance_km
        ORDER BY r.distance_km ASC
        """
        
        parameters = {"lat": lat, "lon": lon, "radius_km": radius_km}
        
        try:
            results = self.execute_query(cypher, parameters)
            logger.info(
                f"Found {len(results)} POIs within {radius_km}km",
                extra={"lat": lat, "lon": lon, "radius_km": radius_km}
            )
            return results
        except Exception as e:
            logger.error(
                f"Failed to find nearby POIs: {str(e)}",
                extra={"lat": lat, "lon": lon, "radius_km": radius_km}
            )
            raise
    
    def get_poi_with_booking_info(
        self,
        poi_id: str
    ) -> dict[str, Any]:
        """
        Get POI with ticket provider information via REQUIRES_TICKET relationship.
        
        Args:
            poi_id: POI identifier
            
        Returns:
            POI dictionary with booking information, or empty dict if not found
            
        Raises:
            ConnectionError: If not connected to Neo4j
            Exception: If query fails
        """
        cypher = """
        MATCH (p:POI {id: $poi_id})
        OPTIONAL MATCH (p)-[r:REQUIRES_TICKET]->(tp:TicketProvider)
        RETURN p.id AS id, p.name AS name, p.lat AS lat, p.lon AS lon,
               p.category AS category, p.popularity AS popularity,
               tp.name AS ticket_provider_name, tp.url AS booking_url,
               tp.booking_type AS booking_type, r.advance_days AS advance_days
        """
        
        parameters = {"poi_id": poi_id}
        
        try:
            results = self.execute_query(cypher, parameters)
            
            if not results:
                logger.warning(f"POI not found: {poi_id}")
                return {}
            
            # Return first result (should only be one)
            poi_data = results[0]
            
            logger.info(
                f"Retrieved POI with booking info: {poi_id}",
                extra={
                    "poi_id": poi_id,
                    "has_booking": poi_data.get("booking_url") is not None
                }
            )
            
            return poi_data
            
        except Exception as e:
            logger.error(
                f"Failed to get POI with booking info: {str(e)}",
                extra={"poi_id": poi_id}
            )
            raise
    
    def close(self) -> None:
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j driver connection closed")
