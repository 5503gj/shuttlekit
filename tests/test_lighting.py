"""
court_lighting 模块测试
测试用例覆盖：正常图片、ROI指定区域、眩光检测、均匀度计算、边界条件
"""

import pytest
import numpy as np
import cv2
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from court_lighting.brightness import BrightnessAnalyzer, analyze_court_lighting, LightingReport


def _save_image(path: str, img: np.ndarray):
    """保存图片（兼容中文路径）"""
    result, data = cv2.imencode('.jpg', img)
    if result:
        data.tofile(path)


@pytest.fixture
def bright_image(tmp_path):
    """生成一张全白亮图"""
    img = np.ones((480, 640, 3), dtype=np.uint8) * 250
    path = str(tmp_path / "bright.jpg")
    _save_image(path, img)
    return path


@pytest.fixture
def dark_image(tmp_path):
    """生成一张全黑暗图"""
    img = np.ones((480, 640, 3), dtype=np.uint8) * 30
    path = str(tmp_path / "dark.jpg")
    _save_image(path, img)
    return path


@pytest.fixture
def glare_image(tmp_path):
    """生成一张带眩光的图"""
    img = np.ones((480, 640, 3), dtype=np.uint8) * 120
    # 左上角加一个高光区
    img[50:150, 50:150] = 250
    path = str(tmp_path / "glare.jpg")
    _save_image(path, img)
    return path


@pytest.fixture
def uneven_image(tmp_path):
    """生成一张亮度不均匀的图"""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:240] = 200  # 上半亮
    img[240:] = 50   # 下半暗
    path = str(tmp_path / "uneven.jpg")
    _save_image(path, img)
    return path


class TestBrightnessAnalyzer:
    """亮度分析器测试"""

    def test_bright_image_has_high_brightness(self, bright_image):
        """正常场景：亮图应该有高亮度值"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(bright_image)
        assert report.mean_brightness > 200
        assert report.brightness_pct > 75

    def test_dark_image_has_low_brightness(self, dark_image):
        """正常场景：暗图应该有低亮度值"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(dark_image)
        assert report.mean_brightness < 50
        assert report.brightness_pct < 20

    def test_glare_detection(self, glare_image):
        """正常场景：带高光的图应检测到眩光"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(glare_image)
        assert report.has_glare == True
        assert report.glare_regions >= 1

    def test_no_glare_on_uniform_image(self, bright_image):
        """正常场景：均匀亮图（250值）阈值250时不应有眩光（250不大于250）"""
        analyzer = BrightnessAnalyzer(glare_threshold=250)
        report = analyzer.analyze(bright_image)
        assert report.has_glare == False  # 250 不 > 250，所以无眩光

    def test_uniformity_calculation(self, bright_image):
        """正常场景：均匀亮图的均匀度应很高"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(bright_image)
        assert report.uniformity > 0.9  # 全白图均匀度接近1

    def test_uneven_image_low_uniformity(self, uneven_image):
        """正常场景：不均匀图的均匀度应较低"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(uneven_image)
        assert report.uniformity < 0.5

    def test_roi_extraction(self, bright_image):
        """正常场景：指定ROI应该只分析该区域"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(bright_image, roi=(0, 0, 100, 100))
        assert report.mean_brightness > 200

    def test_conclusion_generated(self, bright_image):
        """正常场景：结论不应为空"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(bright_image)
        assert len(report.conclusion) > 0

    def test_file_not_found(self):
        """异常场景：文件不存在应报错"""
        analyzer = BrightnessAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze("nonexistent.jpg")

    def test_report_str_format(self, bright_image):
        """正常场景：报告应可正常打印"""
        analyzer = BrightnessAnalyzer()
        report = analyzer.analyze(bright_image)
        text = str(report)
        assert "场馆灯光评估报告" in text
        assert "平均亮度" in text


class TestAnalyzeCourtLighting:
    """快捷函数测试"""

    def test_quick_function_returns_report(self, bright_image):
        """正常场景：快捷函数返回LightingReport"""
        report = analyze_court_lighting(bright_image)
        assert isinstance(report, LightingReport)
