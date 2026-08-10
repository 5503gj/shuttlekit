"""ShuttleKit 实时球速服务。

启动：python speed_api.py，然后打开 http://127.0.0.1:7862。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shuttle_speed.realtime import SpeedSessionStore
from shuttle_speed.video_speed import VideoSpeedAnalyzer
from equipment_kb.recommender import EquipmentRecommender, UserProfile


class SessionCreate(BaseModel):
    venue_id: str = Field(min_length=1, max_length=80)
    court_id: str = Field(min_length=1, max_length=80)
    fps: float = Field(default=60.0, gt=0, le=240)
    px_per_meter: float = Field(default=50.0, gt=0)


class PointPayload(BaseModel):
    x: float
    y: float
    timestamp: Optional[float] = None


class EquipmentRecommendPayload(BaseModel):
    category: str = Field(default="racket", pattern="^(racket|shoe|shuttlecock)$")
    level: str = Field(default="中级", min_length=1, max_length=30)
    budget: float = Field(default=800.0, ge=0, le=100000)
    play_style: str = Field(default="全面", min_length=1, max_length=30)
    gender: str = Field(default="不限", min_length=1, max_length=10)
    top_k: int = Field(default=5, ge=1, le=10)


app = FastAPI(title="ShuttleKit Speed API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
store = SpeedSessionStore()
video_analyzer = VideoSpeedAnalyzer()
equipment_recommender = EquipmentRecommender()


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


def _equipment_item_view(item: dict) -> dict:
    """只返回前端需要的字段，同时保留来源，避免无来源推荐。"""
    return {
        "id": item.get("id"), "category": item.get("category"),
        "brand": item.get("brand"), "model": item.get("model"),
        "price_min": item.get("price_min"), "price_max": item.get("price_max"),
        "specs": item.get("specs") or {}, "play_styles": item.get("play_styles") or [],
        "levels": item.get("levels") or [], "rating": item.get("rating"),
        "review_summary": item.get("review_summary", ""),
        "source": item.get("source", "未标注来源"),
        "source_url": item.get("source_url", ""),
    }


@app.get("/api/equipment/stats")
def equipment_stats() -> dict:
    stats = equipment_recommender.get_stats()
    return {"stats": stats, "total": len(equipment_recommender.equipment),
            "data_policy": "品牌规格 + 公开评测人工整理；非实时爬取"}


@app.get("/api/equipment/catalog")
def equipment_catalog(category: Optional[str] = None) -> dict:
    allowed = {"racket", "shoe", "shuttlecock"}
    if category and category not in allowed:
        raise HTTPException(status_code=422, detail="category 必须是 racket、shoe 或 shuttlecock")
    items = equipment_recommender.equipment if not category else equipment_recommender.get_by_category(category)
    return {"category": category, "count": len(items), "items": [_equipment_item_view(item) for item in items]}


@app.post("/api/equipment/recommend")
def equipment_recommend(payload: EquipmentRecommendPayload) -> dict:
    profile = UserProfile(payload.category, payload.level, payload.budget,
                          payload.play_style, payload.gender)
    matches = equipment_recommender.recommend(profile, top_k=payload.top_k)
    profile_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return {
        "profile": profile_data,
        "count": len(matches),
        "results": [{"score": round(match.score, 1), "reasons": match.reasons,
                      "item": _equipment_item_view(match.item)} for match in matches],
    }


@app.post("/api/video/analyze")
async def analyze_video(file: UploadFile = File(...)) -> dict:
    """上传短视频并返回场地尺寸、球速和击球类型判断。"""
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        raise HTTPException(status_code=415, detail="仅支持 MP4、MOV、AVI、MKV、WEBM 视频")
    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="视频不能超过 200MB")
    temp_path = None
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(content)
            temp_path = temp.name
        return video_analyzer.analyze(temp_path, video_name=file.filename).to_dict()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


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
