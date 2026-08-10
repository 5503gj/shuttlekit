# court_config - 场地配置

检测场馆照片中的场地线，并校验尺寸是否符合 BWF 标准。

## 功能

1. **场地线检测**：基于 Canny 边缘 + 霍夫变换
2. **场地类型判断**：根据线段数量判断单打/双打
3. **尺寸校验**：从角点计算长宽比，对照 BWF 标准
4. **球网高度校验**：输入实测高度，判断是否合规

## BWF 场地标准

| 项目 | 标准 | 说明 |
|------|------|------|
| 单打场地 | 13.40m × 5.18m | 长宽比 ≈ 2.587 |
| 双打场地 | 13.40m × 6.10m | 长宽比 ≈ 2.197 |
| 球网高度 | 中心 1.524m，端点 1.55m | 容差 ±2cm |
| 安全区 | 单打 ≥1.0m，双打 ≥1.46m | 场地外缘 |
| 灯光高度 | ≥ 7m（距地面） | 避免眩光 |

## 用法

```python
from court_config import CourtDetector, CourtValidator

# 检测场地线
detector = CourtDetector()
result = detector.detect("court_photo.jpg", output_path="annotated.jpg")
print(result)

# 校验尺寸
validator = CourtValidator()
vr = validator.validate_from_corners(result.corners)
print(vr)

# 校验球网高度
net_result = validator.validate_net_height(153.0)
print(net_result)
```
