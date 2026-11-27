from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class DashboardDatabase:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    day TEXT PRIMARY KEY,
                    orders_count INTEGER NOT NULL DEFAULT 0,
                    total_weight REAL NOT NULL DEFAULT 0,
                    boxes_count INTEGER NOT NULL DEFAULT 0,
                    client_searches INTEGER NOT NULL DEFAULT 0,
                    searches_found INTEGER NOT NULL DEFAULT 0,
                    searches_not_found INTEGER NOT NULL DEFAULT 0,
                    search_errors INTEGER NOT NULL DEFAULT 0,
                    history_source TEXT NOT NULL DEFAULT 'live',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS parties (
                    guid TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    status INTEGER,
                    box_count INTEGER NOT NULL DEFAULT 0,
                    gross_weight REAL NOT NULL DEFAULT 0,
                    created_at TEXT,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS boxes (
                    guid TEXT PRIMARY KEY,
                    tracking_code TEXT NOT NULL,
                    partial_guid TEXT,
                    partial_name TEXT,
                    status INTEGER,
                    order_count INTEGER NOT NULL DEFAULT 0,
                    gross_weight REAL NOT NULL DEFAULT 0,
                    volumetric_weight REAL NOT NULL DEFAULT 0,
                    created_at TEXT,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"] for row in self._connection.execute("PRAGMA table_info(daily_metrics)")
            }
            if "history_source" not in columns:
                self._connection.execute(
                    "ALTER TABLE daily_metrics ADD COLUMN history_source TEXT NOT NULL DEFAULT 'live'"
                )

    def replace_daily(self, rows: list[dict[str, Any]], updated_at: str) -> None:
        with self._lock, self._connection:
            self._connection.executemany(
                """
                INSERT INTO daily_metrics (
                    day, orders_count, total_weight, boxes_count, client_searches,
                    searches_found, searches_not_found, search_errors, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    orders_count=excluded.orders_count,
                    total_weight=excluded.total_weight,
                    boxes_count=excluded.boxes_count,
                    client_searches=excluded.client_searches,
                    searches_found=excluded.searches_found,
                    searches_not_found=excluded.searches_not_found,
                    search_errors=excluded.search_errors,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["day"], row["orders"], row["weight"], row["boxes"],
                        row["searches"], row["found"], row["not_found"],
                        row["errors"], updated_at,
                    )
                    for row in rows
                ],
            )

    def import_onza_history(self, rows: list[dict[str, Any]], updated_at: str) -> None:
        """Replace historical order/weight totals while preserving other metrics."""
        with self._lock, self._connection:
            self._connection.executemany(
                """
                INSERT INTO daily_metrics (
                    day, orders_count, total_weight, history_source, updated_at
                ) VALUES (?, ?, ?, 'onza_import', ?)
                ON CONFLICT(day) DO UPDATE SET
                    orders_count=excluded.orders_count,
                    total_weight=excluded.total_weight,
                    history_source='onza_import',
                    updated_at=excluded.updated_at
                """,
                [
                    (row["day"], row["orders"], row["weight"], updated_at)
                    for row in rows
                ],
            )

    def replace_parties(self, parties: list[dict[str, Any]], updated_at: str) -> None:
        with self._lock, self._connection:
            self._connection.executemany(
                """
                INSERT INTO parties (
                    guid, name, code, status, box_count, gross_weight,
                    created_at, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    name=excluded.name, code=excluded.code, status=excluded.status,
                    box_count=excluded.box_count, gross_weight=excluded.gross_weight,
                    created_at=excluded.created_at, raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        party["guid"], party["name"], party["code"], party["status"],
                        party["box_count"], party["gross_weight"], party["created_at"],
                        json.dumps(party["raw"], ensure_ascii=False), updated_at,
                    )
                    for party in parties
                ],
            )

    def replace_boxes(self, boxes: list[dict[str, Any]], updated_at: str) -> None:
        with self._lock, self._connection:
            self._connection.executemany(
                """
                INSERT INTO boxes (
                    guid, tracking_code, partial_guid, partial_name, status,
                    order_count, gross_weight, volumetric_weight, created_at,
                    raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    tracking_code=excluded.tracking_code,
                    partial_guid=excluded.partial_guid,
                    partial_name=excluded.partial_name,
                    status=excluded.status,
                    order_count=excluded.order_count,
                    gross_weight=excluded.gross_weight,
                    volumetric_weight=excluded.volumetric_weight,
                    created_at=excluded.created_at,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        box["guid"], box["tracking_code"], box["partial_guid"],
                        box["partial_name"], box["status"], box["order_count"],
                        box["gross_weight"], box["volumetric_weight"],
                        box["created_at"], json.dumps(box["raw"], ensure_ascii=False),
                        updated_at,
                    )
                    for box in boxes
                ],
            )

    def history(self, days: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM daily_metrics ORDER BY day DESC LIMIT ?", (days,)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def parties(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM parties ORDER BY created_at DESC, name DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def boxes_for_party(self, guid: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM boxes WHERE partial_guid = ? ORDER BY tracking_code", (guid,)
            ).fetchall()
        return [dict(row) for row in rows]
