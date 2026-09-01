from pathlib import Path
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    data_dir: Path = BACKEND_ROOT / "data"
    registry_db_path: Path = BACKEND_ROOT / "data" / "registry.db"
    sessions_dir: Path = BACKEND_ROOT / "data" / "sessions"
    uploads_dir: Path = BACKEND_ROOT / "data" / "uploads"

    # Comma-separated list, e.g. "https://app.example.com,https://staging.example.com".
    # Defaults to the Vite dev server origins so local dev keeps working with
    # zero config; production deployments must set this explicitly.
    cors_origins_raw: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Max upload size in bytes for a UCS/QKView/conf file. Real UCS archives
    # can run tens to low hundreds of MB; default generously but boundedly
    # so a stray multi-GB upload can't exhaust disk.
    max_upload_bytes: int = 512 * 1024 * 1024

    model_config = {"env_prefix": "CFGI_"}

    @model_validator(mode="after")
    def _derive_data_subdirs_from_data_dir(self) -> "Settings":
        """registry_db_path/sessions_dir/uploads_dir each have their own
        env var, but the common case (e.g. Docker's CFGI_DATA_DIR=/data) is
        overriding just data_dir and expecting everything under it to
        follow. model_fields_set only contains fields actually supplied
        (via env or the constructor) -- not ones left at their class
        default -- so this only re-derives a field the caller didn't
        already set explicitly."""
        if "data_dir" in self.model_fields_set:
            if "registry_db_path" not in self.model_fields_set:
                self.registry_db_path = self.data_dir / "registry.db"
            if "sessions_dir" not in self.model_fields_set:
                self.sessions_dir = self.data_dir / "sessions"
            if "uploads_dir" not in self.model_fields_set:
                self.uploads_dir = self.data_dir / "uploads"
        return self

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
