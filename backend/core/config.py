from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # OpenRouter
    openrouter_api_key: str
    rag_llm_model: str = "google/gemini-flash-1.5"
    rag_embedding_model: str = "openai/text-embedding-3-small"
    rag_top_k: int = 4

    # Pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "creditintel-kb"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    class Config:
        env_file = ".env"


settings = Settings()
