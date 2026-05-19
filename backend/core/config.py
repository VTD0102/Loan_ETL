from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # OpenRouter
    openrouter_api_key: str
    rag_llm_model: str = "google/gemini-2.5-flash"
    rag_embedding_model: str = "openai/text-embedding-3-small"
    rag_top_k: int = 4

    # RAG timeouts / retries (seconds)
    rag_llm_timeout_seconds: float = 30.0
    rag_llm_max_retries: int = 2
    rag_embedding_timeout_seconds: float = 10.0
    rag_embedding_max_retries: int = 2
    rag_qdrant_timeout_seconds: float = 5.0

    # RAG retrieval (V1: hybrid BM25 + vector)
    rag_bm25_model: str = "Qdrant/bm25"

    # RAG retrieval Stage 2 (reranker)
    rag_reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    rag_reranker_enabled: bool = True
    rag_reranker_candidate_k: int = 20
    rag_reranker_top_k: int = 12

    # RAG memory (V1: window + summary buffer)
    rag_memory_window_token_budget: int = 2000
    rag_memory_summary_max_tokens: int = 500
    rag_memory_min_messages_to_summarize: int = 6

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "creditintel-kb"


settings = Settings()
