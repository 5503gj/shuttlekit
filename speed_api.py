"""ShuttleKit 实时球速服务。

启动：python speed_api.py，然后打开 http://127.0.0.1:7862。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shuttle_speed.realtime import SpeedSessionStore


class SessionCreate(BaseModel):
    venue_id: str = Field(min_length=1, max_length=80)
    court_id: str = Field(min_length=1, max_length=80)
    fps: float = Field(default=60.0, gt=0, le=240)
    px_per_meter: float = Field(default=50.0, gt=0)


class PointPayload(BaseModel):
    x: float
    y: float
    timestamp: Optional[float] = None


app = FastAPI(title="ShuttleKit Speed API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
store = SpeedSessionStore()


def _session_or_404(session_id: str):
    try:
        return store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "shuttlekit-speed", "sessions": len(store.sessions)}


@app.post("/api/sessions")
def create_session(payload: SessionCreate) -> dict:
    return store.create(payload.venue_id, payload.court_id, payload.fps,
                        payload.px_per_meter).snapshot()


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    return _session_or_404(session_id).snapshot()


@app.get("/api/venues/{venue_id}/overview")
def venue_overview(venue_id: str) -> dict:
    return {"venue_id": venue_id, "courts": store.overview(venue_id)}


@app.post("/api/sessions/{session_id}/points")
def add_point(session_id: str, payload: PointPayload) -> dict:
    session = _session_or_404(session_id)
    try:
        return session.add_point(payload.x, payload.y, payload.timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/reset")
def reset_session(session_id: str) -> dict:
    return _session_or_404(session_id).reset()


@app.websocket("/ws/sessions/{session_id}")
async def speed_socket(websocket: WebSocket, session_id: str):
    try:
        session = store.get(session_id)
    except KeyError:
        await websocket.close(code=1008, reason="session not found")
        return
    await websocket.accept()
    await websocket.send_json(session.snapshot())
    try:
        while True:
            payload = await websocket.receive_json()
            event_type = payload.get("type", "point")
            if event_type == "reset":
                state = session.reset()
            elif event_type == "point":
                try:
                    state = session.add_point(payload["x"], payload["y"], payload.get("timestamp"))
                except (KeyError, TypeError, ValueError) as exc:
                    await websocket.send_json({"error": str(exc)})
                    continue
            else:
                await websocket.send_json({"error": f"unknown event: {event_type}"})
                continue
            await websocket.send_json(state)
    except WebSocketDisconnect:
        return


WEB_DIR = Path(__file__).parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("speed_api:app", host=os.getenv("HOST", "127.0.0.1"),
                port=int(os.getenv("PORT", "7862")), reload=False)
