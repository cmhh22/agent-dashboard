"""
Configuration settings for the Agent Dashboard backend.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    # LLM Configuration (supports OpenAI, GitHub Models, OpenRouter, Groq)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://models.inference.ai.azure.com"  # GitHub Models free tier
    
    # Vector Database
    vector_db_path: str = "./data/chroma_db"
    vector_db_collection: str = "agent_documents"
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = "https://models.inference.ai.azure.com"
    
    # FastAPI Configuration
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "info"
    cors_origins: List[str] = ["http://localhost:4200"]
    
    # Agent Configuration
    agent_max_iterations: int = 10
    agent_timeout: int = 60
    
    # RAG Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 5
    
    # Redis Configuration (optional)
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0


settings = Settings()
