from datetime import date
from types import SimpleNamespace

from app.firestore_source import FirestoreSource, history_dates


class Reference:
    def __init__(self, path: str) -> None:
        self.path = path

    def collection(self, name: str) -> "Reference":
        return Reference(f"{self.path}/{name}")

    def document(self, name: str) -> "Reference":
        return Reference(f"{self.path}/{name}")


class Client:
    def __init__(self) -> None:
        self.read_paths: list[str] = []

    def collection(self, name: str) -> Reference:
        return Reference(name)

    def get_all(self, references: list[Reference]):
        self.read_paths.extend(reference.path for reference in references)
        return []


def test_fetch_reads_only_62_daily_documents_per_aggregate() -> None:
    source = FirestoreSource.__new__(FirestoreSource)
    source._settings = SimpleNamespace(warehouse_id="es-main", warehouse_timezone="Europe/Madrid")
    source._client = Client()

    assert source.fetch() == ([], [])
    assert len(source._client.read_paths) == 124
    assert all("/shipment_daily/" in path or "/client_search_daily/" in path for path in source._client.read_paths)
    assert all("/shipments/" not in path and "/box_entries/" not in path for path in source._client.read_paths)


def test_history_dates_are_calendar_days_not_utc_boundaries() -> None:
    days = history_dates(date(2026, 3, 30))
    assert days[:3] == ["2026-03-30", "2026-03-29", "2026-03-28"]
    assert len(days) == 62
