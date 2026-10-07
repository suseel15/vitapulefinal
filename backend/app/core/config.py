from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="VitaPulse Backend", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, ge=1, le=65535, validation_alias="PORT")
    supabase_url: str = Field(default="", validation_alias="SUPABASE_URL")
    supabase_publishable_key: str = Field(default="", validation_alias="SUPABASE_PUBLISHABLE_KEY")
    supabase_service_role_key: str = Field(default="", validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    ocr_enabled: bool = Field(default=False, validation_alias="OCR_ENABLED")
    ocr_provider: str = Field(default="ocrmypdf", validation_alias="OCR_PROVIDER")
    ocrmy_pdf_enabled: bool = Field(default=True, validation_alias="OCRMY_PDF_ENABLED")
    ocr_languages: str = Field(default="eng", validation_alias="OCR_LANGUAGES")
    ocr_timeout_seconds: int = Field(default=300, ge=10, le=1800, validation_alias="OCR_TIMEOUT_SECONDS")
    ocr_executable: str = Field(default="ocrmypdf", validation_alias="OCR_EXECUTABLE")
    max_upload_size_mb: int = Field(default=25, ge=1, le=25, validation_alias="MAX_UPLOAD_SIZE_MB")
    medical_report_bucket: Literal["medical-reports"] = Field(
        default="medical-reports",
        validation_alias="MEDICAL_REPORT_BUCKET",
    )
    health_report_bucket: str = Field(default="reports", validation_alias="HEALTH_REPORT_BUCKET")
    report_storage_bucket: str = Field(default="reports", validation_alias="REPORT_STORAGE_BUCKET")
    reports_enabled: bool = Field(default=True, validation_alias="REPORTS_ENABLED")
    report_signed_url_expiry_seconds: int = Field(
        default=900,
        ge=60,
        le=3600,
        validation_alias="REPORT_SIGNED_URL_EXPIRY_SECONDS",
    )
    report_default_template_version: str = Field(default="v1", validation_alias="REPORT_DEFAULT_TEMPLATE_VERSION")
    pdf_generation_enabled: bool = Field(default=True, validation_alias="PDF_GENERATION_ENABLED")
    signed_url_expiry_seconds: int = Field(
        default=900,
        ge=60,
        le=3600,
        validation_alias="SIGNED_URL_EXPIRY_SECONDS",
    )
    skin_screening_enabled: bool = Field(default=False, validation_alias="SKIN_SCREENING_ENABLED")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="", validation_alias="GEMINI_MODEL")
    gemini_enabled: bool = Field(default=True, validation_alias="GEMINI_ENABLED")
    gemini_timeout_seconds: int = Field(default=60, ge=5, le=180, validation_alias="GEMINI_TIMEOUT_SECONDS")
    gemini_max_retries: int = Field(default=2, ge=0, le=5, validation_alias="GEMINI_MAX_RETRIES")
    gemini_temperature: float = Field(default=0.2, ge=0.0, le=1.0, validation_alias="GEMINI_TEMPERATURE")
    ai_provider: Literal["gemini"] = Field(default="gemini", validation_alias="AI_PROVIDER")
    athlete_intelligence_enabled: bool = Field(default=True, validation_alias="ATHLETE_INTELLIGENCE_ENABLED")
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:4173", "http://localhost:4173"],
        validation_alias="CORS_ORIGINS",
    )
    smtp_enabled: bool = Field(default=False, validation_alias="SMTP_ENABLED")
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", validation_alias="SMTP_FROM_EMAIL")
    fcm_enabled: bool = Field(default=False, validation_alias="FCM_ENABLED")
    enable_real_emergency_escalation: bool = Field(
        default=False, validation_alias="ENABLE_REAL_EMERGENCY_ESCALATION"
    )
    demo_mode_enabled: bool = Field(default=False, validation_alias="DEMO_MODE_ENABLED")
    ml_enabled: bool = Field(default=False, validation_alias="ML_ENABLED")
    ml_local_inference_enabled: bool = Field(default=False, validation_alias="ML_LOCAL_INFERENCE_ENABLED")
    ml_model_directory: Path = Field(default=Path("models"), validation_alias="ML_MODEL_DIRECTORY")
    ml_default_model_version: str = Field(default="v1", validation_alias="ML_DEFAULT_MODEL_VERSION")
    movement_min_sampling_rate_hz: float = Field(default=8.0, gt=0, le=100, validation_alias="MOVEMENT_MIN_SAMPLING_RATE_HZ")
    movement_window_ms: int = Field(default=3000, ge=1000, le=10_000, validation_alias="MOVEMENT_WINDOW_MS")
    movement_step_ms: int = Field(default=1000, ge=100, le=10_000, validation_alias="MOVEMENT_STEP_MS")
    baseline_min_sessions: int = Field(default=3, ge=1, le=100, validation_alias="BASELINE_MIN_SESSIONS")
    baseline_min_repetitions: int = Field(default=20, ge=1, le=1000, validation_alias="BASELINE_MIN_REPETITIONS")
    anomaly_detection_enabled: bool = Field(default=True, validation_alias="ANOMALY_DETECTION_ENABLED")
    fatigue_engine_enabled: bool = Field(default=True, validation_alias="FATIGUE_ENGINE_ENABLED")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("supabase_url")
    @classmethod
    def strip_supabase_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def supabase_is_configured(self) -> bool:
        if not self.supabase_url or not self.supabase_publishable_key:
            return False
        try:
            parsed_url = urlsplit(self.supabase_url)
            port = parsed_url.port
            secure_url = parsed_url.scheme == "https" and bool(parsed_url.hostname)
            local_development_url = (
                self.app_env == "development"
                and parsed_url.scheme == "http"
                and parsed_url.hostname in {"localhost", "127.0.0.1"}
            )
            return (
                (secure_url or local_development_url)
                and parsed_url.path in {"", "/"}
                and (port is None or 1 <= port <= 65535)
                and parsed_url.username is None
                and parsed_url.password is None
                and parsed_url.query == ""
                and parsed_url.fragment == ""
            )
        except ValueError:
            return False

    @property
    def supabase_storage_is_configured(self) -> bool:
        return self.supabase_is_configured and bool(self.supabase_service_role_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
