from pathlib import Path
from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parents[1] / ".env"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _build_postgres_url(
    prefix: str,
    host: str | None,
    port: str | int | None,
    name: str | None,
    user: str | None,
    password: str | None,
) -> str:
    missing = []
    if not host:
        missing.append(f"{prefix}_HOST")
    if not name:
        missing.append(f"{prefix}_NAME")
    if not user:
        missing.append(f"{prefix}_USER")
    if missing:
        raise ValueError(f"Missing database settings: {', '.join(missing)}")

    safe_user = quote(str(user), safe="")
    safe_password = quote(str(password or ""), safe="")
    safe_name = quote(str(name), safe="")
    host_part = str(host)
    port_part = f":{port}" if port else ""
    return f"postgresql://{safe_user}:{safe_password}@{host_part}{port_part}/{safe_name}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str | None = None
    bureau_database_url: str | None = None
    db_host: str | None = None
    db_port: str = "5432"
    db_name: str | None = None
    db_user: str | None = None
    db_password: str = ""
    bureau_db_host: str | None = None
    bureau_db_port: str | None = None
    bureau_db_name: str | None = None
    bureau_db_user: str | None = None
    bureau_db_password: str | None = None

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
    rag_fastembed_cache_path: str = str(PROJECT_ROOT / ".cache" / "fastembed")

    # RAG retrieval Stage 2 (reranker)
    rag_reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"
    rag_reranker_enabled: bool = True
    rag_reranker_candidate_k: int = 20
    rag_reranker_top_k: int = 12

    # RAG loan adjustment reasoner (soft-propose / hard-verify)
    rag_loan_reasoner_enabled: bool = True

    # RAG memory (V1: window + summary buffer)
    rag_memory_window_token_budget: int = 2000
    rag_memory_summary_max_tokens: int = 500
    rag_memory_min_messages_to_summarize: int = 6

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "creditintel-kb"

    @model_validator(mode="after")
    def build_database_urls(self) -> "Settings":
        if not self.database_url:
            self.database_url = _build_postgres_url(
                "DB",
                self.db_host,
                self.db_port,
                self.db_name,
                self.db_user,
                self.db_password,
            )

        if not self.bureau_database_url:
            has_bureau_config = any(
                [
                    self.bureau_db_host,
                    self.bureau_db_port,
                    self.bureau_db_name,
                    self.bureau_db_user,
                    self.bureau_db_password,
                ]
            )
            if has_bureau_config:
                self.bureau_database_url = _build_postgres_url(
                    "BUREAU_DB",
                    self.bureau_db_host or self.db_host,
                    self.bureau_db_port or self.db_port,
                    self.bureau_db_name or self.db_name,
                    self.bureau_db_user or self.db_user,
                    self.bureau_db_password if self.bureau_db_password is not None else self.db_password,
                )
            else:
                self.bureau_database_url = self.database_url

        return self


settings = Settings()
