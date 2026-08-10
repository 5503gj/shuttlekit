"""视频球速 MVP：场地尺寸估计、羽毛球候选点追踪和杀球判断。

默认使用 OpenCV 的轻量级候选点算法，不需要额外模型即可跑通流程；
如果要在复杂背景下提高精度，可把 `_detect_shuttle` 替换为 TrackNet/YOLO。
报告会明确返回检测率、标定来源和告警，避免把低置信度结果当成精密测速。
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

import cv2
import numpy as np


@dataclass
class CourtSizeEstimate:
    court_type: str
    length_m: float
    width_m: float
    px_per_meter: float
    confidence: float
    source: str
    line_count: int = 0
    corners: list[tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VideoSpeedReport:
    video_name: str
    fps: float
    total_frames: int
    duration_s: float
    detected_frames: int
    detection_rate: float
    court: CourtSizeEstimate
    peak_speed_kmh: float
    average_speed_kmh: float
    speed_curve: list[float]
    shot_type: str
    shot_confidence: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["court"] = self.court.to_dict()
        return data


class VideoSpeedAnalyzer:
    """从视频中估计球速；适合固定机位、光线稳定的短视频。"""

    def __init__(self, smash_threshold_kmh: float = 260.0,
                 max_speed_kmh: float = 500.0) -> None:
        self.smash_threshold_kmh = smash_threshold_kmh
        self.max_speed_kmh = max_speed_kmh

    def analyze(self, video_path: str, video_name: Optional[str] = None) -> VideoSpeedReport:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"找不到视频：{video_path}")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("无法打开视频，请上传 MP4、MOV 或 AVI 文件")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_s = total_frames / fps if fps > 0 else 0.0
        ok, first_frame = cap.read()
        if not ok or first_frame is None:
            cap.release()
            raise ValueError("视频没有可读取的画面")

        court = self._estimate_court(first_frame)
        points: list[tuple[int, float, float]] = []
        previous_gray: Optional[np.ndarray] = None
        previous_point: Optional[tuple[float, float]] = None
        frame_index = 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            point = self._detect_shuttle(frame, previous_gray, previous_point)
            if point is not None:
                points.append((frame_index, point[0], point[1]))
                previous_point = point
            previous_gray = gray
            frame_index += 1
        cap.release()

        speeds: list[float] = []
        for previous, current in zip(points, points[1:]):
            frame_gap = current[0] - previous[0]
            if frame_gap <= 0:
                continue
            distance_px = math.hypot(current[1] - previous[1], current[2] - previous[2])
            speed_kmh = distance_px / court.px_per_meter * fps / frame_gap * 3.6
            if 1.0 <= speed_kmh <= self.max_speed_kmh:
                speeds.append(round(speed_kmh, 1))

        detection_rate = len(points) / max(1, total_frames)
        peak = max(speeds, default=0.0)
        average = sum(speeds) / len(speeds) if speeds else 0.0
        shot_type, shot_confidence = self._classify_shot(peak, detection_rate, court.confidence)
        warnings: list[str] = []
        if court.source == "fallback":
            warnings.append("未稳定识别到完整场地线，像素比例使用画面估计；建议手动标定。")
        if detection_rate < 0.25:
            warnings.append("羽毛球有效检测率较低，建议使用 60fps 以上、固定机位和更亮画面。")
        if len(speeds) < 2:
            warnings.append("有效速度样本不足，当前结果只能作为参考。")
        if shot_type == "疑似杀球" and shot_confidence < 0.65:
            warnings.append("速度达到杀球阈值，但置信度不高，请结合原视频复核。")

        return VideoSpeedReport(
            video_name=video_name or os.path.basename(video_path), fps=round(fps, 2),
            total_frames=total_frames, duration_s=round(duration_s, 2),
            detected_frames=len(points), detection_rate=round(detection_rate, 3),
            court=court, peak_speed_kmh=round(peak, 1),
            average_speed_kmh=round(average, 1), speed_curve=speeds[-120:],
            shot_type=shot_type, shot_confidence=round(shot_confidence, 3),
            warnings=warnings,
        )

    def _estimate_court(self, frame: np.ndarray) -> CourtSizeEstimate:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45,
                                 minLineLength=max(35, min(frame.shape[:2]) // 8),
                                 maxLineGap=18)
        horizontal = []
        vertical = []
        lengths = []
        endpoints: list[tuple[int, int]] = []
        if lines is not None:
            for raw in lines[:, 0, :]:
                x1, y1, x2, y2 = map(int, raw)
                dx, dy = abs(x2 - x1), abs(y2 - y1)
                length = math.hypot(dx, dy)
                lengths.append(length)
                endpoints.extend([(x1, y1), (x2, y2)])
                if dy <= max(8, dx * 0.08):
                    horizontal.append(raw)
                elif dx <= max(8, dy * 0.08):
                    vertical.append(raw)

        if len(horizontal) >= 6 and len(vertical) >= 4:
            court_type, width_m = "双打场地", 6.10
        elif len(horizontal) >= 3 and len(vertical) >= 2:
            court_type, width_m = "单打场地", 5.18
        else:
            court_type, width_m = "无法确定", 6.10

        if lengths:
            longest_px = max(lengths)
            px_per_meter = max(5.0, longest_px / 13.4)
            confidence = min(0.92, 0.35 + 0.05 * min(len(horizontal), 6) + 0.05 * min(len(vertical), 4))
            source = "court-lines"
        else:
            longest_px = float(frame.shape[1])
            px_per_meter = max(5.0, longest_px / 13.4)
            confidence, source = 0.2, "fallback"

        corners: list[tuple[int, int]] = []
        if endpoints:
            hull = cv2.convexHull(np.array(endpoints, dtype=np.int32).reshape(-1, 1, 2))
            corners = [tuple(map(int, point[0])) for point in hull[:8]]
        return CourtSizeEstimate(court_type, 13.40, width_m, round(px_per_meter, 3),
                                 round(confidence, 3), source, len(horizontal) + len(vertical), corners)

    def _detect_shuttle(self, frame: np.ndarray, previous_gray: Optional[np.ndarray],
                        previous_point: Optional[tuple[float, float]]) -> Optional[tuple[float, float]]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white = cv2.inRange(hsv, np.array([0, 0, 155]), np.array([180, 145, 255]))
        if previous_gray is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            motion = cv2.threshold(cv2.absdiff(gray, previous_gray), 12, 255, cv2.THRESH_BINARY)[1]
            mask = cv2.bitwise_and(white, motion)
        else:
            mask = white
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        height, width = frame.shape[:2]
        min_area, max_area = max(3.0, width * height * 0.000005), width * height * 0.0012
        candidates: list[tuple[float, float, float]] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            if not min_area <= area <= max_area or w <= 0 or h <= 0:
                continue
            ratio = max(w / h, h / w)
            if ratio > 7.0:
                continue
            cx, cy = x + w / 2, y + h / 2
            distance = math.hypot(cx - previous_point[0], cy - previous_point[1]) if previous_point else 0.0
            if previous_point and distance > max(width, height) * 0.45:
                continue
            score = area + (max(width, height) * 0.08 - distance if previous_point else 0)
            candidates.append((score, cx, cy))
        if not candidates:
            return None
        _, cx, cy = max(candidates)
        return round(cx, 2), round(cy, 2)

    def _classify_shot(self, peak: float, detection_rate: float,
                       court_confidence: float) -> tuple[str, float]:
        if peak <= 0:
            return "数据不足", 0.15
        if peak >= self.smash_threshold_kmh:
            shot = "疑似杀球"
        elif peak >= 180:
            shot = "快速平抽"
        elif peak >= 100:
            shot = "高远球/快球"
        else:
            shot = "慢速击球"
        confidence = min(0.98, 0.25 + detection_rate * 0.55 + court_confidence * 0.2)
        return shot, confidence
