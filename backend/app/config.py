"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Orion application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://orion:orion_secret@localhost:5433/orion"
    )

    # ── Redis ────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── LLM ──────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"

    # ── Embeddings ───────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "gemini"
    EMBEDDING_MODEL: str = "text-embedding-004"

    # ── Enrichment APIs ──────────────────────────────────────
    PROXYCURL_API_KEY: str = "mock"
    HUNTER_API_KEY: str = "mock"
    CLEARBIT_API_KEY: str = "mock"
    BUILTWITH_API_KEY: str = "mock"

    # ── Feature Flags ────────────────────────────────────────
    USE_MOCK_ENRICHMENT: bool = True
    USE_MOCK_SIGNALS: bool = True
    ENABLE_INBOUND_WEBHOOKS: bool = True
    MOCK_SMTP_MODE: str = "deterministic"
    MOCK_SMTP_BOUNCE_DOMAINS: str = "bounce.test"
    MOCK_SMTP_REPLY_DOMAINS: str = "reply.test"
    MOCK_SMTP_BOUNCE_RATE: float = 0.0
    MOCK_SMTP_REPLY_RATE: float = 0.0
    MOCK_SMTP_RANDOM_SEED: int = 42

    # ── Thresholds ───────────────────────────────────────────
    AUTO_PERSONALIZE_THRESHOLD: float = 0.75
    AUTO_ENROLL_ICP_THRESHOLD: float = 70.0
    CRITIQUE_REWRITE_THRESHOLD: float = 7.0


settings = Settings()
