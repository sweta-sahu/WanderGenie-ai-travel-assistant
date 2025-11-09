"""Configuration management using Pydantic Settings."""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    opentripmap_api_key: str
    openai_api_key: str
    
    # Supabase (VectorDB)
    supabase_url: str
    supabase_key: str
    supabase_service_key: Optional[str] = None
    
    # Neo4j (GraphDB)
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    
    # App Configuration
    environment: str = "development"
    log_level: str = "INFO"
    cache_dir: str = "./data"
    enable_cache: bool = True
    
    # Performance Settings
    max_concurrent_requests: int = 10
    request_timeout: int = 30
    
    class Config:
        """Pydantic configuration."""
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
