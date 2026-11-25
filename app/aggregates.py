from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _day(value: Any, timezone: ZoneInfo) -> str | None:
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone)
        return aware.astimezone(timezone).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone)
            return parsed.astimezone(timezone).date().isoformat()
        except ValueError:
            return normalized[:10] if len(normalized) >= 10 else None
    return None


def normalize_tracking(value: Any) -> str:
    return "".join(character for character in _text(value).upper() if character.isalnum())


def build_dashboard_data(
    shipments: list[dict[str, Any]],
    searches: list[dict[str, Any]],
    boxes: list[dict[str, Any]],
    parties: list[dict[str, Any]],
    timezone_name: str,
    history_days: int = 62,
) -> dict[str, Any]:
    timezone = ZoneInfo(timezone_name)
    today = datetime.now(timezone).date()
    first_day = today - timedelta(days=history_days - 1)
    daily: dict[str, dict[str, Any]] = {
        (first_day + timedelta(days=offset)).isoformat(): {
            "day": (first_day + timedelta(days=offset)).isoformat(),
            "orders": 0,
            "weight": 0.0,
            "boxes": 0,
            "searches": 0,
            "found": 0,
            "not_found": 0,
            "errors": 0,
        }
        for offset in range(history_days)
    }

    unique_shipments: dict[str, dict[str, Any]] = {}
    for shipment in shipments:
        tracking = normalize_tracking(shipment.get("trackingNumber") or shipment.get("tracking_number"))
        if tracking:
            unique_shipments[tracking] = shipment
    for shipment in unique_shipments.values():
        day = _day(shipment.get("createdAt") or shipment.get("dateString"), timezone)
        if day in daily:
            daily[day]["orders"] += 1
            daily[day]["weight"] += max(0.0, _number(shipment.get("weight")))

    normalized_boxes: list[dict[str, Any]] = []
    seen_boxes: set[str] = set()
    for raw in boxes:
        guid = _text(raw.get("guid"))
        tracking = _text(raw.get("tracking_code"))
        identity = guid or normalize_tracking(tracking)
        if not identity or identity in seen_boxes:
            continue
        seen_boxes.add(identity)
        created_at = _text(raw.get("date_created")) or None
        day = _day(created_at, timezone)
        if day in daily:
            daily[day]["boxes"] += 1
        normalized_boxes.append(
            {
                "guid": identity,
                "tracking_code": tracking,
                "partial_guid": _text(raw.get("partial")) or None,
                "partial_name": _text(raw.get("partial_name")) or None,
                "status": raw.get("status"),
                "order_count": _integer(raw.get("orderCount")),
                "gross_weight": max(0.0, _number(raw.get("gross_weight"))),
                "volumetric_weight": max(0.0, _number(raw.get("v_weight"))),
                "created_at": created_at,
                "raw": raw,
            }
        )

    for search in searches:
        day = _text(search.get("date") or search.get("_id"))
        if day in daily:
            daily[day]["searches"] = _integer(search.get("total"))
            daily[day]["found"] = _integer(search.get("found"))
            daily[day]["not_found"] = _integer(search.get("not_found"))
            daily[day]["errors"] = _integer(search.get("error"))

    normalized_parties: list[dict[str, Any]] = []
    box_totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"orders": 0, "weight": 0.0, "boxes": 0}
    )
    for box in normalized_boxes:
        partial_guid = box["partial_guid"]
        if partial_guid:
            box_totals[partial_guid]["orders"] += box["order_count"]
            box_totals[partial_guid]["weight"] += box["gross_weight"]
            box_totals[partial_guid]["boxes"] += 1

    for raw in parties:
        guid = _text(raw.get("guid"))
        if not guid:
            continue
        totals = box_totals[guid]
        has_loaded_boxes = totals["boxes"] > 0
        normalized_parties.append(
            {
                "guid": guid,
                "name": _text(raw.get("partial_name") or raw.get("partial")),
                "code": _text(raw.get("partial_code")),
                "status": raw.get("status"),
                "box_count": int(totals["boxes"]) if has_loaded_boxes else _integer(raw.get("boxCount")),
                "order_count": int(totals["orders"]),
                "gross_weight": totals["weight"] if has_loaded_boxes else _number(raw.get("gross_weight")),
                "created_at": _text(raw.get("date_created")) or None,
                "raw": raw,
            }
        )

    history = list(daily.values())
    today_row = daily[today.isoformat()]
    summary = {
        "day": today.isoformat(),
        "orders": today_row["orders"],
        "weight": round(today_row["weight"], 2),
        "boxes": today_row["boxes"],
        "searches": today_row["searches"],
        "searches_found": today_row["found"],
        "searches_not_found": today_row["not_found"],
        "search_errors": today_row["errors"],
        "open_parties": sum(1 for party in normalized_parties if party["status"] == 0),
    }
    return {
        "summary": summary,
        "history": history,
        "parties": normalized_parties,
        "boxes": normalized_boxes,
    }
