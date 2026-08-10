"""
shuttle_speed 模块测试
测试用例覆盖：速度计算、像素标定、边界条件
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shuttle_speed.speed_calc import SpeedCalculator, SpeedReport, SPEED_REFERENCE


class TestSpeedCalculator:
    """速度计算器测试"""

    def test_basic_speed_calculation(self):
        """正常场景：基本速度计算"""
        calc = SpeedCalculator(fps=30, px_per_meter=50)
        # 30fps, 每帧移动50像素 = 50/50=1米/帧 = 30米/秒 = 108 km/h
        trajectory = [(0, 0), (50, 0), (100, 0), (150, 0)]
        report = calc.calculate(trajectory)
        assert report.avg_speed_kmh > 0
        assert report.max_speed_kmh > 0

    def test_diagonal_movement(self):
        """正常场景：对角线运动"""
        calc = SpeedCalculator(fps=30, px_per_meter=50)
        # 对角线运动：每帧(50, 50) = √(50²+50²) ≈ 70.7像素
        trajectory = [(0, 0), (50, 50), (100, 100)]
        report = calc.calculate(trajectory)
        assert report.avg_speed_kmh > 0

    def test_empty_trajectory(self):
        """边界场景：空轨迹"""
        calc = SpeedCalculator()
        report = calc.calculate([])
        assert report.max_speed_kmh == 0
        assert report.avg_speed_kmh == 0

    def test_single_point(self):
        """边界场景：单点轨迹（无法计算速度）"""
        calc = SpeedCalculator()
        report = calc.calculate([(100, 100)])
        assert report.max_speed_kmh == 0

    def test_stationary_object(self):
        """边界场景：静止目标"""
        calc = SpeedCalculator(fps=30, px_per_meter=50)
        trajectory = [(100, 100), (100, 100), (100, 100)]
        report = calc.calculate(trajectory)
        assert report.avg_speed_kmh == 0

    def test_calibration(self):
        """正常场景：像素标定"""
        calc = SpeedCalculator()
        # 场地长边 13.4m，图像中 670 像素
        px_per_m = calc.calibrate_px_per_meter(670, 13.4)
        assert abs(px_per_m - 50.0) < 0.1

    def test_speed_reference(self):
        """正常场景：球速参考表不为空"""
        assert "世界纪录" in SPEED_REFERENCE
        assert "421" in SPEED_REFERENCE["世界纪录"]

    def test_report_str(self):
        """正常场景：报告可打印"""
        calc = SpeedCalculator(fps=30, px_per_meter=50)
        trajectory = [(0, 0), (50, 0)]
        report = calc.calculate(trajectory)
        text = str(report)
        assert "球速检测报告" in text
        assert "km/h" in text
