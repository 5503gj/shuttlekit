"""Bounded 2D trajectory analysis; physical speed requires explicit measured scale."""
from dataclasses import asdict,dataclass,field
import math
import os
import time
from typing import Optional
import cv2
import numpy as np
from .speed_calc import SpeedCalculator, finite

@dataclass
class CourtSizeEstimate:
    court_type:str="未标定"
    length_m:Optional[float]=None
    width_m:Optional[float]=None
    px_per_meter:Optional[float]=None
    confidence:Optional[float]=None
    source:str="unavailable"
    line_count:int=0
    corners:list=field(default_factory=list)
    def to_dict(self):return asdict(self)

@dataclass
class VideoSpeedReport:
    video_name:str
    fps:float
    total_frames:int
    duration_s:float
    detected_frames:int
    detection_rate:float
    court:CourtSizeEstimate
    peak_speed_kmh:Optional[float]
    average_speed_kmh:Optional[float]
    smash_angle_deg:Optional[float]
    speed_curve:list
    shot_type:str
    shot_confidence:Optional[float]
    warnings:list=field(default_factory=list)
    peak_speed_px_s:Optional[float]=None
    trajectory_angle_deg:Optional[float]=None
    speed_basis:str="uncalibrated"
    def to_dict(self):return asdict(self)

class VideoSpeedAnalyzer:
    def __init__(self,smash_threshold_kmh=260,max_speed_kmh=600):
        self.smash_threshold_kmh=smash_threshold_kmh;self.max_speed_kmh=max_speed_kmh
    def _estimate_court(self,frame):
        # No dimensions or scale can be inferred from an arbitrary Hough line.
        return CourtSizeEstimate()
    def analyze(self,video_path,video_name=None,px_per_meter=None):
        if not os.path.isfile(video_path):raise FileNotFoundError("视频不存在")
        cap=cv2.VideoCapture(video_path)
        points,times=[],[]
        try:
            if not cap.isOpened():raise ValueError("无法打开视频")
            fps=finite(cap.get(cv2.CAP_PROP_FPS),"fps")
            calc=SpeedCalculator(fps,px_per_meter,self.max_speed_kmh)
            declared=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if declared>3600 or declared/fps>60:raise ValueError("视频最多60秒/3600帧")
            if cap.get(cv2.CAP_PROP_FRAME_WIDTH)*cap.get(cv2.CAP_PROP_FRAME_HEIGHT)>1920*1080:raise ValueError("视频最多1920×1080像素")
            previous_gray=previous_point=None;frame_index=0;start=time.monotonic()
            while True:
                ok,frame=cap.read()
                if not ok:break
                if frame_index>=3600 or frame_index/fps>60 or time.monotonic()-start>15:raise ValueError("视频超过处理时间/帧数限制")
                if frame.shape[0]*frame.shape[1]>1920*1080:raise ValueError("视频分辨率超限")
                gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                point=self._detect_shuttle(frame,previous_gray,previous_point)
                if point is not None:
                    timestamp=float(cap.get(cv2.CAP_PROP_POS_MSEC))/1000
                    if not math.isfinite(timestamp) or timestamp<0 or (times and timestamp<=times[-1]):timestamp=frame_index/fps
                    if times and timestamp<=times[-1]:raise ValueError("视频时间轴无效")
                    points.append(point);times.append(timestamp);previous_point=point
                previous_gray=gray;frame_index+=1
            if not frame_index:raise ValueError("视频没有画面")
        finally:cap.release()
        report=calc.calculate(points,timestamps=times)
        court=CourtSizeEstimate(px_per_meter=px_per_meter,source="manual-scale" if px_per_meter is not None else "unavailable")
        peak=report.max_speed_kmh
        angle=math.degrees(math.atan2(points[-1][1]-points[0][1],points[-1][0]-points[0][0])) if len(points)>1 else None
        shot,_=self._classify_shot(peak,len(points)/frame_index,None)
        warnings=["仅画面2D轨迹估计，不是实际飞行3D速度；不推断物理扣杀俯角或球场尺寸。", "击球标签是未校准的速度阈值参考，不是概率或模型分类结果。"]
        if px_per_meter is None:warnings.append("未提供实际标定；仅输出px/s，km/h为空。")
        if report.rejected_samples:warnings.append(f"{report.rejected_samples}个样本超过配置阈值并被拒绝，未作为零速。")
        return VideoSpeedReport(video_name or os.path.basename(video_path),fps,frame_index,frame_index/fps,len(points),len(points)/frame_index,court,peak,report.avg_speed_kmh,None,report.speed_curve[-120:],shot,None,warnings,max(report.pixel_speed_curve) if report.pixel_speed_curve else None,angle,"2d_projected" if px_per_meter is not None else "uncalibrated")

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


    def _classify_shot(self,peak,detection_rate,court_confidence):
        if peak is None:return "数据不足/未标定",None
        if peak>=self.smash_threshold_kmh:return "阈值参考：疑似杀球",None
        return "阈值参考：其他击球",None
