from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./data/recyclink-api.sqlite"
    secret_key: str = "development-only-change-this-secret-key"
    frontend_origin: str = "http://127.0.0.1:5173"
    image_upload_max_mb: int = 8
    ml_model_path: str | None = None
    ml_model_version: str = "untrained"
    ml_min_confidence: float = 0.55
    ml_device: str = "auto"
    osrm_base_url: str | None = None
    route_timeout_seconds: float = 8.0
    bin_warning_fill_percent: float = 75.0
    bin_high_fill_percent: float = 90.0
    bin_critical_fill_percent: float = 100.0
    bin_stale_after_hours: int = 2
    elevenlabs_api_key: str | None = None
    elevenlabs_agent_id: str | None = None
    elevenlabs_api_base_url: str = "https://api.elevenlabs.io/v1"

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore")

    @model_validator(mode="after")
    def require_production_secret(self) -> "Settings":
        if self.app_env.lower() == "production" and len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        if self.image_upload_max_mb < 1 or self.image_upload_max_mb > 20:
            raise ValueError("IMAGE_UPLOAD_MAX_MB must be between 1 and 20")
        if not 0 < self.ml_min_confidence < 1:
            raise ValueError("ML_MIN_CONFIDENCE must be between 0 and 1")
        if not 1 <= self.route_timeout_seconds <= 60:
            raise ValueError("ROUTE_TIMEOUT_SECONDS must be between 1 and 60")
        if not 0 < self.bin_warning_fill_percent < self.bin_high_fill_percent < self.bin_critical_fill_percent <= 100:
            raise ValueError("Bin fill thresholds must increase from warning through critical and be at most 100")
        if not 1 <= self.bin_stale_after_hours <= 168:
            raise ValueError("BIN_STALE_AFTER_HOURS must be between 1 and 168")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
