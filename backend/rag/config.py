from core.config import settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = settings.rag_llm_model
EMBEDDING_MODEL = settings.rag_embedding_model
BM25_SPARSE_MODEL = settings.rag_bm25_model
FASTEMBED_CACHE_DIR = settings.rag_fastembed_cache_path
RERANKER_MODEL = settings.rag_reranker_model
RERANKER_ENABLED = settings.rag_reranker_enabled
RERANKER_CANDIDATE_K = settings.rag_reranker_candidate_k
RERANKER_TOP_K = settings.rag_reranker_top_k
TOP_K = settings.rag_top_k

QDRANT_URL = settings.qdrant_url
QDRANT_API_KEY = settings.qdrant_api_key or None
QDRANT_COLLECTION = settings.qdrant_collection
