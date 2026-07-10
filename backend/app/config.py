from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LocalRAG Intelligent Retrieval Platform"
    database_url: str = (
        "postgresql://retrieval:local_development_only@localhost:5432/retrieval"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    retrieval_cache_ttl_seconds: int = 300
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    llm_provider: str = "ollama"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 768
    upload_dir: str = "/data/uploads"
    jwt_secret: str = "local_development_secret_change_before_deployment"
    jwt_expiration_minutes: int = 10080
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
