# match_stats - 比赛统计

记录比赛数据并生成可视化看板。

## 功能

1. **比赛记录**：逐回合记录得分、发球方、击球类型、回合时长
2. **数据导出**：CSV / JSON 格式
3. **可视化看板**：比分曲线、击球分布饼图、回合时长柱状图、HTML 数据看板

## 用法

```python
from match_stats import MatchRecorder, StatsVisualizer

# 记录比赛
recorder = MatchRecorder("林丹", "李宗伟")
recorder.add_point(server="A", winner="A", shot_type="杀球", duration=8.5)
recorder.add_point(server="A", winner="B", shot_type="吊球", duration=6.2)
recorder.add_point(server="B", winner="A", shot_type="网前小球", duration=4.1)

# 导出
recorder.export_csv("match.csv")
recorder.export_json("match.json")
print(recorder.summary())

# 生成可视化看板
viz = StatsVisualizer()
viz.generate_dashboard(recorder.data, "output/")
```

## 输出示例

```
========== 比赛摘要 ==========
选手: 林丹 vs 李宗伟
总回合: 3
最终比分: 2 - 1
平均回合时长: 6.3 秒
击球类型分布:
  杀球: 1 次
  吊球: 1 次
  网前小球: 1 次
==============================
```

## 颜色约定

遵循中国体育转播习惯：红方得分=红色，绿方得分=绿色。
