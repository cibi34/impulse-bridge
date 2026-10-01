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

    # Curated collections (created by users in the web app, stored in SQLite).
    database_path: Path | None = None
    """SQLite file for curated collections; default: <data_dir>/curator.db."""
    collection_owner_id: str = "impulse-curator"
    """`owner_id` published for every curated collection (Impulse metadata).
    Deliberately not the creator's email: collection metadata is public."""
    default_organization: str = "IMPULSE Curator"
    """`organization` for curated collections whose creator left it empty."""
    max_assets_per_collection: int = 500

    # Email (SMTP account and recipients are set in the admin UI).
    smtp_password: str | None = None
    """Overrides the SMTP password stored via the admin UI, for operators who
    keep secrets in the environment only."""
    mail_log_only: bool = False
    """Development: log emails (incl. login links) instead of sending them."""

    # CORS. Comma-separated list of origins allowed to call the API from a
    # browser (cross-origin fetch/XHR), e.g. the Impulse web frontend served
    # from a different domain than the bridge. "*" allows any origin. Override
    # per deployment with BRIDGE_CORS_ALLOW_ORIGINS (e.g.
    # "https://app.example.org,https://staging.example.org").
    cors_allow_origins: str = "*"

    @property
    def database_file(self) -> Path:
        return self.database_path or self.data_dir / "curator.db"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()
