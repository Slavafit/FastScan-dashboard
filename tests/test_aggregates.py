from datetime import datetime
from zoneinfo import ZoneInfo

from app.aggregates import build_dashboard_data


def test_build_dashboard_data_deduplicates_orders_and_aggregates_today() -> None:
    timezone = ZoneInfo("Europe/Madrid")
    now = datetime.now(timezone)
    shipments = [
        {"trackingNumber": " A-1 ", "weight": 2.5, "createdAt": now},
        {"trackingNumber": "A1", "weight": 9.0, "createdAt": now},
        {"trackingNumber": "B-2", "weight": 3.5, "createdAt": now},
    ]
    boxes = [
        {
            "guid": "box-1",
            "tracking_code": "NBX1",
            "date_created": now.isoformat(),
            "orderCount": 2,
            "gross_weight": 6,
        }
    ]
    searches = [
        {"date": now.date().isoformat(), "total": 5, "found": 4, "not_found": 1}
    ]

    result = build_dashboard_data(shipments, searches, boxes, [], "Europe/Madrid")

    assert result["summary"]["orders"] == 2
    assert result["summary"]["weight"] == 12.5
    assert result["summary"]["boxes"] == 1
    assert result["summary"]["searches"] == 5


def test_party_uses_loaded_box_totals_instead_of_partial_summary() -> None:
    timezone = ZoneInfo("Europe/Madrid")
    now = datetime.now(timezone)
    boxes = [
        {
            "guid": "box-1",
            "tracking_code": "NBX1",
            "partial": "party-1",
            "date_created": now.isoformat(),
            "orderCount": 12,
            "gross_weight": 23.4,
        }
    ]
    parties = [
        {
            "guid": "party-1",
            "partial_name": "KG200",
            "status": 0,
            "boxCount": 99,
            "gross_weight": 1,
        }
    ]

    result = build_dashboard_data([], [], boxes, parties, "Europe/Madrid")
    party = result["parties"][0]

    assert party["box_count"] == 1
    assert party["order_count"] == 12
    assert party["gross_weight"] == 23.4


def test_parties_are_sorted_from_newest_to_oldest() -> None:
    parties = [
        {"guid": "old", "partial_name": "KG1", "date_created": "2026-10-01T10:00:00Z"},
        {"guid": "missing", "partial_name": "KG0", "date_created": None},
        {"guid": "new", "partial_name": "KG2", "date_created": "2026-11-25T10:00:00Z"},
    ]

    result = build_dashboard_data([], [], [], parties, "Europe/Madrid")

    assert [party["guid"] for party in result["parties"]] == ["new", "old", "missing"]
