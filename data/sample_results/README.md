# ShuttleKit 样例输出

此目录存放示例运行结果（灯光报告、场地标注图、比赛看板等），供参考。

## 目录结构

```
sample_results/
├── README.md              # 本文件
├── court_photo.jpg        # 示例场馆照片（自行放入）
├── annotated_court.jpg    # 场地标注图（运行后生成）
├── lighting_report.txt    # 灯光评估报告（运行后生成）
└── dashboard/             # 比赛数据看板（运行后生成）
    ├── score_curve.png
    ├── shot_distribution.png
    ├── rally_duration.png
    └── dashboard.html
```

## 如何生成示例

```bash
# 灯光评估
python -m court_lighting.analyze --image sample_results/court_photo.jpg

# 场地检测
python -c "
from court_config import CourtDetector
d = CourtDetector()
r = d.detect('sample_results/court_photo.jpg', output_path='sample_results/annotated_court.jpg')
print(r)
"

# 比赛看板
python -c "
from match_stats import MatchRecorder, StatsVisualizer
rec = MatchRecorder('A', 'B')
rec.add_point('A', 'A', '杀球', 8.5)
rec.add_point('A', 'B', '吊球', 6.2)
rec.add_point('B', 'A', '网前小球', 4.1)
viz = StatsVisualizer()
viz.generate_dashboard(rec.data, 'sample_results/dashboard/')
"
```
