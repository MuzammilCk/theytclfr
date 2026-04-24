from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    database_pool_size: int = 5
    redis_url: str
    temp_media_path: str = "/tmp/ytclfr_media"
    temp_media_max_age_seconds: int = 3600
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    llm_request_timeout_seconds: int = 120
    llm_max_retries: int = 3
    whisper_model_size: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    tesseract_cmd_path: str = "tesseract"
    ocr_frame_sample_rate: int = 1
    ytdlp_cookies_file: str | None = None
    router_frame_sample_count: int = 5
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    worker_concurrency: int = 2
    celery_task_time_limit: int = 1800
    log_level: str = "INFO"
    environment: str = "development"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    s3_bucket_name: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore
