from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    catalog_path: Path = Path("data/catalog.seed.json")
    cache_path: Path = Path("data/cache.json")
    cache_namespace: str = "style-agent-v5"

    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    allow_embedding_fallback: bool = True

    vector_backend: str = "local_json"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "quickeee_catalog"
    qdrant_recreate_on_startup: bool = True
    allow_local_vector_fallback: bool = True

    llm_provider: str = "local"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"

    scraper_delay_min_seconds: float = 0.8
    scraper_delay_max_seconds: float = 2.2
    scraper_timeout_seconds: float = 30.0

    rate_limit_per_minute: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
