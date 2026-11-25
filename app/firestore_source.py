from __future__ import annotations

from datetime import datetime
from typing import Any

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

    def fetch(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        if self._client is None:
            raise RuntimeError("Firebase service account is not configured")

        warehouse = self._client.collection("warehouses").document(self._settings.warehouse_id)
        shipments = [_document_data(doc) for doc in warehouse.collection("shipments").stream()]
        box_entries = [_document_data(doc) for doc in warehouse.collection("box_entries").stream()]
        searches = [
            _document_data(doc)
            for doc in warehouse.collection("client_search_daily").stream()
        ]

        if self._settings.include_legacy_firestore:
            shipments.extend(_document_data(doc) for doc in self._client.collection("shipments").stream())
            box_entries.extend(_document_data(doc) for doc in self._client.collection("box_entries").stream())

        return shipments, box_entries, searches


def serialize_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None
