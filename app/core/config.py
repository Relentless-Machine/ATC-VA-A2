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
    a2_liveatc_search_url: str = "https://www.liveatc.net/search/?icao={icao}"
    a2_liveatc_base_url: str = "https://www.liveatc.net"
    a2_liveatc_archive_base_url: str = "https://archive.liveatc.net"
    a2_liveatc_mount_ids: str = "vhhh5"
    a2_liveatc_archive_file_prefixes: str = "VHHH5-App-Dep-Dir-Zone"
    a2_historical_candidate_slots: int = 8
    a2_liveatc_realtime_stream_url: str = ""
    a2_realtime_capture_seconds: int = 60
    a2_realtime_capture_max_bytes: int = 2 * 1024 * 1024
    a2_realtime_half_hour_seconds: int = 30 * 60
    a2_realtime_interval_seconds: int = 30 * 60
    a2_historical_interval_seconds: int = 60 * 60
    a2_scheduler_interval_jitter_seconds: int = 5 * 60
    a2_liveatc_human_delay_min_seconds: float = 5.0
    a2_liveatc_human_delay_max_seconds: float = 45.0
    a2_liveatc_download_gap_min_seconds: float = 3.0
    a2_liveatc_download_gap_max_seconds: float = 20.0
    a2_historical_max_files_per_run: int = 5
    a2_auto_start_scheduler: bool = True
    a2_http_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    a2_http_accept_language: str = "en-US,en;q=0.9,zh-CN;q=0.8"
    a2_http_max_retries: int = 2
    a2_http_backoff_base_seconds: float = 1.0
    a2_http_backoff_max_seconds: float = 30.0
    a2_http_cookie: str = ""

    a3_callback_token: str = "replace-with-secure-token"
    a3_service_base_url: str = "http://localhost:9000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
