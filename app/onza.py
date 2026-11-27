from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class OnzaClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token: str | None = None
        self._client = httpx.AsyncClient(base_url=settings.onza_base_url, timeout=30)

    async def close(self) -> None:
        await self._client.aclose()

    async def _login(self) -> None:
        if not self._settings.onza_configured:
            raise RuntimeError("ONZA_LOGIN and ONZA_PASSWORD are not configured")
        response = await self._client.post(
            "/api/admin/auth/login",
            json={"login": self._settings.onza_login, "password": self._settings.onza_password},
        )
        response.raise_for_status()
        token = response.json().get("accessToken")
        if not token:
            raise RuntimeError("Onza login response does not contain accessToken")
        self._token = token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self._token:
            await self._login()
        response = await self._client.get(
            path,
            params=params,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if response.status_code == 401:
            self._token = None
            await self._login()
            response = await self._client.get(
                path,
                params=params,
                headers={"Authorization": f"Bearer {self._token}"},
            )
        response.raise_for_status()
        return response.json()

    async def fetch(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        boxes = await self._get("/api/order/box")
        parties = await self._get("/api/order/partial")
        return list(boxes or []), list(parties or [])

    async def fetch_boxes(self) -> list[dict[str, Any]]:
        boxes = await self._get("/api/order/box")
        return list(boxes or [])

    async def fetch_box_orders(self, box_tracking_code: str) -> list[dict[str, Any]]:
        orders = await self._get(
            "/api/order/order-tracking-code", params={"boxId": box_tracking_code}
        )
        if not isinstance(orders, list):
            raise RuntimeError(
                f"Unexpected Onza response for box {box_tracking_code}: expected a list"
            )
        return orders
