"""App settings, read from environment variables / agent/.env.

Everything has a safe default so the server can start (and /health can tell
you what is missing) before every key is filled in.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=AGENT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = ""
    storage_bucket: str = "textbooks"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_embed_dim: int = 768

    # Agent behaviour
    llm_provider: Literal["gemini", "fake"] = "gemini"
    storage_backend: Literal["supabase", "local"] = "supabase"
    local_storage_dir: str = "./storage"
    cors_origins: str = "http://localhost:3000"
    dev_auth: bool = False
    max_upload_mb: int = 100

    # Chunking (tokens are estimated as characters / 4)
    chunk_tokens: int = 600
    chunk_overlap_tokens: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def local_storage_path(self) -> Path:
        p = Path(self.local_storage_dir)
        return p if p.is_absolute() else AGENT_DIR / p

    def missing(self) -> list[str]:
        """Names of env vars that are required for the chosen setup but empty."""
        required: dict[str, str] = {"DATABASE_URL": self.database_url}
        if self.llm_provider == "gemini":
            required["GEMINI_API_KEY"] = self.gemini_api_key
        if self.storage_backend == "supabase":
            required["SUPABASE_URL"] = self.supabase_url
            required["SUPABASE_SERVICE_ROLE_KEY"] = self.supabase_service_role_key
        if not self.dev_auth and not self.supabase_jwt_secret:
            # Without a legacy secret we fall back to the project's JWKS URL.
            required["SUPABASE_URL (or SUPABASE_JWT_SECRET)"] = self.supabase_url
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
