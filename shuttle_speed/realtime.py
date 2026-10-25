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
from .speed_calc import finite


@dataclass
class RealtimeSpeedSession:
    """一个球馆场地的一次实时测速会话。"""

    venue_id: str
    court_id: str
    fps: float = 60.0
    px_per_meter: Optional[float] = None
    max_speed_kmh: float = 600.0
    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    points: list[dict] = field(default_factory=list)
    speed_history: list[float] = field(default_factory=list)
    last_timestamp: Optional[float] = None
    last_x: Optional[float] = None
    last_y: Optional[float] = None
    current_speed_kmh: Optional[float] = None
    current_speed_px_s: float = 0.0

    def __post_init__(self) -> None:
        self.fps = finite(self.fps, "fps")
        self.px_per_meter = None if self.px_per_meter is None else finite(self.px_per_meter, "px_per_meter")
        self.max_speed_kmh = finite(self.max_speed_kmh, "max_speed_kmh")
        if self.max_speed_kmh <= 0:
            raise ValueError("max_speed_kmh must be positive")
        if self.fps <= 0:
            raise ValueError("fps 必须大于 0")
        if self.px_per_meter is not None and self.px_per_meter <= 0:
            raise ValueError("px_per_meter 必须大于 0")

    def calibrate(self, known_pixels: float, known_meters: float) -> float:
        known_pixels, known_meters = finite(known_pixels,"pixels"), finite(known_meters,"meters")
        if known_pixels <= 0 or known_meters <= 0:
            raise ValueError("已知像素长度和实际长度必须大于 0")
        self.px_per_meter = known_pixels / known_meters
        self.reset()
        return self.px_per_meter

    def add_point(self, x: float, y: float, timestamp: Optional[float] = None, *, source: str = 'unverified') -> dict:
        """添加球的位置并返回最新状态；timestamp 使用秒。"""
        if source not in {'simulated','device','unverified'}:
            raise ValueError('Unsupported point source')
        x, y = finite(x,"x"), finite(y,"y")
        ts = time.monotonic() if timestamp is None else finite(timestamp,"timestamp")
        if ts < 0:raise ValueError("timestamp must be nonnegative")
        speed = None
        quality = "first_point"
        if self.last_timestamp is not None:
            dt = ts - self.last_timestamp
            if dt <= 0:
                raise ValueError("timestamp 必须严格递增")
            distance_px = math.hypot(x - self.last_x, y - self.last_y)
            pixel_speed = distance_px / dt
            speed = pixel_speed / self.px_per_meter * 3.6 if self.px_per_meter is not None else None
            if speed is None:
                quality = "uncalibrated"
            elif speed <= self.max_speed_kmh:
                self.speed_history.append(speed)
                self.speed_history = self.speed_history[-300:]
                quality = "ok"
            else:
                return self.snapshot("outlier")
        self.current_speed_px_s = pixel_speed if self.last_timestamp is not None else 0
        self.current_speed_kmh = speed
        self.last_timestamp, self.last_x, self.last_y = ts, x, y
        self.points.append({"x": x, "y": y, "timestamp": ts, "speed_kmh": speed, "source": source})
        self.points = self.points[-300:]
        return self.snapshot(quality)

    def reset(self) -> dict:
        self.points.clear()
        self.speed_history.clear()
        self.last_timestamp = self.last_x = self.last_y = None
        self.current_speed_kmh = None
        self.current_speed_px_s = 0
        return self.snapshot("reset")

    def snapshot(self, quality: str = "waiting") -> dict:
        sources={point.get('source','unverified') for point in self.points}
        return {
            "session_id": self.session_id, "venue_id": self.venue_id,
            "court_id": self.court_id,
            "status": "tracking" if self.speed_history else "waiting",
            "quality": quality,
            "current_speed_px_s": round(self.current_speed_px_s,1),
            "current_speed_kmh": round(self.current_speed_kmh, 1) if self.current_speed_kmh is not None else None,
            "peak_speed_kmh": round(max(self.speed_history), 1) if self.speed_history else None,
            "average_speed_kmh": round(sum(self.speed_history) / len(self.speed_history), 1) if self.speed_history else None,
            "sample_count": len(self.speed_history), "fps": self.fps,
            "px_per_meter": self.px_per_meter,
            "last_point": self.points[-1] if self.points else None,
            "data_source": next(iter(sources)) if len(sources)==1 else 'mixed' if sources else 'unverified',
        }


class SpeedSessionStore:
    """进程内会话存储，适合演示和单球馆 MVP。"""

    def __init__(self) -> None:
        self.sessions: Dict[str, RealtimeSpeedSession] = {}
        self.touched = {}
        self.max_sessions = 128
        self.ttl = 3600

    def create(self, venue_id: str, court_id: str, fps: float = 60.0,
               px_per_meter: Optional[float] = None) -> RealtimeSpeedSession:
        now = time.monotonic()
        for key in list(self.sessions):
            if now-self.touched.get(key,0)>self.ttl:
                self.sessions.pop(key,None);self.touched.pop(key,None)
        if len(self.sessions)>=self.max_sessions:raise ValueError("session capacity exceeded")
        session = RealtimeSpeedSession(venue_id, court_id, fps, px_per_meter)
        self.sessions[session.session_id] = session
        self.touched[session.session_id] = time.monotonic()
        return session

    def get(self, session_id: str) -> RealtimeSpeedSession:
        try:
            if time.monotonic()-self.touched.get(session_id,0)>self.ttl:
                self.sessions.pop(session_id,None);self.touched.pop(session_id,None)
                raise KeyError(session_id)
            self.touched[session_id] = time.monotonic()
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"找不到测速会话: {session_id}") from exc

    def overview(self, venue_id: str) -> list[dict]:
        return [s.snapshot() for s in self.sessions.values() if s.venue_id == venue_id]
