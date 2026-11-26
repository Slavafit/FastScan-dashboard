from datetime import datetime
from zoneinfo import ZoneInfo

from app.aggregates import build_dashboard_data


def test_build_dashboard_data_uses_daily_order_aggregate() -> None:
    timezone = ZoneInfo("Europe/Madrid")
    now = datetime.now(timezone)
    shipment_daily = [
        {"date": now.date().isoformat(), "count": 2, "total_weight": 12.5},
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

    result = build_dashboard_data(shipment_daily, searches, boxes, [], "Europe/Madrid")

    assert result["summary"]["orders"] == 2
    assert result["summary"]["weight"] == 12.5
    assert result["summary"]["boxes"] == 1
    assert result["summary"]["searches"] == 5


def test_invalid_daily_values_cannot_make_totals_negative() -> None:
    today = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    result = build_dashboard_data(
        [{"date": today, "count": -1, "total_weight": -5}], [], [], [], "Europe/Madrid"
    )
    assert result["summary"]["orders"] == 0
    assert result["summary"]["weight"] == 0


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
