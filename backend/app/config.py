from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://aiwriter:aiwriter_dev@localhost/aiwriter"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Auth
    auth_token: str = "dev-token-change-me"

    # Embedding
    embedding_dim: int = 1536

    # RAG settings
    rag_top_k: int = 20
    rag_top_m: int = 5
    rag_rrf_k: int = 60
    jina_api_key: str = ""
    jina_rerank_model: str = "jina-reranker-v2-base-multilingual"

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Rate limiting
    llm_rate_limit_max: int = 60  # max requests per window
    llm_rate_limit_window: int = 60  # window in seconds

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    # Encryption - Generate via: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str = ""

    # Storage
    storage_dir: str = "./storage"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
