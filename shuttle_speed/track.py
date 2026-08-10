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
from .speed_calc import SpeedCalculator, SpeedReport


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

    def __init__(self, fps: int = 30, method: str = "yolo"):
        """
        Args:
            fps: 视频帧率
            method: 追踪方法 "yolo" | "manual" | "tracknet"
        """
        self.fps = fps
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
        import cv2

        if self.method == "yolo" and self._load_yolo_model():
            return self._track_with_yolo(video_path, output_path)
        else:
            print("回退到手动标注模式，请使用 track_from_csv")
            return TrackResult(trajectory=[], total_frames=0, detected_frames=0,
                             detection_rate=0.0)

    def _track_with_yolo(self, video_path: str, output_path: Optional[str]) -> TrackResult:
        """使用 YOLO 追踪"""
        import cv2

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        trajectory = []
        detected = 0
        out = None

        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            video_fps = cap.get(cv2.CAP_PROP_FPS) or self.fps
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(output_path, fourcc, video_fps,
                                  (frame_width, frame_height))

        # YOLO 的 "sports ball" 类 (class 32) 可用于近似检测球
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = self._model(frame, verbose=False)
            # 找最小的检测框（羽毛球在画面中通常最小）
            best_box = None
            min_area = float('inf')

            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = (x2 - x1) * (y2 - y1)
                if area < min_area:
                    min_area = area
                    best_box = (x1, y1, x2, y2)

            if best_box:
                cx = (best_box[0] + best_box[2]) / 2
                cy = (best_box[1] + best_box[3]) / 2
                trajectory.append((cx, cy))
                detected += 1

            if output_path:
                # 绘制轨迹
                for i in range(1, len(trajectory)):
                    cv2.line(frame,
                            (int(trajectory[i-1][0]), int(trajectory[i-1][1])),
                            (int(trajectory[i][0]), int(trajectory[i][1])),
                            (0, 255, 0), 2)
                out.write(frame)

        cap.release()
        if out is not None:
            out.release()

        detection_rate = detected / total_frames if total_frames > 0 else 0

        # 计算速度
        calc = SpeedCalculator(fps=self.fps)
        speed_report = calc.calculate(trajectory) if trajectory else None

        return TrackResult(
            trajectory=trajectory,
            total_frames=total_frames,
            detected_frames=detected,
            detection_rate=detection_rate,
            speed_report=speed_report,
        )

    def track_from_csv(self, csv_path: str) -> TrackResult:
        """
        从 CSV 文件读取轨迹数据（手动标注或其他工具导出）

        CSV 格式: frame, x, y
        """
        trajectory = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                x = float(row['x'])
                y = float(row['y'])
                trajectory.append((x, y))

        calc = SpeedCalculator(fps=self.fps)
        speed_report = calc.calculate(trajectory) if trajectory else None

        return TrackResult(
            trajectory=trajectory,
            total_frames=len(trajectory),
            detected_frames=len(trajectory),
            detection_rate=1.0,
            speed_report=speed_report,
        )
