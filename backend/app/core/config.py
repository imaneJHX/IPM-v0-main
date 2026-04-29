"""Pydantic Settings — all environment variables for the IPM backend."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # --- Database ---
    database_url: str = "postgresql+asyncpg://ipm:ipm@postgres:5432/ipm"

    # --- ChromaDB ---
    chroma_host: str = "chromadb"
    chroma_port: int = 8001
    chroma_path: str = "./.chroma"

    # --- MinIO ---
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False

    # --- LLM Provider ---
    llm_provider: str = "groq"  # "groq" | "azure"
    groq_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-02-15-preview"

    # --- Embedding Provider ---
    embedding_provider: str = "local"  # "local" | "openai"
    openai_api_key: str = ""
    embedding_model_local: str = "BAAI/bge-small-en-v1.5"
    embedding_model_openai: str = "text-embedding-ada-002"

    # --- Langfuse ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Tech Signals — Tavily ---
    tavily_api_key: str = ""
    tavily_max_results: int = 5        # fixed for v0, never increase on free tier
    tavily_search_depth: str = "basic"  # NEVER change to "advanced" on free tier

    # --- CORS ---
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
