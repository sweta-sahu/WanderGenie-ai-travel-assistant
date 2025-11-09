"""Singleton pattern implementation for database client reuse."""

import threading
from typing import Dict, Any, Optional, Type, TypeVar


T = TypeVar('T')


class SingletonMeta(type):
    """
    Thread-safe Singleton metaclass.
    
    This metaclass ensures that only one instance of a class exists per set of
    initialization parameters. Different parameter combinations create different instances.
    """
    
    _instances: Dict[tuple, Any] = {}
    _lock: threading.Lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        """
        Create or return existing instance based on initialization parameters.
        
        Args:
            *args: Positional arguments for class initialization
            **kwargs: Keyword arguments for class initialization
            
        Returns:
            Singleton instance of the class
        """
        # Create a key from the class and its initialization parameters
        # This allows different parameter combinations to have different instances
        key = (cls, args, tuple(sorted(kwargs.items())))
        
        # Double-checked locking pattern for thread safety
        if key not in cls._instances:
            with cls._lock:
                if key not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[key] = instance
        
        return cls._instances[key]
    
    @classmethod
    def clear_instances(cls):
        """Clear all singleton instances (useful for testing)."""
        with cls._lock:
            cls._instances.clear()


class ClientPool:
    """
    Generic client pool for managing database connections.
    
    This class provides a simple connection pool that reuses clients
    and manages their lifecycle.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize client pool.
        
        Args:
            max_size: Maximum number of clients in the pool
        """
        self.max_size = max_size
        self._clients: Dict[str, Any] = {}
        self._lock = threading.Lock()
    
    def get_client(
        self,
        client_id: str,
        client_class: Type[T],
        *args,
        **kwargs
    ) -> T:
        """
        Get or create a client from the pool.
        
        Args:
            client_id: Unique identifier for this client configuration
            client_class: Class to instantiate if client doesn't exist
            *args: Positional arguments for client initialization
            **kwargs: Keyword arguments for client initialization
            
        Returns:
            Client instance
        """
        with self._lock:
            if client_id not in self._clients:
                if len(self._clients) >= self.max_size:
                    # Pool is full, remove oldest client
                    oldest_id = next(iter(self._clients))
                    old_client = self._clients.pop(oldest_id)
                    
                    # Close old client if it has a close method
                    if hasattr(old_client, 'close'):
                        try:
                            old_client.close()
                        except Exception:
                            pass
                
                # Create new client
                self._clients[client_id] = client_class(*args, **kwargs)
            
            return self._clients[client_id]
    
    def remove_client(self, client_id: str) -> None:
        """
        Remove a client from the pool.
        
        Args:
            client_id: Unique identifier for the client
        """
        with self._lock:
            if client_id in self._clients:
                client = self._clients.pop(client_id)
                
                # Close client if it has a close method
                if hasattr(client, 'close'):
                    try:
                        client.close()
                    except Exception:
                        pass
    
    def clear(self) -> None:
        """Clear all clients from the pool."""
        with self._lock:
            for client in self._clients.values():
                if hasattr(client, 'close'):
                    try:
                        client.close()
                    except Exception:
                        pass
            
            self._clients.clear()
    
    def size(self) -> int:
        """Get current pool size."""
        with self._lock:
            return len(self._clients)


# Global client pools for reuse
_vectordb_pool = ClientPool(max_size=10)
_graphdb_pool = ClientPool(max_size=10)


def get_vectordb_client(*args, **kwargs):
    """
    Get or create a VectorDB client from the pool.
    
    This function ensures client reuse across the application.
    
    Args:
        *args: Positional arguments for VectorDBClient
        **kwargs: Keyword arguments for VectorDBClient
        
    Returns:
        VectorDBClient instance
    """
    from backend.memory.vectordb import VectorDBClient
    
    # Create client ID from parameters
    client_id = f"vectordb_{args}_{tuple(sorted(kwargs.items()))}"
    
    return _vectordb_pool.get_client(client_id, VectorDBClient, *args, **kwargs)


def get_graphdb_client(*args, **kwargs):
    """
    Get or create a GraphDB client from the pool.
    
    This function ensures client reuse across the application.
    
    Args:
        *args: Positional arguments for GraphDBClient
        **kwargs: Keyword arguments for GraphDBClient
        
    Returns:
        GraphDBClient instance
    """
    from backend.memory.graphdb import GraphDBClient
    
    # Create client ID from parameters
    client_id = f"graphdb_{args}_{tuple(sorted(kwargs.items()))}"
    
    return _graphdb_pool.get_client(client_id, GraphDBClient, *args, **kwargs)


def clear_all_pools():
    """Clear all client pools (useful for testing and cleanup)."""
    _vectordb_pool.clear()
    _graphdb_pool.clear()
