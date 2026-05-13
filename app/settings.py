from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BRIDGE_",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8080
    config_dir: Path = Path("configs/sources")
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    default_cache_ttl: int = 600
    public_base_url: str = "http://localhost:8080"


settings = Settings()
