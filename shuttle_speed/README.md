# shuttle_speed - 球速检测

从视频检测羽毛球轨迹并计算球速。

## 功能

1. **球轨迹追踪**：基于 YOLO 检测每帧球的位置
2. **速度计算**：帧间位移 → 像素速度 → 实际速度
3. **速度统计**：最高速度、平均速度、速度曲线
4. **像素标定**：用场地已知尺寸校准像素到米的换算

## 安装进阶依赖

```bash
pip install ultralytics torch
# 下载 YOLO 权重（自动完成，首次运行会下载）
```

## 用法

### 方式 1：从视频自动检测

```python
from shuttle_speed import ShuttleTracker

tracker = ShuttleTracker(fps=30, method="yolo")
result = tracker.track_from_video("match.mp4", output_path="tracked.mp4")
print(result.speed_report)
```

### 方式 2：从 CSV 读取（手动标注的轨迹）

```python
from shuttle_speed import ShuttleTracker

tracker = ShuttleTracker(fps=30)
result = tracker.track_from_csv("trajectory.csv")
print(result.speed_report)
```

### 像素标定

```python
from shuttle_speed import SpeedCalculator

calc = SpeedCalculator(fps=30, px_per_meter=50)
# 如果场地长边在图像中是 500 像素，实际 13.4 米
calc.calibrate_px_per_meter(known_length_px=500, known_length_m=13.4)
# 之后 calc 的换算系数会自动更新
```

## 球速参考

| 类型 | 速度范围 |
|------|---------|
| 初学者杀球 | 200-260 km/h |
| 业余高手杀球 | 260-350 km/h |
| 职业选手杀球 | 350-420 km/h |
| 世界纪录 | 421 km/h (傅海峰) |

## 注意事项

- YOLO 通用模型对羽毛球的检测率可能不高，建议使用 TrackNet 专用模型
- 速度计算需要正确的像素标定，否则结果不准确
- 拍摄角度（斜拍 vs 俯视）会影响检测效果，俯视最佳

## 参考项目

- [TrackNet](https://github.com/yastrebksv/TrackNet) - 专用羽球追踪模型
- [Good-Badminton](https://github.com/Chen-Jason/Good-Badminton) - 完整鹰眼系统
- [BaddieVision](https://github.com/MaxLinCode/BaddieVision) - 综合分析工具链
