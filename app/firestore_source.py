from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from firebase_admin import credentials, firestore, initialize_app

from .config import Settings


def _document_data(snapshot: Any) -> dict[str, Any]:
    data = snapshot.to_dict() or {}
    data["_id"] = snapshot.id
    return data


class FirestoreSource:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None
        if settings.firebase_configured:
            app = initialize_app(
                credentials.Certificate(str(settings.firebase_credentials_path)),
                name=f"fastscan-dashboard-{id(self)}",
            )
            self._client = firestore.client(app=app)

    @property
    def configured(self) -> bool:
        return self._client is not None

    def fetch(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if self._client is None:
            raise RuntimeError("Firebase service account is not configured")

        warehouse = self._client.collection("warehouses").document(self._settings.warehouse_id)
        today = datetime.now(ZoneInfo(self._settings.warehouse_timezone)).date()
        days = history_dates(today)
        shipment_refs = [warehouse.collection("shipment_daily").document(day) for day in days]
        search_refs = [warehouse.collection("client_search_daily").document(day) for day in days]
        shipment_daily = [
            _document_data(doc) for doc in self._client.get_all(shipment_refs) if doc.exists
        ]
        searches = [
            _document_data(doc) for doc in self._client.get_all(search_refs) if doc.exists
        ]
        return shipment_daily, searches


def history_dates(today: date, days: int = 62) -> list[str]:
    return [(today - timedelta(days=offset)).isoformat() for offset in range(days)]


def serialize_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None
