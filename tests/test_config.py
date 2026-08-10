"""
court_config 模块测试
测试用例覆盖：线检测、角点、校验器、球网高度
"""

import pytest
import numpy as np
import cv2
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from court_config.detect import CourtDetector, CourtDetection
from court_config.validate import CourtValidator, ValidationResult


def _save_image(path: str, img: np.ndarray):
    """保存图片（兼容中文路径）"""
    result, data = cv2.imencode('.jpg', img)
    if result:
        data.tofile(path)


@pytest.fixture
def court_image(tmp_path):
    """生成一张模拟场地线图（黑底白线）"""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # 画矩形边框
    cv2.rectangle(img, (100, 100), (540, 380), (255, 255, 255), 3)
    # 画中线
    cv2.line(img, (320, 100), (320, 380), (255, 255, 255), 2)
    # 画发球线
    cv2.line(img, (200, 100), (200, 380), (255, 255, 255), 2)
    cv2.line(img, (440, 100), (440, 380), (255, 255, 255), 2)
    path = str(tmp_path / "court.jpg")
    _save_image(path, img)
    return path


class TestCourtDetector:
    """场地检测器测试"""

    def test_detect_returns_result(self, court_image):
        """正常场景：检测返回结果对象"""
        detector = CourtDetector()
        result = detector.detect(court_image)
        assert isinstance(result, CourtDetection)
        assert result.line_count > 0

    def test_detect_court_type(self, court_image):
        """正常场景：应检测到场地"""
        detector = CourtDetector()
        result = detector.detect(court_image)
        assert result.court_type != "未检测到完整场地"

    def test_detect_corners(self, court_image):
        """正常场景：应检测到角点"""
        detector = CourtDetector()
        result = detector.detect(court_image)
        assert len(result.corners) > 0

    def test_file_not_found(self):
        """异常场景：文件不存在"""
        detector = CourtDetector()
        with pytest.raises(FileNotFoundError):
            detector.detect("nonexistent.jpg")

    def test_annotated_image(self, court_image, tmp_path):
        """正常场景：输出标注图"""
        detector = CourtDetector()
        output = str(tmp_path / "annotated.jpg")
        detector.detect(court_image, output_path=output)
        assert os.path.exists(output)

    def test_report_str(self, court_image):
        """正常场景：结果可打印"""
        detector = CourtDetector()
        result = detector.detect(court_image)
        text = str(result)
        assert "场地检测结果" in text


class TestCourtValidator:
    """校验器测试"""

    def test_validate_single_court_ratio(self):
        """正常场景：单打长宽比"""
        validator = CourtValidator()
        # 单打长宽比 ≈ 2.587，模拟 670×259 像素
        corners = [(0, 0), (670, 0), (670, 259), (0, 259)]
        result = validator.validate_from_corners(corners)
        assert result.court_type == "单打"
        assert result.ratio_ok == True

    def test_validate_double_court_ratio(self):
        """正常场景：双打长宽比"""
        validator = CourtValidator()
        # 双打长宽比 ≈ 2.197，模拟 670×305 像素
        corners = [(0, 0), (670, 0), (670, 305), (0, 305)]
        result = validator.validate_from_corners(corners)
        assert result.court_type == "双打"

    def test_insufficient_corners(self):
        """边界场景：角点不足"""
        validator = CourtValidator()
        result = validator.validate_from_corners([(100, 100), (200, 200)])
        assert not result.ratio_ok
        assert "角点不足" in result.errors[0]

    def test_net_height_ok(self):
        """正常场景：球网高度合格"""
        validator = CourtValidator()
        result = validator.validate_net_height(152.5)
        assert result["ok"] == True

    def test_net_height_too_low(self):
        """边界场景：球网太低"""
        validator = CourtValidator()
        result = validator.validate_net_height(140.0)
        assert result["ok"] == False
        assert "偏低" in result["error"]

    def test_net_height_too_high(self):
        """边界场景：球网太高"""
        validator = CourtValidator()
        result = validator.validate_net_height(160.0)
        assert result["ok"] == False
        assert "偏高" in result["error"]
