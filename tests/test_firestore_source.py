from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.firestore_source import FirestoreSource


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


def test_fetch_reads_only_today_aggregate_documents() -> None:
    source = FirestoreSource.__new__(FirestoreSource)
    source._settings = SimpleNamespace(warehouse_id="es-main", warehouse_timezone="Europe/Madrid")
    source._client = Client()

    today = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    assert source.fetch() == ([], [])
    assert len(source._client.read_paths) == 2
    assert all("/shipment_daily/" in path or "/client_search_daily/" in path for path in source._client.read_paths)
    assert all(path.endswith(f"/{today}") for path in source._client.read_paths)
    assert all("/shipments/" not in path and "/box_entries/" not in path for path in source._client.read_paths)
