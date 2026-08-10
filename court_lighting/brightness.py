"""
场馆灯光评估 - 核心模块
功能：分析场馆照片的亮度、均匀度、眩光，判断是否达到 BWF 标准

BWF 照度参考标准：
  - 国际比赛: 500 lux 以上
  - 一般比赛: 300-500 lux
  - 训练/休闲: 200-300 lux
  - 亮度不均匀度应 < 0.6（均匀度 > 0.4）
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LightingReport:
    """灯光评估报告"""
    mean_brightness: float          # 平均亮度 0-255
    brightness_pct: float          # 亮度百分比
    uniformity: float               # 均匀度 0-1
    has_glare: bool                 # 是否检测到眩光
    glare_regions: int             # 眩光区域数
    brightness_dist: str           # 亮度分布描述
    conclusion: str                # 评估结论
    suggestions: list              = field(default_factory=list)  # 改进建议

    def __str__(self):
        lines = [
            "========== 场馆灯光评估报告 ==========",
            f"平均亮度: {self.mean_brightness:.1f} / 255 ({self.brightness_pct:.1f}%)",
            f"亮度均匀度: {self.uniformity:.2f} ({'良好' if self.uniformity > 0.5 else '较差'})",
            f"眩光区域: 检测到 {self.glare_regions} 处{'高光区' if self.has_glare else '无明显眩光'}",
            f"亮度分布: {self.brightness_dist}",
            f"评估结论: {self.conclusion}",
        ]
        if self.suggestions:
            lines.append("改进建议:")
            for i, s in enumerate(self.suggestions, 1):
                lines.append(f"  {i}. {s}")
        lines.append("=" * 38)
        return "\n".join(lines)


class BrightnessAnalyzer:
    """场馆亮度分析器"""

    # 亮度阈值（0-255 灰度空间）
    LUX_MIN_MATCH = 180     # 对应约 500 lux（国际赛）
    LUX_MIN_NORMAL = 120    # 对应约 300 lux（一般比赛）
    LUX_MIN_TRAIN = 80      # 对应约 200 lux（训练）
    GLARE_THRESHOLD = 240  # 眩光阈值
    UNIFORMITY_MIN = 0.5    # 均匀度最低要求

    def __init__(self, glare_threshold: int = 240):
        self.glare_threshold = glare_threshold

    def analyze(self, image_path: str, roi: Optional[tuple] = None) -> LightingReport:
        """
        分析场馆照片的灯光状况

        Args:
            image_path: 图片路径
            roi: 可选，感兴趣区域 (x, y, w, h)

        Returns:
            LightingReport 评估报告
        """
        img = self._read_image(image_path)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if roi:
            x, y, w, h = roi
            gray = gray[y:y+h, x:x+w]

        # 1. 平均亮度
        mean_brightness = float(np.mean(gray))
        brightness_pct = mean_brightness / 255 * 100

        # 2. 亮度均匀度 = 1 - (标准差 / 均值)
        std_brightness = float(np.std(gray))
        uniformity = max(0.0, 1.0 - std_brightness / (mean_brightness + 1e-6))

        # 3. 眩光检测：亮度超过阈值的像素比例
        glare_mask = gray > self.glare_threshold
        glare_pixels = int(np.sum(glare_mask))
        total_pixels = gray.size
        glare_ratio = glare_pixels / total_pixels

        # 连通区域数（近似眩光源数量）
        glare_regions = self._count_glare_regions(gray)

        # 4. 亮度分布
        brightness_dist = self._describe_distribution(gray)

        # 5. 结论
        conclusion, suggestions = self._evaluate(mean_brightness, uniformity, glare_ratio)

        return LightingReport(
            mean_brightness=mean_brightness,
            brightness_pct=brightness_pct,
            uniformity=uniformity,
            has_glare=glare_ratio > 0.01,
            glare_regions=glare_regions,
            brightness_dist=brightness_dist,
            conclusion=conclusion,
            suggestions=suggestions,
        )

    def _read_image(self, image_path: str):
        """读取图片（兼容中文路径）"""
        import os
        if not os.path.exists(image_path):
            return None
        # cv2.imread 不支持中文路径，用 numpy 中转
        data = np.fromfile(image_path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    def _count_glare_regions(self, gray: np.ndarray) -> int:
        """统计眩光连通区域数"""
        _, binary = cv2.threshold(gray, self.glare_threshold, 255, cv2.THRESH_BINARY)
        # 膨胀合并相邻区域
        kernel = np.ones((5, 5), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=2)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # 只保留面积大于 100 像素的区域
        return sum(1 for c in contours if cv2.contourArea(c) > 100)

    def _describe_distribution(self, gray: np.ndarray) -> str:
        """描述亮度分布特征"""
        mean = np.mean(gray)
        std = np.std(gray)
        median = np.median(gray)

        if std < 20:
            dist_type = "均匀"
        elif std < 40:
            dist_type = "较均匀"
        else:
            dist_type = "不均匀"

        if median > mean + 10:
            skew = "偏亮（多数像素较亮）"
        elif median < mean - 10:
            skew = "偏暗（多数像素较暗）"
        else:
            skew = "对称分布"

        return f"{dist_type}，{skew}（均值{mean:.0f}，中位数{median:.0f}，标准差{std:.0f}）"

    def _evaluate(self, mean: float, uniformity: float, glare_ratio: float):
        """综合评估，生成结论和建议"""
        suggestions = []

        # 亮度等级
        if mean >= self.LUX_MIN_MATCH:
            level = "国际比赛标准"
        elif mean >= self.LUX_MIN_NORMAL:
            level = "一般比赛标准"
        elif mean >= self.LUX_MIN_TRAIN:
            level = "训练/休闲标准"
        else:
            level = "偏暗，未达训练标准"
            suggestions.append("建议增加照明灯具数量或更换高功率灯泡")

        # 均匀度
        if uniformity < self.UNIFORMITY_MIN:
            suggestions.append(f"亮度均匀度({uniformity:.2f})偏低，建议调整灯具角度或加装漫射罩")

        # 眩光
        if glare_ratio > 0.05:
            suggestions.append(f"眩光比例({glare_ratio*100:.1f}%)偏高，建议加装防眩光格栅或调整灯具位置")
        elif glare_ratio > 0.01:
            suggestions.append("存在轻微眩光，建议关注灯具直射方向")

        # 最终结论
        if not suggestions:
            conclusion = f"达标（{level}），灯光条件适合羽毛球运动"
        else:
            conclusion = f"基本达标（{level}），但有改进空间"

        return conclusion, suggestions


def analyze_court_lighting(image_path: str, roi: Optional[tuple] = None) -> LightingReport:
    """快捷函数：一步分析场馆灯光"""
    analyzer = BrightnessAnalyzer()
    return analyzer.analyze(image_path, roi)
