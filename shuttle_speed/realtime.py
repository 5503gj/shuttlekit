"""实时球速会话与球馆场地状态。

接收已经检测到的球的位置，负责实时换算球速、统计峰值和平均值。
摄像头识别可以由 TrackNet、YOLO 或其他检测器提供，和速度计算解耦。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from uuid import uuid4


@dataclass
class RealtimeSpeedSession:
    """一个球馆场地的一次实时测速会话。"""

    venue_id: str
    court_id: str
    fps: float = 60.0
    px_per_meter: float = 50.0
    max_speed_kmh: float = 600.0
    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    points: list[dict] = field(default_factory=list)
    speed_history: list[float] = field(default_factory=list)
    last_timestamp: Optional[float] = None
    last_x: Optional[float] = None
    last_y: Optional[float] = None
    current_speed_kmh: float = 0.0

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError("fps 必须大于 0")
        if self.px_per_meter <= 0:
            raise ValueError("px_per_meter 必须大于 0")

    def calibrate(self, known_pixels: float, known_meters: float) -> float:
        if known_pixels <= 0 or known_meters <= 0:
            raise ValueError("已知像素长度和实际长度必须大于 0")
        self.px_per_meter = known_pixels / known_meters
        return self.px_per_meter

    def add_point(self, x: float, y: float, timestamp: Optional[float] = None) -> dict:
        """添加球的位置并返回最新状态；timestamp 使用秒。"""
        x, y = float(x), float(y)
        ts = time.time() if timestamp is None else float(timestamp)
        speed = 0.0
        quality = "first_point"
        if self.last_timestamp is not None:
            dt = ts - self.last_timestamp
            if dt <= 0:
                raise ValueError("timestamp 必须严格递增")
            distance_px = math.hypot(x - self.last_x, y - self.last_y)
            speed = distance_px / self.px_per_meter / dt * 3.6
            if speed <= self.max_speed_kmh:
                self.speed_history.append(speed)
                quality = "ok"
            else:
                quality = "outlier"
        self.current_speed_kmh = speed
        self.last_timestamp, self.last_x, self.last_y = ts, x, y
        self.points.append({"x": x, "y": y, "timestamp": ts, "speed_kmh": speed})
        self.points = self.points[-300:]
        return self.snapshot(quality)

    def reset(self) -> dict:
        self.points.clear()
        self.speed_history.clear()
        self.last_timestamp = self.last_x = self.last_y = None
        self.current_speed_kmh = 0.0
        return self.snapshot("reset")

    def snapshot(self, quality: str = "waiting") -> dict:
        return {
            "session_id": self.session_id, "venue_id": self.venue_id,
            "court_id": self.court_id,
            "status": "tracking" if self.speed_history else "waiting",
            "quality": quality,
            "current_speed_kmh": round(self.current_speed_kmh, 1),
            "peak_speed_kmh": round(max(self.speed_history, default=0.0), 1),
            "average_speed_kmh": round(sum(self.speed_history) / len(self.speed_history), 1) if self.speed_history else 0.0,
            "sample_count": len(self.speed_history), "fps": self.fps,
            "px_per_meter": round(self.px_per_meter, 3),
            "last_point": self.points[-1] if self.points else None,
        }


class SpeedSessionStore:
    """进程内会话存储，适合演示和单球馆 MVP。"""

    def __init__(self) -> None:
        self.sessions: Dict[str, RealtimeSpeedSession] = {}

    def create(self, venue_id: str, court_id: str, fps: float = 60.0,
               px_per_meter: float = 50.0) -> RealtimeSpeedSession:
        session = RealtimeSpeedSession(venue_id, court_id, fps, px_per_meter)
        self.sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> RealtimeSpeedSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"找不到测速会话: {session_id}") from exc

    def overview(self, venue_id: str) -> list[dict]:
        return [s.snapshot() for s in self.sessions.values() if s.venue_id == venue_id]
