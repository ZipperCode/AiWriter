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

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
