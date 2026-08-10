# 快速上手

## Step 1: 安装

```bash
git clone https://github.com/your-username/ShuttleKit.git
cd ShuttleKit
pip install -r requirements.txt
```

## Step 2: 准备一张场馆照片

用手机拍一张羽毛球馆的照片，保存为 jpg。

## Step 3: 灯光评估

```bash
python -m court_lighting.analyze --image your_photo.jpg
```

## Step 4: 场地检测（可选）

```python
from court_config import CourtDetector

detector = CourtDetector()
result = detector.detect("your_photo.jpg", output_path="annotated.jpg")
print(result)
```

## Step 5: 比赛记录（可选）

```python
from match_stats import MatchRecorder, StatsVisualizer

recorder = MatchRecorder("A", "B")
recorder.add_point("A", "A", "杀球", 8.5)
recorder.add_point("A", "B", "吊球", 6.2)

viz = StatsVisualizer()
viz.generate_dashboard(recorder.data, "output/")
# 打开 output/dashboard.html 查看数据看板
```

## Step 6: 球拍推荐（可选）

```python
from equipment_kb import EquipmentRecommender, PlayerProfile

profile = PlayerProfile(level="中级", budget=800, play_style="进攻")
recommender = EquipmentRecommender()
print(recommender.format_recommendation(profile))
```

## 常见问题

参见 [FAQ.md](./FAQ.md)
