from backend.core.config import settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = settings.rag_llm_model
EMBEDDING_MODEL = settings.rag_embedding_model
TOP_K = settings.rag_top_k

PINECONE_API_KEY = settings.pinecone_api_key
PINECONE_INDEX = settings.pinecone_index_name
PINECONE_CLOUD = settings.pinecone_cloud
PINECONE_REGION = settings.pinecone_region
