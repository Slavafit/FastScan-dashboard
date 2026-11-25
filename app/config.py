from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    onza_base_url: str
    onza_login: str
    onza_password: str
    warehouse_id: str
    warehouse_timezone: str
    poll_interval_seconds: int
    database_path: Path
    firebase_credentials_path: Path | None
    include_legacy_firestore: bool
    demo_mode: bool

    @classmethod
    def from_env(cls) -> "Settings":
        credentials = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
        return cls(
            onza_base_url=os.getenv("ONZA_BASE_URL", "https://onza-api.ibm.kg").rstrip("/"),
            onza_login=os.getenv("ONZA_LOGIN", "").strip(),
            onza_password=os.getenv("ONZA_PASSWORD", ""),
            warehouse_id=os.getenv("WAREHOUSE_ID", "es-main").strip() or "es-main",
            warehouse_timezone=os.getenv("WAREHOUSE_TIMEZONE", "Europe/Madrid").strip(),
            poll_interval_seconds=max(10, int(os.getenv("POLL_INTERVAL_SECONDS", "30"))),
            database_path=Path(os.getenv("DATABASE_PATH", "/data/fastscan-dashboard.sqlite3")),
            firebase_credentials_path=Path(credentials) if credentials else None,
            include_legacy_firestore=_bool("INCLUDE_LEGACY_FIRESTORE", True),
            demo_mode=_bool("DASHBOARD_DEMO", False),
        )

    @property
    def onza_configured(self) -> bool:
        return bool(self.onza_login and self.onza_password)

    @property
    def firebase_configured(self) -> bool:
        return bool(
            self.firebase_credentials_path
            and self.firebase_credentials_path.is_file()
        )
