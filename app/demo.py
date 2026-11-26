from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def demo_sources(timezone_name: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    now = datetime.now(ZoneInfo(timezone_name))
    shipment_daily: list[dict] = []
    boxes: list[dict] = []
    searches: list[dict] = []
    for offset in range(31):
        current = now - timedelta(days=offset)
        count = 82 + ((offset * 17) % 64)
        shipment_daily.append(
            {
                "date": current.date().isoformat(),
                "count": count,
                "total_weight": round(
                    sum(1.4 + ((index * 7) % 39) / 10 for index in range(count)), 2
                ),
            }
        )
        for index in range(5 + offset % 7):
            boxes.append(
                {
                    "guid": f"box-{offset}-{index}",
                    "tracking_code": f"NBX{offset:02d}{index:03d}",
                    "partial": f"party-{offset // 5}",
                    "partial_name": f"KG{160 + offset // 5}",
                    "status": 16,
                    "orderCount": 10 + index,
                    "gross_weight": 20 + index * 1.7,
                    "v_weight": 18 + index,
                    "date_created": current.isoformat(),
                }
            )
        searches.append(
            {
                "date": current.date().isoformat(),
                "total": 12 + offset % 9,
                "found": 10 + offset % 7,
                "not_found": 2,
                "error": 0,
            }
        )
    parties = [
        {
            "guid": f"party-{index}",
            "partial_name": f"KG{160 + index}",
            "partial_code": f"NPX-DEMO-{index}",
            "status": 0 if index == 0 else 16,
            "boxCount": 6 + index,
            "gross_weight": 140 + index * 18,
            "date_created": (now - timedelta(days=index * 5)).isoformat(),
        }
        for index in range(7)
    ]
    return shipment_daily, searches, boxes, parties
