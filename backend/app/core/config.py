"""Central settings — the only place the environment is read.

Pydantic Settings as in the FastAPI docs:
https://fastapi.tiangolo.com/advanced/settings/
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    frontend_origin: str = "http://localhost:3000"

    # Session wall (D42). When false, /auth/dev-session is disabled.
    dev_auth: bool = False
    dev_session_secret: str = "dev-only-not-for-production"

    groq_api_key: str = ""
    # Extra Groq keys tried in order when the primary hits rate limits.
    # Comma-separated; GROQ_API_KEY may also be comma-separated.
    groq_api_key_fallbacks: str = ""
    # Groq deprecations: llama-3.3-70b-versatile shut down 2026-08-16.
    groq_model: str = "openai/gpt-oss-120b"
    # Multimodal model for image evidence (D39). Llama-4 was retired from
    # Groq's catalog; qwen3.6-27b accepts image_url parts (verified live 2026-08-19).
    groq_vision_model: str = "qwen/qwen3.6-27b"

    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    local_upload_dir: str = "./data/uploads"

    serpapi_key: str = ""

    job_worker_enabled: bool = False
    skip_migrations: bool = False

    # Local embedding model (D70) - not an API key gate, a test-hermeticity
    # switch. EmbeddingGemma-300M has no "absent key" state the way the old
    # Gemini adapter did, so conftest.py forces this false to keep the sqlite
    # suite from loading a 300M-param model on every run.
    embeddings_enabled: bool = True

    # Retrieval policy. These are environment-configurable so production
    # behavior is not tied to a particular fixture, document type, or query.
    rag_top_k: int = 5
    rag_candidate_pool: int = 20
    rag_vector_similarity_floor: float = 0.35
    rag_rrf_k: int = 60
    rag_exact_weight: float = 1.35
    rag_fts_weight: float = 1.0
    rag_fts_min_rank: float = 0.15
    rag_vector_weight: float = 1.0
    rag_max_context_chars: int = 6000
    rag_trace_enabled: bool = True

    # Docling's HybridChunker token cap (D71) - environment-configurable for
    # the same reason as the rag_* settings above: not tied to a particular
    # document type or fixture. Matches chunk_text()'s legacy ~1200-char/
    # ~250-token granularity (D64) by default.
    docling_max_chunk_tokens: int = 256

    # Microsoft personal OneDrive (D85). Empty client id → OAuth disabled;
    # onedrive_local_mirror_dir writes the same folder layout to disk for
    # hermetic tests / demos without Azure.
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:8000/auth/microsoft/callback"
    microsoft_tenant: str = "consumers"
    onedrive_local_mirror_dir: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
