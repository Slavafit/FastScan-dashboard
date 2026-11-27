from datetime import datetime
from zoneinfo import ZoneInfo

from app.aggregates import build_dashboard_data, merge_daily_history


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


def test_onza_boxes_backfill_daily_orders_and_weight_when_no_exact_aggregate_exists() -> None:
    day = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    boxes = [
        {"guid": "box-1", "date_created": f"{day}T09:00:00+01:00", "orderCount": 4, "gross_weight": 12.5},
        {"guid": "box-2", "date_created": f"{day}T11:00:00+01:00", "orderCount": 3, "gross_weight": 8.0},
    ]

    result = build_dashboard_data([], [], boxes, [], "Europe/Madrid")

    assert result["summary"]["orders"] == 7
    assert result["summary"]["weight"] == 20.5


def test_exact_firestore_aggregate_overrides_onza_backfill_for_same_day() -> None:
    day = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    boxes = [{"guid": "box-1", "date_created": f"{day}T09:00:00+01:00", "orderCount": 4, "gross_weight": 12.5}]

    result = build_dashboard_data(
        [{"date": day, "count": 2, "total_weight": 7.25}], [], boxes, [], "Europe/Madrid"
    )

    assert result["summary"]["orders"] == 2
    assert result["summary"]["weight"] == 7.25


def test_onza_backfill_replaces_old_zero_rows_but_retains_days_without_boxes() -> None:
    fresh = [
        {"day": "2026-11-25", "orders": 7, "weight": 20.5, "boxes": 2, "searches": 0, "found": 0, "not_found": 0, "errors": 0},
        {"day": "2026-11-24", "orders": 0, "weight": 0, "boxes": 0, "searches": 0, "found": 0, "not_found": 0, "errors": 0},
    ]
    stored = [
        {"day": "2026-11-25", "orders_count": 0, "total_weight": 0, "boxes_count": 2, "client_searches": 0, "searches_found": 0, "searches_not_found": 0, "search_errors": 0},
        {"day": "2026-11-24", "orders_count": 9, "total_weight": 18.2, "boxes_count": 1, "client_searches": 3, "searches_found": 3, "searches_not_found": 0, "search_errors": 0},
    ]

    result = merge_daily_history(fresh, stored, "2026-11-26")

    by_day = {row["day"]: row for row in result}
    assert by_day["2026-11-25"]["orders"] == 7
    assert by_day["2026-11-24"]["orders"] == 9


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
