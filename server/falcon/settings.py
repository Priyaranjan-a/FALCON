"""Deployment settings.

Every field can be overridden with a ``FALCON_``-prefixed environment variable
(for example ``FALCON_DATABASE_URL`` or ``FALCON_PORT``) or a ``.env`` file in
the repository root.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SERVER_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FALCON_", env_file=REPO_DIR / ".env", extra="ignore"
    )

    environment: Literal["development", "production", "test"] = "development"
    host: str = "127.0.0.1"
    port: int = 8600

    data_dir: Path = REPO_DIR / "data"
    database_url: str | None = None

    # Sessions: sliding idle timeout plus a hard absolute lifetime.
    session_idle_minutes: int = Field(default=120, ge=5, le=24 * 60)
    session_absolute_hours: int = Field(default=12, ge=1, le=24 * 30)
    secure_cookies: bool | None = None  # defaults to True in production

    # Brute-force protection.
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    login_rate_per_minute: int = 20

    invitation_valid_hours: int = 72
    console_dist: Path = REPO_DIR / "console" / "dist"
    cors_origins: list[str] = []

    # Desktop mode: single user on their own machine (set by the desktop shell).
    desktop: bool = False

    # Discovery engine.
    scan_workers: int = Field(default=2, ge=1, le=8)
    scan_timeout_minutes: int = Field(default=60, ge=1, le=24 * 60)
    scan_max_files: int = Field(default=200_000, ge=100)
    scan_max_file_mb: int = Field(default=16, ge=1, le=512)
    upload_max_mb: int = Field(default=2048, ge=1)
    # Server mode: folders may be scanned only under these roots (desktop mode allows any folder).
    scan_roots: list[Path] = []
    # Live probing of TLS endpoints. Defaults to on for desktop, off for servers.
    allow_network_probes: bool | None = None
    registry_username: str | None = None
    registry_password: SecretStr | None = None

    # First-run demonstration (``falcon serve --demo``): seeds an organisation, an
    # admin account, systems and scans of the bundled sample estates when FALCON
    # is not set up yet. The credentials are printed at start-up.
    demo: bool = False
    demo_admin_email: str = "admin@falcon.local"
    demo_admin_password: SecretStr = SecretStr("Quantum-Safe-2026!")
    demo_benchmarks: bool = True

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'falcon.db').as_posix()}"

    @property
    def cookies_secure(self) -> bool:
        if self.secure_cookies is not None:
            return self.secure_cookies
        return self.environment == "production"

    @property
    def network_probes_allowed(self) -> bool:
        return self.allow_network_probes if self.allow_network_probes is not None else self.desktop

    @property
    def any_folder_allowed(self) -> bool:
        """Desktop and development installs may scan any readable folder."""
        return self.desktop or self.environment == "development"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "work"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
