
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_healthlink.db")

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("OPENROUTER_MODEL", "openai/gpt-4o-mini")
os.environ.setdefault("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("LLM_TEMPERATURE", "0.2")
os.environ.setdefault("LLM_MAX_TOKENS", "2048")
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-key")
os.environ.setdefault("PINECONE_INDEX_NAME", "healthlink-test")
os.environ.setdefault("PINECONE_DIMENSION", "1024")
os.environ.setdefault("EMBEDDING_MODEL", "snowflake-arctic-embed2")
os.environ.setdefault("PINECONE_CLOUD", "aws")
os.environ.setdefault("PINECONE_REGION", "us-east-1")
os.environ.setdefault("PINECONE_METRIC", "cosine")
os.environ.setdefault("RAG_TOP_K", "5")
os.environ.setdefault("CHUNK_SIZE", "500")
os.environ.setdefault("CHUNK_OVERLAP", "50")
os.environ.setdefault("LOAD_KB_ON_STARTUP", "false")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
os.environ.setdefault("DB_ECHO", "false")
os.environ.setdefault("DB_POOL_SIZE", "10")
os.environ.setdefault("DB_MAX_OVERFLOW", "20")
os.environ.setdefault("DB_POOL_RECYCLE_SECONDS", "1800")
os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("ENABLE_METRICS", "true")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_API_KEY", "")
os.environ.setdefault("LANGCHAIN_PROJECT", "healthlink")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000/api/v1")
os.environ.setdefault("KB_FILE", "./data/symptoms_kb.json")
os.environ.setdefault("DOCTORS_CSV", "./data/doctors.csv")
os.environ.setdefault("GCP_REGION", "us-central1")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("RATE_LIMIT_MAX", "20")
os.environ.setdefault("RATE_LIMIT_WINDOW", "60")
os.environ.setdefault("CORS_ORIGINS", "*")

import pytest
from fastapi.testclient import TestClient

from app.database import reset_db_manager
from app.rag import reset_vector_store


@pytest.fixture()
def client():

    reset_db_manager()
    reset_vector_store()

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    import app.main as main_module
    from app.main import app
    from app.security import RateLimiter


    main_module.rate_limiter = RateLimiter(max_requests=20, window_seconds=60)

    with TestClient(app) as test_client:
        yield test_client

    reset_db_manager()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.fixture()
def doctor_names(client):

    response = client.get("/api/v1/doctors")
    assert response.status_code == 200
    return [doctor["name"] for doctor in response.json()]
