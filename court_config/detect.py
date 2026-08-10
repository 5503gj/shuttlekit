"""
场地线检测 - 核心模块
功能：从场馆照片检测羽毛球场地线，识别场地类型

BWF 场地标准尺寸：
  - 单打场地: 13.40m × 5.18m
  - 双打场地: 13.40m × 6.10m
  - 球网高度: 1.55m（两端），1.524m（中间）
  - 发球线距网: 1.98m
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class CourtDetection:
    """场地检测结果"""
    line_count: int                  # 检测到的线段数
    court_type: str                  # 场地类型（单打/双打/无法判断）
    has_boundary: bool               # 是否检测到边界线
    has_service_line: bool           # 是否检测到发球线
    has_center_line: bool            # 是否检测到中线
    corners: List[Tuple[int, int]] = field(default_factory=list)  # 场地角点
    annotated_image: Optional[np.ndarray] = None  # 标注后的图像

    def __str__(self):
        lines = [
            "========== 场地检测结果 ==========",
            f"检测到线段数: {self.line_count}",
            f"场地类型: {self.court_type}",
            f"边界线: {'有' if self.has_boundary else '无'}",
            f"发球线: {'有' if self.has_service_line else '无'}",
            f"中线: {'有' if self.has_center_line else '无'}",
            f"角点数: {len(self.corners)}",
            "==================================",
        ]
        return "\n".join(lines)


class CourtDetector:
    """羽毛球场地检测器"""

    def __init__(self,
                 canny_low: int = 50,
                 canny_high: int = 150,
                 hough_threshold: int = 80,
                 min_line_length: int = 50,
                 max_line_gap: int = 10):
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.hough_threshold = hough_threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap

    def detect(self, image_path: str, output_path: Optional[str] = None) -> CourtDetection:
        """
        检测场地线

        Args:
            image_path: 场馆照片路径
            output_path: 标注图输出路径（可选）

        Returns:
            CourtDetection 检测结果
        """
        img = self._read_image(image_path)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. 高斯模糊去噪
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 2. Canny 边缘检测
        edges = cv2.Canny(blurred, self.canny_low, self.canny_high)

        # 3. 霍夫变换检测直线
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180,
            threshold=self.hough_threshold,
            minLineLength=self.min_line_length,
            maxLineGap=self.max_line_gap
        )

        # 4. 分类线段（水平/垂直/对角）
        horizontal, vertical, diagonal = self._classify_lines(lines)

        # 5. 判断场地类型
        court_type = self._judge_court_type(horizontal, vertical)

        # 6. 角点检测
        corners = self._find_corners(edges)

        # 7. 判断关键线
        has_boundary = len(horizontal) >= 2 and len(vertical) >= 2
        has_service_line = len(horizontal) >= 4  # 发球线
        has_center_line = len(vertical) >= 3      # 中线

        # 8. 绘制标注图
        annotated = img.copy()
        if lines is not None:
            for line in lines:
                coords = line.flatten() if hasattr(line, 'flatten') else line
                if len(coords) >= 4:
                    x1, y1, x2, y2 = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
                    cv2.line(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # 标注角点
        for pt in corners:
            cv2.circle(annotated, pt, 8, (0, 0, 255), -1)

        if output_path:
            self._write_image(output_path, annotated)

        line_count = 0 if lines is None else len(lines)

        return CourtDetection(
            line_count=line_count,
            court_type=court_type,
            has_boundary=has_boundary,
            has_service_line=has_service_line,
            has_center_line=has_center_line,
            corners=corners,
            annotated_image=annotated,
        )

    def _read_image(self, image_path: str):
        """读取图片（兼容中文路径）"""
        import os
        if not os.path.exists(image_path):
            return None
        data = np.fromfile(image_path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    def _write_image(self, output_path: str, img: np.ndarray):
        """写入图片（兼容中文路径）"""
        ext = os.path.splitext(output_path)[1]
        result, data = cv2.imencode(ext, img)
        if result:
            data.tofile(output_path)

    def _classify_lines(self, lines) -> Tuple[list, list, list]:
        """将线段分为水平/垂直/对角"""
        horizontal, vertical, diagonal = [], [], []
        if lines is None:
            return horizontal, vertical, diagonal

        for line in lines:
            # HoughLinesP 返回的 line 可能是 [[x1,y1,x2,y2]] 或 [x1,y1,x2,y2]
            coords = line.flatten() if hasattr(line, 'flatten') else line
            if len(coords) >= 4:
                x1, y1, x2, y2 = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
            else:
                continue
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dx < 10:          # 近似垂直
                vertical.append(line)
            elif dy < 10:        # 近似水平
                horizontal.append(line)
            else:
                diagonal.append(line)

        return horizontal, vertical, diagonal

    def _judge_court_type(self, horizontal: list, vertical: list) -> str:
        """根据线段数粗略判断场地类型"""
        h_count = len(horizontal)
        v_count = len(vertical)

        # 双打场地通常有更多线段
        if h_count >= 6 and v_count >= 4:
            return "双打场地"
        elif h_count >= 3 and v_count >= 2:
            return "单打场地"
        elif h_count >= 2 or v_count >= 2:
            return "无法确定（线段不足）"
        else:
            return "未检测到完整场地"

    def _find_corners(self, edges: np.ndarray) -> List[Tuple[int, int]]:
        """使用 Shi-Tomasi 角点检测"""
        corners = cv2.goodFeaturesToTrack(edges, maxCorners=20, qualityLevel=0.01,
                                          minDistance=30, blockSize=7)
        result = []
        if corners is not None:
            for pt in corners:
                x, y = pt[0]
                x, y = int(x), int(y)
                result.append((x, y))
        return result
