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

    # CORS. Comma-separated list of origins allowed to call the API from a
    # browser (cross-origin fetch/XHR), e.g. the Impulse web frontend served
    # from a different domain than the bridge. "*" allows any origin. Override
    # per deployment with BRIDGE_CORS_ALLOW_ORIGINS (e.g.
    # "https://app.example.org,https://staging.example.org").
    cors_allow_origins: str = "*"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()
