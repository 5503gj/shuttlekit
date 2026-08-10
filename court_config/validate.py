"""
场地尺寸校验模块
功能：根据检测到的角点和像素尺寸，校验场地是否符合 BWF 标准

BWF 场地标准（单位：米）：
  单打: 13.40 × 5.18
  双打: 13.40 × 6.10
  球网高度: 端点 1.55m，中心 1.524m
  前发球线距网: 1.98m
  后发球线距底线: 0.76m（双打）
  边线外安全区: 单打 ≥1.0m，双打 ≥1.46m
"""

from dataclasses import dataclass
from typing import Tuple, List, Optional
import numpy as np


@dataclass
class ValidationResult:
    """校验结果"""
    aspect_ratio: float          # 长宽比
    expected_ratio: float        # 期望长宽比
    ratio_ok: bool               # 长宽比是否达标
    court_type: str              # 判定类型
    errors: list
    warnings: list

    def __str__(self):
        lines = [
            "========== 场地尺寸校验 ==========",
            f"判定类型: {self.court_type}",
            f"长宽比: {self.aspect_ratio:.2f} (期望: {self.expected_ratio:.2f})",
            f"长宽比校验: {'通过' if self.ratio_ok else '不通过'}",
        ]
        if self.errors:
            lines.append(f"错误: {self.errors}")
        if self.warnings:
            lines.append(f"警告: {self.warnings}")
        lines.append("==================================")
        return "\n".join(lines)


class CourtValidator:
    """场地尺寸校验器"""

    # BWF 标准
    SINGLES_LENGTH = 13.40
    SINGLES_WIDTH = 5.18
    DOUBLES_LENGTH = 13.40
    DOUBLES_WIDTH = 6.10
    NET_HEIGHT_END = 1.55
    NET_HEIGHT_CENTER = 1.524

    SINGLES_RATIO = SINGLES_LENGTH / SINGLES_WIDTH      # ~2.587
    DOUBLES_RATIO = DOUBLES_LENGTH / DOUBLES_WIDTH       # ~2.197

    RATIO_TOLERANCE = 0.08  # 8% 容差（拍摄角度会产生偏差）

    def validate_from_corners(self, corners: List[Tuple[int, int]]) -> ValidationResult:
        """
        从角点校验场地尺寸

        Args:
            corners: 检测到的角点列表 [(x, y), ...]

        Returns:
            ValidationResult 校验结果
        """
        errors = []
        warnings = []

        if len(corners) < 4:
            return ValidationResult(
                aspect_ratio=0.0, expected_ratio=0.0,
                ratio_ok=False, court_type="无法判断",
                errors=["角点不足4个，无法校验"],
                warnings=[],
            )

        # 取最外围的4个角点（凸包）
        pts = np.array(corners, dtype=np.float32)
        hull = cv2_convex_hull(pts)

        # 计算长和宽（像素）
        length_px, width_px = self._measure_sides(hull)
        if length_px == 0 or width_px == 0:
            errors.append("无法测量场地边长，可能角点有误")

        aspect_ratio = length_px / width_px if width_px > 0 else 0

        # 判断是单打还是双打
        ratio_diff_singles = abs(aspect_ratio - self.SINGLES_RATIO)
        ratio_diff_doubles = abs(aspect_ratio - self.DOUBLES_RATIO)

        if ratio_diff_doubles < ratio_diff_singles:
            court_type = "双打"
            expected_ratio = self.DOUBLES_RATIO
        else:
            court_type = "单打"
            expected_ratio = self.SINGLES_RATIO

        # 校验长宽比
        ratio_error = abs(aspect_ratio - expected_ratio) / expected_ratio
        ratio_ok = ratio_error <= self.RATIO_TOLERANCE

        if not ratio_ok:
            warnings.append(f"长宽比偏差 {ratio_error*100:.1f}%，"
                            f"可能因拍摄角度或检测误差导致")

        # 安全区校验（无法直接测量，提示）
        warnings.append("安全区需现场实测，标准: 单打≥1.0m，双打≥1.46m")

        return ValidationResult(
            aspect_ratio=aspect_ratio,
            expected_ratio=expected_ratio,
            ratio_ok=ratio_ok,
            court_type=court_type,
            errors=errors,
            warnings=warnings,
        )

    def _measure_sides(self, hull: np.ndarray) -> Tuple[float, float]:
        """从凸包测量长和宽"""
        # 找到最远的两对边
        if len(hull) < 4:
            return 0.0, 0.0

        # 简化：取凸包的4个顶点（近似最小外接矩形）
        rect = cv2_min_area_rect(hull)
        length, width = rect[1]
        # 确保长 > 宽
        if length < width:
            length, width = width, length
        return float(length), float(width)

    def validate_net_height(self, net_height_cm: float) -> dict:
        """
        校验球网高度

        Args:
            net_height_cm: 实测球网高度（厘米）

        Returns:
            {"ok": bool, "error": str, "standard": float}
        """
        # 中心高度标准 1.524m = 152.4cm
        standard = 152.4
        tolerance = 2.0  # 2cm 容差
        diff = abs(net_height_cm - standard)

        if diff <= tolerance:
            return {"ok": True, "error": "", "standard": standard}
        elif net_height_cm > standard:
            return {"ok": False, "error": f"球网偏高 {diff:.1f}cm", "standard": standard}
        else:
            return {"ok": False, "error": f"球网偏低 {diff:.1f}cm", "standard": standard}


def cv2_convex_hull(pts: np.ndarray) -> np.ndarray:
    """包装 cv2 凸包计算"""
    import cv2
    hull = cv2.convexHull(pts)
    return hull.reshape(-1, 2)


def cv2_min_area_rect(pts: np.ndarray):
    """包装 cv2 最小外接矩形"""
    import cv2
    rect = cv2.minAreaRect(pts)
    return rect
