from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .aggregates import _day
from .config import Settings
from .database import DashboardDatabase
from .onza import OnzaClient


def _weight(order: dict[str, Any]) -> float:
    try:
        value = float(order.get("gross_weight") or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, value)


async def backfill(year: int | None = None) -> None:
    settings = Settings.from_env()
    if not settings.onza_configured:
        raise RuntimeError("Set ONZA_LOGIN and ONZA_PASSWORD in .env first")

    timezone = ZoneInfo(settings.warehouse_timezone)
    today = datetime.now(timezone).date()
    if year is not None:
        if not 1 <= year <= 9998 or year > today.year:
            raise ValueError(f"Invalid or future year: {year}")
        first_day = date(year, 1, 1)
        end_day = min(date(year + 1, 1, 1), today)
    else:
        first_day = today - timedelta(days=61)
        end_day = today
    database = DashboardDatabase(settings.database_path)
    onza = OnzaClient(settings)
    try:
        boxes = await onza.fetch_boxes()
        targets: list[tuple[str, str]] = []
        seen: set[str] = set()
        for box in boxes:
            tracking = str(box.get("tracking_code") or "").strip()
            created = _day(box.get("date_created"), timezone)
            if not tracking or not created or not first_day.isoformat() <= created < end_day.isoformat():
                continue
            key = tracking.upper()
            if key in seen:
                continue
            seen.add(key)
            targets.append((tracking, created))

        period_end = end_day - timedelta(days=1)
        period = f"{first_day} through {period_end}" if end_day > first_day else "no completed days yet"
        print(f"Onza boxes to inspect: {len(targets)} ({period})")
        totals: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"orders": 0, "weight": 0.0, "missing_weights": 0}
        )
        for index, (tracking, created) in enumerate(targets, start=1):
            orders = await onza.fetch_box_orders(tracking)
            totals[created]["orders"] += len(orders)
            totals[created]["weight"] += sum(_weight(order) for order in orders)
            totals[created]["missing_weights"] += sum(
                1 for order in orders if order.get("gross_weight") in (None, "")
            )
            if index % 25 == 0 or index == len(targets):
                print(f"Loaded contents for {index}/{len(targets)} boxes")
            # Keep the one-time history import gentle on the Onza API.
            await asyncio.sleep(0.15)

        rows = [
            {"day": day, "orders": int(values["orders"]), "weight": round(float(values["weight"]), 3)}
            for day, values in sorted(totals.items())
        ]
        stamp = datetime.now(timezone).isoformat()
        database.import_onza_history(rows, stamp)
        print(f"Saved {len(rows)} daily totals into {settings.database_path}")
        missing_weights = sum(int(values["missing_weights"]) for values in totals.values())
        if missing_weights:
            print(f"Note: {missing_weights} orders had no gross_weight; those orders count as 0 kg.")
        print("Today's metrics were left unchanged; box counts and search counters were preserved.")
    finally:
        await onza.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical order counts and weights from Onza")
    parser.add_argument(
        "--year",
        type=int,
        help="Import a calendar year through yesterday (for example: --year 2026)",
    )
    args = parser.parse_args()
    asyncio.run(backfill(year=args.year))


if __name__ == "__main__":
    main()
