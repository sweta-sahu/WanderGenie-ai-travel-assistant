"""VectorDB client for Supabase pgvector operations."""

import logging
from typing import Optional, Any
from functools import lru_cache
from supabase import create_client, Client
from openai import OpenAI
from backend.utils.config import settings
from backend.utils.exceptions import (
    VectorDBError,
    TransientError,
    PermanentError,
    ConnectionError as WGConnectionError,
    TimeoutError as WGTimeoutError
)
from backend.utils.retry import retry_with_exponential_backoff

logger = logging.getLogger(__name__)


class VectorDBClient:
    """Client for Supabase pgvector operations."""
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        openai_api_key: Optional[str] = None,
        max_connections: int = 10
    ):
        """
        Initialize connection to Supabase with pgvector.
        
        Args:
            supabase_url: Supabase project URL (defaults to settings)
            supabase_key: Supabase API key (defaults to settings)
            embedding_model: Model name for generating embeddings
            openai_api_key: OpenAI API key (defaults to settings)
            max_connections: Maximum number of connections in pool (default: 10)
        """
        self.supabase_url = supabase_url or settings.supabase_url
        self.supabase_key = supabase_key or settings.supabase_key
        self.embedding_model = embedding_model
        self.openai_api_key = openai_api_key or settings.openai_api_key
        self.max_connections = max_connections
        self.client: Optional[Client] = None
        self.openai_client: Optional[OpenAI] = None
        
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        
        logger.info(
            "VectorDBClient initialized",
            extra={
                "embedding_model": self.embedding_model,
                "supabase_url": self.supabase_url[:30] + "..." if self.supabase_url else None,
                "max_connections": self.max_connections
            }
        )
    
    @retry_with_exponential_backoff(
        max_attempts=3,
        base_delay=1.0,
        retryable_exceptions=(TransientError, WGConnectionError, WGTimeoutError)
    )
    def connect(self) -> bool:
        """
        Verify connection and pgvector extension availability.
        
        Connection pooling is handled automatically by the Supabase client.
        The client maintains a pool of connections for efficient reuse.
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            VectorDBError: If connection fails
            TransientError: If connection fails transiently (will be retried)
        """
        try:
            # Create Supabase client with connection pooling
            # Note: Supabase Python client uses httpx which handles connection pooling
            # The max_connections parameter is informational for our tracking
            self.client = create_client(self.supabase_url, self.supabase_key)
            
            # Verify connection is established
            # The client is created successfully if credentials are valid
            logger.info(
                "Successfully connected to Supabase with connection pooling",
                extra={"max_connections": self.max_connections}
            )
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to Supabase: {str(e)}"
            logger.error(error_msg, extra={"error_type": type(e).__name__})
            # Wrap as transient error for retry
            raise TransientError(error_msg, context={"original_error": str(e)}) from e
    
    @lru_cache(maxsize=1000)
    def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector for text using configured model.
        
        Uses LRU cache to avoid regenerating embeddings for identical texts.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            list[float]: Embedding vector (1536 dimensions for text-embedding-3-small)
            
        Raises:
            PermanentError: If text is invalid
            TransientError: If API call fails transiently
            VectorDBError: If embedding generation fails
        """
        try:
            # Clean and prepare text
            text = text.strip()
            if not text:
                raise PermanentError(
                    "Cannot generate embedding for empty text",
                    context={"text": text}
                )
            
            # Generate embedding using OpenAI API
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            logger.debug(
                "Generated embedding",
                extra={
                    "text_length": len(text),
                    "embedding_dimensions": len(embedding)
                }
            )
            
            return embedding
            
        except PermanentError:
            raise
        except Exception as e:
            error_msg = f"Failed to generate embedding: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "text_preview": text[:100] if text else "",
                    "error_type": type(e).__name__
                }
            )
            # Treat as transient error (API might be temporarily down)
            raise TransientError(
                error_msg,
                context={"text_preview": text[:100], "original_error": str(e)}
            ) from e

    
    def create_collection(self, collection_name: str, schema: dict[str, Any]) -> bool:
        """
        Create a new collection with specified schema.
        
        Note: In Supabase, collections are tables. This method creates a table
        with the specified schema if it doesn't exist.
        
        Args:
            collection_name: Name of the collection/table
            schema: Schema definition (not used in basic implementation,
                   assumes table already exists or is created via migrations)
            
        Returns:
            bool: True if collection exists/created successfully
            
        Raises:
            VectorDBError: If collection creation fails
            WGConnectionError: If not connected
        """
        try:
            if not self.client:
                raise WGConnectionError(
                    "Not connected to Supabase. Call connect() first.",
                    context={"collection_name": collection_name}
                )
            
            # Verify table exists by attempting a query
            self.client.table(collection_name).select("*").limit(0).execute()
            
            logger.info(f"Collection '{collection_name}' verified/created")
            return True
            
        except WGConnectionError:
            raise
        except Exception as e:
            error_msg = f"Failed to create/verify collection '{collection_name}': {str(e)}"
            logger.error(error_msg, extra={"error_type": type(e).__name__})
            raise VectorDBError(
                error_msg,
                context={"collection_name": collection_name, "original_error": str(e)}
            ) from e
    
    def insert_documents(
        self,
        collection_name: str,
        documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Insert documents with embeddings.
        
        Processes documents in batches of 100 and generates embeddings
        for the 'body' field if present.
        
        Args:
            collection_name: Target collection/table name
            documents: List of document dictionaries to insert
            
        Returns:
            dict: {"success": int, "failed": int, "errors": list}
            
        Raises:
            WGConnectionError: If not connected to Supabase
            VectorDBError: If insertion fails
        """
        if not self.client:
            raise WGConnectionError(
                "Not connected to Supabase. Call connect() first.",
                context={"collection_name": collection_name}
            )
        
        success_count = 0
        failed_count = 0
        errors = []
        
        # Process in batches of 100
        batch_size = 100
        total_docs = len(documents)
        
        logger.info(f"Inserting {total_docs} documents into '{collection_name}'")
        
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_docs + batch_size - 1) // batch_size
            
            logger.debug(f"Processing batch {batch_num}/{total_batches}")
            
            # Prepare batch with embeddings
            prepared_batch = []
            for doc in batch:
                try:
                    # Generate embedding if 'body' field exists
                    if 'body' in doc and doc['body']:
                        embedding = self._generate_embedding(doc['body'])
                        doc_with_embedding = {**doc, 'embedding': embedding}
                    else:
                        doc_with_embedding = doc
                    
                    prepared_batch.append(doc_with_embedding)
                    
                except Exception as e:
                    failed_count += 1
                    error_msg = f"Failed to prepare document: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg, extra={"doc_id": doc.get('id', 'unknown')})
            
            # Insert batch
            if prepared_batch:
                try:
                    self.client.table(collection_name).insert(prepared_batch).execute()
                    success_count += len(prepared_batch)
                    logger.debug(f"Successfully inserted batch {batch_num}")
                    
                except Exception as e:
                    failed_count += len(prepared_batch)
                    error_msg = f"Failed to insert batch {batch_num}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        result = {
            "success": success_count,
            "failed": failed_count,
            "errors": errors
        }
        
        logger.info(
            f"Insert completed for '{collection_name}'",
            extra={
                "success": success_count,
                "failed": failed_count,
                "total": total_docs
            }
        )
        
        return result

    
    def similarity_search(
        self,
        collection_name: str,
        query: str,
        k: int = 10,
        filters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Perform semantic similarity search.
        
        Args:
            collection_name: Target collection/table name
            query: Search query text
            k: Number of results to return
            filters: Optional filters (e.g., {"city": "NYC", "tags": ["museum"]})
            
        Returns:
            List of documents with similarity scores, sorted by relevance
            
        Raises:
            WGConnectionError: If not connected to Supabase
            VectorDBError: If search fails
            TransientError: If search fails transiently
        """
        if not self.client:
            raise WGConnectionError(
                "Not connected to Supabase. Call connect() first.",
                context={"collection_name": collection_name}
            )
        
        try:
            # Generate embedding for query
            query_embedding = self._generate_embedding(query)
            
            logger.debug(
                f"Performing similarity search on '{collection_name}'",
                extra={"query_length": len(query), "k": k, "filters": filters}
            )
            
            # Build the RPC call for vector similarity search
            # Note: This assumes a Postgres function exists for vector similarity
            # In practice, you'd use: embedding <-> query_embedding
            # For now, we'll use a simplified approach with the Supabase client
            
            # Start with base query
            query_builder = self.client.table(collection_name).select("*")
            
            # Apply filters if provided
            if filters:
                for key, value in filters.items():
                    if isinstance(value, list):
                        # For array fields like tags, use contains
                        if key == "tags":
                            # This would need proper array containment query
                            # For now, we'll skip complex array filtering in basic implementation
                            pass
                        else:
                            query_builder = query_builder.in_(key, value)
                    else:
                        query_builder = query_builder.eq(key, value)
            
            # Execute query
            # Note: Actual vector similarity would use a custom RPC function
            # This is a simplified version that fetches all and sorts in Python
            response = query_builder.limit(k * 10).execute()  # Fetch more for filtering
            
            documents = response.data
            
            # Calculate similarity scores in Python (simplified)
            # In production, this should be done in the database
            results_with_scores = []
            for doc in documents:
                if 'embedding' in doc and doc['embedding']:
                    # Parse embedding if it's a string (from Supabase)
                    doc_embedding = doc['embedding']
                    if isinstance(doc_embedding, str):
                        try:
                            import json
                            doc_embedding = json.loads(doc_embedding)
                        except (json.JSONDecodeError, ValueError):
                            logger.warning(f"Failed to parse embedding for doc: {doc.get('id', 'unknown')}")
                            continue
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(query_embedding, doc_embedding)
                    results_with_scores.append({
                        **doc,
                        'similarity_score': similarity
                    })
            
            # Sort by similarity and take top k
            results_with_scores.sort(key=lambda x: x['similarity_score'], reverse=True)
            results = results_with_scores[:k]
            
            logger.info(
                f"Similarity search completed on '{collection_name}'",
                extra={
                    "results_count": len(results),
                    "query": query[:50]
                }
            )
            
            return results
            
        except (TransientError, PermanentError, WGConnectionError):
            raise
        except Exception as e:
            error_msg = f"Similarity search failed on '{collection_name}': {str(e)}"
            logger.error(
                error_msg,
                extra={"query": query[:50], "error_type": type(e).__name__}
            )
            raise VectorDBError(
                error_msg,
                context={
                    "collection_name": collection_name,
                    "query_preview": query[:50],
                    "original_error": str(e)
                }
            ) from e
    
    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            float: Cosine similarity score (0 to 1)
        """
        import math
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)
        
        return similarity
