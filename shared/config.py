

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


    openrouter_api_key: str = Field(..., validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        ..., validation_alias=AliasChoices("OPENROUTER_MODEL", "LLM_MODEL_NAME")
    )
    pinecone_api_key: str = Field(..., validation_alias="PINECONE_API_KEY")
    pinecone_index_name: str = Field(..., validation_alias="PINECONE_INDEX_NAME")
    pinecone_dimension: int = Field(..., validation_alias="PINECONE_DIMENSION")
    embedding_model: str = Field(..., validation_alias="EMBEDDING_MODEL")


    llm_temperature: float = Field(default=0.2, validation_alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, validation_alias="LLM_MAX_TOKENS")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", validation_alias="OPENROUTER_BASE_URL"
    )


    pinecone_cloud: str = Field(default="aws", validation_alias="PINECONE_CLOUD")
    pinecone_region: str = Field(default="us-east-1", validation_alias="PINECONE_REGION")
    pinecone_metric: str = Field(default="cosine", validation_alias="PINECONE_METRIC")


    rag_top_k: int = Field(default=5, validation_alias="RAG_TOP_K")
    chunk_size: int = Field(default=500, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, validation_alias="CHUNK_OVERLAP")
    load_kb_on_startup: bool = Field(default=False, validation_alias="LOAD_KB_ON_STARTUP")


    database_url: str = Field(
        default="sqlite:///./data/healthlink.db", validation_alias="DATABASE_URL"
    )
    db_echo: bool = Field(default=False, validation_alias="DB_ECHO")
    db_pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    db_pool_recycle_seconds: int = Field(
        default=1800, validation_alias="DB_POOL_RECYCLE_SECONDS"
    )


    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    enable_metrics: bool = Field(default=True, validation_alias="ENABLE_METRICS")
    langchain_tracing_v2: bool | None = Field(
        default=None, validation_alias="LANGCHAIN_TRACING_V2"
    )
    langchain_api_key: str | None = Field(
        default=None, validation_alias="LANGCHAIN_API_KEY"
    )
    langchain_project: str = Field(default="healthlink", validation_alias="LANGCHAIN_PROJECT")


    secret_key: str = Field(
        default="dev-secret-key-change-in-production", validation_alias="SECRET_KEY"
    )
    rate_limit_max: int = Field(default=20, validation_alias="RATE_LIMIT_MAX")
    rate_limit_window: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW")


    cors_origins: str = Field(default="*", validation_alias="CORS_ORIGINS")
    api_base_url: str = Field(
        default="http://localhost:8000/api/v1", validation_alias="API_BASE_URL"
    )
    kb_file: str = Field(default="./data/symptoms_kb.json", validation_alias="KB_FILE")
    doctors_csv: str = Field(default="./data/doctors.csv", validation_alias="DOCTORS_CSV")
    gcp_region: str = Field(default="us-central1", validation_alias="GCP_REGION")

def get_settings() -> Settings:

    return Settings()
