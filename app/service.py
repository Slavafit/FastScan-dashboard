from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .aggregates import build_dashboard_data, merge_daily_history
from .config import Settings
from .database import DashboardDatabase
from .demo import demo_sources
from .firestore_source import FirestoreSource
from .onza import OnzaClient
from .state import DashboardState

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(
        self,
        settings: Settings,
        database: DashboardDatabase,
        state: DashboardState,
    ) -> None:
        self.settings = settings
        self.database = database
        self.state = state
        self.onza = OnzaClient(settings)
        self.firestore = FirestoreSource(settings)
        self._shipment_daily: list[dict[str, Any]] = []
        self._searches: list[dict[str, Any]] = []
        self._boxes: list[dict[str, Any]] = []
        self._parties: list[dict[str, Any]] = []
        self._onza_status = "waiting"
        self._firebase_status = "waiting"
        self._last_success: str | None = None
        self._refresh_lock = asyncio.Lock()
        self._last_onza_fetch = 0.0
        self._onza_refresh_seconds = 300
        self._last_firebase_fetch = 0.0
        self._firebase_refresh_seconds = 300

    async def close(self) -> None:
        await self.onza.close()

    async def run(self) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def refresh(self) -> None:
        async with self._refresh_lock:
            await self._refresh_unlocked()

    async def _refresh_unlocked(self) -> None:
        now = datetime.now(ZoneInfo(self.settings.warehouse_timezone))
        attempt = now.isoformat()
        messages: list[str] = []

        if self.settings.demo_mode:
            self._shipment_daily, self._searches, self._boxes, self._parties = demo_sources(
                self.settings.warehouse_timezone
            )
            self._onza_status = "demo"
            self._firebase_status = "demo"
        else:
            if time.monotonic() - self._last_onza_fetch >= self._onza_refresh_seconds:
                try:
                    self._boxes, self._parties = await self.onza.fetch()
                    self._onza_status = "online"
                    self._last_onza_fetch = time.monotonic()
                except Exception as error:  # noqa: BLE001 - source health is reported to the UI
                    self._onza_status = "error"
                    messages.append(f"Onza: {error}")
                    logger.warning("Onza refresh failed", exc_info=error)

            if time.monotonic() - self._last_firebase_fetch >= self._firebase_refresh_seconds:
                try:
                    self._shipment_daily, self._searches = await asyncio.to_thread(self.firestore.fetch)
                    self._firebase_status = "online"
                    self._last_firebase_fetch = time.monotonic()
                except Exception as error:  # noqa: BLE001
                    self._firebase_status = "error"
                    messages.append(f"Firebase: {error}")
                    logger.warning("Firebase refresh failed", exc_info=error)

        dashboard = build_dashboard_data(
            self._shipment_daily,
            self._searches,
            self._boxes,
            self._parties,
            self.settings.warehouse_timezone,
        )
        if not self.settings.demo_mode:
            # Firestore now returns only today's two aggregate documents. Keep
            # older points from SQLite so the limited live fetch cannot replace
            # prior days with the zero-filled placeholders from aggregation.
            current_day = dashboard["summary"]["day"]
            dashboard["history"] = merge_daily_history(
                dashboard["history"], self.database.history(366), current_day
            )
        if self._onza_status in {"online", "demo"} or self._firebase_status in {"online", "demo"}:
            self._last_success = attempt

        dashboard["health"] = {
            "onza": self._onza_status,
            "firebase": self._firebase_status,
            "last_success": self._last_success,
            "last_attempt": attempt,
            "message": " · ".join(messages) if messages else "All data sources are available",
            "source_refresh_seconds": 300,
        }
        self.database.replace_daily(dashboard["history"], attempt)
        self.database.replace_parties(dashboard["parties"], attempt)
        self.database.replace_boxes(dashboard["boxes"], attempt)
        await self.state.update(dashboard)
