"""
球速计算模块
功能：根据羽毛球轨迹的帧间位移，计算球速

原理：
  1. TrackNet / YOLO 检测每帧球的位置 (x, y)
  2. 帧间位移 = 相邻帧的像素距离
  3. 像素速度 = 帧间位移 × 帧率
  4. 实际速度 = 像素速度 × 像素到米的换算系数（需标定）

注意：
  本模块只负责速度计算，球检测由 track.py 完成。
  像素到米的换算系数需要通过场地标定获得（在场地已知尺寸上校准）。
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class SpeedReport:
    """球速报告"""
    max_speed_kmh: float              # 最高速度 (km/h)
    avg_speed_kmh: float             # 平均速度 (km/h)
    speed_curve: List[float] = field(default_factory=list)  # 速度曲线
    frame_count: int = 0             # 有效帧数
    fps: int = 30                    # 帧率
    px_per_meter: float = 50.0       # 像素/米 换算系数

    def __str__(self):
        lines = [
            "========== 球速检测报告 ==========",
            f"帧率: {self.fps} fps",
            f"有效帧数: {self.frame_count}",
            f"换算系数: {self.px_per_meter:.1f} px/m",
            f"最高球速: {self.max_speed_kmh:.1f} km/h",
            f"平均球速: {self.avg_speed_kmh:.1f} km/h",
            "===================================",
        ]
        return "\n".join(lines)


class SpeedCalculator:
    """球速计算器"""

    def __init__(self, fps: int = 30, px_per_meter: float = 50.0):
        """
        Args:
            fps: 视频帧率
            px_per_meter: 像素到米的换算系数（需场地标定）
        """
        self.fps = fps
        self.px_per_meter = px_per_meter

    def calculate(self, trajectory: List[Tuple[float, float]]) -> SpeedReport:
        """
        从球的轨迹计算速度

        Args:
            trajectory: 球的像素坐标序列 [(x1,y1), (x2,y2), ...]

        Returns:
            SpeedReport 速度报告
        """
        if len(trajectory) < 2:
            return SpeedReport(max_speed_kmh=0, avg_speed_kmh=0, frame_count=len(trajectory),
                               fps=self.fps, px_per_meter=self.px_per_meter)

        speeds = []
        for i in range(1, len(trajectory)):
            x1, y1 = trajectory[i-1]
            x2, y2 = trajectory[i]
            # 像素位移
            dx = x2 - x1
            dy = y2 - y1
            pixel_dist = np.sqrt(dx**2 + dy**2)

            # 像素速度 → 米/秒 → km/h
            meter_dist = pixel_dist / self.px_per_meter
            time_interval = 1.0 / self.fps
            speed_ms = meter_dist / time_interval
            speed_kmh = speed_ms * 3.6

            # 过滤异常值（球静止或检测噪声）
            if speed_kmh < 300:  # 羽毛球最高记录约 400 km/h
                speeds.append(speed_kmh)

        if not speeds:
            return SpeedReport(max_speed_kmh=0, avg_speed_kmh=0, frame_count=len(trajectory),
                               fps=self.fps, px_per_meter=self.px_per_meter)

        return SpeedReport(
            max_speed_kmh=max(speeds),
            avg_speed_kmh=sum(speeds) / len(speeds),
            speed_curve=speeds,
            frame_count=len(trajectory),
            fps=self.fps,
            px_per_meter=self.px_per_meter,
        )

    def calibrate_px_per_meter(self, known_length_px: float, known_length_m: float) -> float:
        """
        标定像素到米的换算系数

        用法：在视频中找到已知长度的线段（如场地长边 13.4m），
        测量它在图像中的像素长度，输入即可获得换算系数。

        Args:
            known_length_px: 图像中已知线段的像素长度
            known_length_m: 该线段的实际长度（米）

        Returns:
            px_per_meter 像素/米
        """
        self.px_per_meter = known_length_px / known_length_m
        return self.px_per_meter


# 羽毛球球速参考
SPEED_REFERENCE = {
    "初学者杀球": "200-260 km/h",
    "业余高手杀球": "260-350 km/h",
    "职业选手杀球": "350-420 km/h",
    "世界纪录": "421 km/h (傅海峰)",
    "高远球": "100-150 km/h",
    "吊球": "50-80 km/h",
}
