"""
羽毛球轨迹追踪模块
功能：从视频中检测羽毛球位置，生成轨迹序列

支持两种方式：
  1. TrackNet 方式（推荐，精度高，需 GPU + 模型权重）
  2. YOLO 方式（通用，需安装 ultralytics）
  3. 手动标注方式（无需模型，适合小量分析）

安装进阶依赖：
  pip install ultralytics torch
  模型权重下载见 scripts/setup_models.sh
"""

import csv
import os
from dataclasses import dataclass
from typing import List, Tuple, Optional
from .speed_calc import SpeedCalculator, SpeedReport, finite


@dataclass
class TrackResult:
    """追踪结果"""
    trajectory: List[Tuple[float, float]]   # 球的像素坐标序列
    total_frames: int                       # 总帧数
    detected_frames: int                    # 成功检测帧数
    detection_rate: float                   # 检测率
    speed_report: Optional[SpeedReport] = None


class ShuttleTracker:
    """羽毛球追踪器"""

    def __init__(self, fps: int = 30, method: str = "yolo", px_per_meter=None, model_path=None, class_ids=(32,), confidence=0.5):
        """
        Args:
            fps: 视频帧率
            method: 追踪方法 "yolo" | "manual" | "tracknet"
        """
        self.fps = SpeedCalculator(fps, px_per_meter).fps
        self.px_per_meter = px_per_meter
        self.model_path = model_path
        self.class_ids = set(class_ids)
        self.confidence = finite(confidence, "confidence")
        if not 0<=self.confidence<=1:raise ValueError("invalid confidence")
        self.method = method
        self._model = None

    def _load_yolo_model(self, model_path: str = "yolov8n.pt"):
        """加载 YOLO 模型"""
        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            return True
        except ImportError:
            print("警告: ultralytics 未安装，请运行: pip install ultralytics")
            return False
        except Exception as e:
            print(f"警告: 模型加载失败: {e}")
            return False

    def track_from_video(self, video_path: str, output_path: Optional[str] = None) -> TrackResult:
        """
        从视频自动追踪羽毛球

        Args:
            video_path: 视频路径
            output_path: 输出标注视频路径（可选）

        Returns:
            TrackResult 包含轨迹和速度
        """
        if self.method == "tracknet":
            raise NotImplementedError("TrackNet推理未实现，请使用手动CSV或显式配置YOLO")
        if self.method != "yolo":
            raise ValueError("自动追踪只支持显式配置的YOLO，手动轨迹请使用track_from_csv")
        if not self.model_path or not os.path.isfile(self.model_path):
            raise ValueError("请提供本地已验证YOLO权重；不会自动下载模型")
        if not self._load_yolo_model(self.model_path):
            raise RuntimeError("YOLO未安装或权重加载失败")
        return self._track_with_yolo(video_path, output_path)

    def _track_with_yolo(self, video_path, output_path):
        import cv2
        cap=cv2.VideoCapture(video_path)
        trajectory,frames=[],[]
        try:
            if not cap.isOpened():raise ValueError("无法读取视频")
            fps=finite(cap.get(cv2.CAP_PROP_FPS),"video fps")
            calc=SpeedCalculator(fps,self.px_per_meter)
            index=0
            while True:
                ok,frame=cap.read()
                if not ok:break
                if index>=3600 or max(frame.shape[:2])>1920:raise ValueError("视频超出3600帧/1920像素限制")
                result=self._model(frame,verbose=False)
                candidates=[]
                for box in result[0].boxes:
                    if int(box.cls[0]) not in self.class_ids or float(box.conf[0])<self.confidence:continue
                    x1,y1,x2,y2=box.xyxy[0].tolist()
                    if x2>x1 and y2>y1:candidates.append(((x1+x2)/2,(y1+y2)/2))
                if candidates:
                    previous=trajectory[-1] if trajectory else candidates[0]
                    point=min(candidates,key=lambda p:(p[0]-previous[0])**2+(p[1]-previous[1])**2)
                    trajectory.append(point);frames.append(index)
                index+=1
        finally:cap.release()
        report=calc.calculate(trajectory,frame_indices=frames)
        return TrackResult(trajectory,index,len(trajectory),len(trajectory)/index if index else 0,report)

    def track_from_csv(self,csv_path):
        trajectory,frames=[],[]
        with open(csv_path,encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                frame=finite(row['frame'],"frame")
                if frame<0 or not frame.is_integer():raise ValueError("frame必须为非负整数")
                frames.append(int(frame));trajectory.append((finite(row['x'],"x"),finite(row['y'],"y")))
        report=SpeedCalculator(self.fps,self.px_per_meter).calculate(trajectory,frame_indices=frames)
        total=frames[-1]+1 if frames else 0
        return TrackResult(trajectory,total,len(trajectory),len(trajectory)/total if total else 0,report)
