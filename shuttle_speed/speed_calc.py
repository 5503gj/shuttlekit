"""Explicit calibration and shared frame/time-aware speed calculations."""
import math
from dataclasses import dataclass, field
from typing import Optional


def finite(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be finite") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass
class SpeedReport:
    max_speed_kmh: Optional[float]
    avg_speed_kmh: Optional[float]
    speed_curve: list = field(default_factory=list)
    frame_count: int = 0
    fps: float = 30
    px_per_meter: Optional[float] = None
    pixel_speed_curve: list = field(default_factory=list)
    rejected_samples: int = 0
    status: str = "insufficient_data"

    def __str__(self):
        return f"球速检测报告 | {self.status} | {self.max_speed_kmh} km/h | calibration={self.px_per_meter} px/m"


class SpeedCalculator:
    def __init__(self, fps=30, px_per_meter=None, max_speed_kmh=600):
        self.fps = finite(fps, "fps")
        if not 0 < self.fps <= 1000:
            raise ValueError("fps must be positive and <=1000")
        self.px_per_meter = None if px_per_meter is None else finite(px_per_meter, "px_per_meter")
        if self.px_per_meter is not None and self.px_per_meter <= 0:
            raise ValueError("px_per_meter must be positive")
        self.max_speed_kmh = finite(max_speed_kmh, "max_speed_kmh")
        if self.max_speed_kmh <= 0:
            raise ValueError("max_speed_kmh must be positive")

    def calculate(self, trajectory, frame_indices=None, timestamps=None):
        count = len(trajectory)
        if frame_indices is not None and timestamps is not None:
            raise ValueError("provide frame_indices or timestamps, not both")
        times = timestamps if timestamps is not None else [(f / self.fps) for f in (frame_indices if frame_indices is not None else range(count))]
        if len(times) != count:
            raise ValueError("timeline length differs from trajectory")
        times = [finite(t, "timestamp") for t in times]
        if any(t < 0 for t in times) or any(b <= a for a,b in zip(times,times[1:])):
            raise ValueError("timestamps must be nonnegative and strictly increasing")
        positions = [(finite(p[0],"x"),finite(p[1],"y")) for p in trajectory]
        pixels, speeds, rejected = [], [], 0
        for i in range(1,count):
            px_s = math.hypot(positions[i][0]-positions[i-1][0],positions[i][1]-positions[i-1][1])/(times[i]-times[i-1])
            pixels.append(px_s)
            if self.px_per_meter is not None:
                kmh = px_s / self.px_per_meter * 3.6
                if kmh <= self.max_speed_kmh:speeds.append(kmh)
                else:rejected += 1
        status = "uncalibrated" if self.px_per_meter is None else "ok" if speeds else "no_valid_samples" if rejected else "insufficient_data"
        return SpeedReport(max(speeds) if speeds else None,sum(speeds)/len(speeds) if speeds else None,
                           speeds,count,self.fps,self.px_per_meter,pixels,rejected,status)

    def calibrate_px_per_meter(self, known_length_px, known_length_m):
        px,m=finite(known_length_px,"known_length_px"),finite(known_length_m,"known_length_m")
        if px<=0 or m<=0:raise ValueError("calibration lengths must be positive")
        self.px_per_meter=px/m
        return self.px_per_meter


SPEED_REFERENCE = {"世界纪录":"历史示例421 km/h，非最新纪录，不作为过滤阈值", "高远球":"需按实际标定场景验证"}
