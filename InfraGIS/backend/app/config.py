from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://infragis:infragis@localhost:5432/infragis"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    admin_login: str | None = None
    admin_password: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: str = "uploads"
    max_upload_mb: int = 50

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
