from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "A2 Voice Processing Service"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    db_url: str = "sqlite+aiosqlite:///./a2_voice.db"

    a2_icao_code: str = "VHHH"
    a2_audio_storage: str = "./data/audio"
    a2_chunk_size: int = 65536
    a2_disk_limit_bytes: int = 10 * 1024 * 1024 * 1024
    a2_disk_safe_free_bytes: int = 2 * 1024 * 1024 * 1024

    a3_callback_token: str = "replace-with-secure-token"
    a3_service_base_url: str = "http://localhost:9000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
