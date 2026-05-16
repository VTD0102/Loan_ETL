import importlib.util
import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAG_DIR = BACKEND_DIR / "rag"
sys.path.insert(0, str(BACKEND_DIR))


def load_rag_config():
    required_env = {
        "DB_HOST": "localhost",
        "DB_NAME": "loan_etl",
        "DB_USER": "postgres",
        "DB_PASSWORD": "postgres",
        "SECRET_KEY": "test-secret",
        "OPENROUTER_API_KEY": "test-openrouter-key",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_COLLECTION": "creditintel-kb",
        "QDRANT_API_KEY": "",
    }
    for key, value in required_env.items():
        os.environ.setdefault(key, value)

    spec = importlib.util.spec_from_file_location("rag_config_under_test", RAG_DIR / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rag_config_exposes_qdrant_settings():
    config = load_rag_config()

    assert config.QDRANT_URL == "http://localhost:6333"
    assert config.QDRANT_COLLECTION == "creditintel-kb"
    assert config.QDRANT_API_KEY is None


def test_rag_modules_use_qdrant_not_pinecone():
    checked_files = [
        RAG_DIR / "config.py",
        RAG_DIR / "ingest.py",
        RAG_DIR / "retriever.py",
        RAG_DIR / "__init__.py",
    ]
    combined_source = "\n".join(path.read_text(encoding="utf-8") for path in checked_files)

    assert "pinecone" not in combined_source.lower()
    assert "QdrantVectorStore" in combined_source
    assert "QDRANT_COLLECTION" in combined_source
    assert "upsert_to_qdrant" in combined_source


def test_retriever_module_imports_without_eager_chain_side_effects():
    load_rag_config()

    import importlib

    retriever = importlib.import_module("rag.retriever")

    assert callable(retriever.get_retriever)


if __name__ == "__main__":
    test_rag_config_exposes_qdrant_settings()
    test_rag_modules_use_qdrant_not_pinecone()
    test_retriever_module_imports_without_eager_chain_side_effects()
    print("RAG Qdrant config tests passed")
