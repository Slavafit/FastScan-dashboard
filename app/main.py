from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .database import DashboardDatabase
from .service import DashboardService
from .state import DashboardState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = Settings.from_env()
database = DashboardDatabase(settings.database_path)
state = DashboardState()
service = DashboardService(settings, database, state)
static_directory = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(service.run(), name="dashboard-refresh")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await service.close()


app = FastAPI(title="FastScan Dashboard", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_directory), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_directory / "index.html")


@app.get("/widget", include_in_schema=False)
async def widget() -> FileResponse:
    return FileResponse(static_directory / "widget.html")


@app.get("/api/dashboard")
async def dashboard() -> dict:
    return await state.snapshot()


@app.get("/api/history")
async def history(days: int = Query(31, ge=1, le=366)) -> list[dict]:
    return database.history(days)


@app.get("/api/parties")
async def parties() -> list[dict]:
    return database.parties()


@app.get("/api/parties/{guid}/boxes")
async def party_boxes(guid: str) -> list[dict]:
    rows = database.boxes_for_party(guid)
    if not rows:
        raise HTTPException(status_code=404, detail="Party boxes were not found")
    return rows


@app.post("/api/refresh")
async def refresh() -> dict[str, bool]:
    await service.refresh()
    return {"ok": True}


@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    queue = state.subscribe()

    async def stream():
        try:
            yield f"data: {json.dumps(await state.snapshot(), ensure_ascii=False, default=str)}\n\n"
            while not await request.is_disconnected():
                try:
                    snapshot = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {json.dumps(snapshot, ensure_ascii=False, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            state.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")
