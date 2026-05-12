"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    google_api_key: str = ""  # Alias for gemini_api_key

    @property
    def effective_gemini_key(self) -> str:
        """Return Gemini API key (supports both GEMINI_API_KEY and GOOGLE_API_KEY)."""
        return self.gemini_api_key or self.google_api_key

    # Database
    database_url: str = "sqlite:///./medishield.db"

    # Vector Store
    chroma_persist_dir: str = "./chroma_db"

    # LangSmith Tracing (optional)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "medishield"

    # Model Configuration
    classifier_model: str = "claude-sonnet-4-20250514"
    vision_model: str = "claude-sonnet-4-20250514"

    # Rate Limiting
    request_delay_seconds: float = 1.0
    max_retries: int = 3

    # Document Categories
    document_categories: list[str] = [
        "Patient Bills",
        "Claim Forms",
        "KYC Documents",
        "Medical Reports",
        "Prescriptions",
        "Policy Documents",
        "Unknown",
    ]

    # Queue Routing
    queue_routing: dict[str, str] = {
        "Patient Bills": "billing_queue",
        "Claim Forms": "claims_queue",
        "KYC Documents": "verification_queue",
        "Medical Reports": "medical_review_queue",
        "Prescriptions": "medical_review_queue",
        "Policy Documents": "policy_ingestion_queue",
        "Unknown": "manual_review_queue",
    }

    @property
    def project_root(self) -> Path:
        """Return the project root directory."""
        return Path(__file__).parent.parent

    @property
    def dataset_dir(self) -> Path:
        """Return the dataset directory path."""
        return self.project_root / "dataset"

    @property
    def policies_dir(self) -> Path:
        """Return the policies directory path."""
        return self.project_root / "policies"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
