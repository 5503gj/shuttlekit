"""
比赛数据可视化模块
功能：生成比分曲线、击球分布、回合时长等图表
"""

import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional
from .recorder import MatchData


class StatsVisualizer:
    """比赛数据可视化"""

    # 配色方案
    COLOR_A = '#E74C3C'   # 红色 - 中国习惯
    COLOR_B = '#2ECC71'   # 绿色
    COLOR_BG = '#FAFAFA'
    COLOR_GRID = '#E0E0E0'

    def __init__(self, font_size: int = 12):
        plt.rcParams['font.size'] = font_size
        plt.rcParams['axes.facecolor'] = self.COLOR_BG
        plt.rcParams['figure.facecolor'] = 'white'

    def plot_score_curve(self, data: MatchData, output_path: str):
        """比分曲线"""
        fig, ax = plt.subplots(figsize=(10, 5))

        rallies = [p.rally for p in data.points]
        scores_a = [p.score_a for p in data.points]
        scores_b = [p.score_b for p in data.points]

        ax.plot(rallies, scores_a, 'o-', color=self.COLOR_A,
                label=data.player_a, linewidth=2, markersize=6)
        ax.plot(rallies, scores_b, 's-', color=self.COLOR_B,
                label=data.player_b, linewidth=2, markersize=6)

        ax.set_xlabel('回合')
        ax.set_ylabel('得分')
        ax.set_title(f'比分曲线 {data.final_score()}')
        ax.legend()
        ax.grid(True, color=self.COLOR_GRID, alpha=0.5)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

    def plot_shot_distribution(self, data: MatchData, output_path: str):
        """击球类型分布饼图"""
        dist = data.shot_distribution()
        if not dist:
            return

        fig, ax = plt.subplots(figsize=(8, 8))
        labels = list(dist.keys())
        sizes = list(dist.values())
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

        ax.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=90,
               colors=colors, textprops={'fontsize': 11})
        ax.set_title('击球类型分布')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

    def plot_rally_duration(self, data: MatchData, output_path: str):
        """回合时长分布"""
        fig, ax = plt.subplots(figsize=(10, 5))

        rallies = [p.rally for p in data.points]
        durations = [p.duration for p in data.points]
        colors = [self.COLOR_A if p.winner == 'A' else self.COLOR_B for p in data.points]

        ax.bar(rallies, durations, color=colors, alpha=0.8)
        ax.set_xlabel('回合')
        ax.set_ylabel('时长 (秒)')
        ax.set_title('回合时长分布（红=A得分，绿=B得分）')
        ax.grid(True, color=self.COLOR_GRID, alpha=0.5, axis='y')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

    def generate_dashboard(self, data: MatchData, output_dir: str):
        """生成完整数据看板"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        self.plot_score_curve(data, f"{output_dir}/score_curve.png")
        self.plot_shot_distribution(data, f"{output_dir}/shot_distribution.png")
        self.plot_rally_duration(data, f"{output_dir}/rally_duration.png")

        # 生成 HTML 看板
        html = self._generate_html(data, output_dir)
        with open(f"{output_dir}/dashboard.html", 'w', encoding='utf-8') as f:
            f.write(html)

    def _generate_html(self, data: MatchData, img_dir: str) -> str:
        """生成 HTML 看板"""
        dist = data.shot_distribution()
        dist_rows = "\n".join(
            f"<tr><td>{k}</td><td>{v}</td><td>{v/data.total_rallies()*100:.0f}%</td></tr>"
            for k, v in sorted(dist.items(), key=lambda x: -x[1])
        )

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>比赛数据看板 - {data.player_a} vs {data.player_b}</title>
<style>
body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 20px; background: #f5f5f5; }}
.card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
h1 {{ color: #333; }}
h2 {{ color: #555; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
.stat-box {{ text-align: center; padding: 16px; background: #f8f9fa; border-radius: 8px; }}
.stat-num {{ font-size: 28px; font-weight: bold; color: #E74C3C; }}
.stat-label {{ color: #666; font-size: 14px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
th, td {{ padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0; }}
th {{ background: #f0f0f0; font-weight: bold; }}
img {{ max-width: 100%; border-radius: 8px; }}
</style>
</head>
<body>
<h1>羽毛球比赛数据看板</h1>
<div class="card">
  <h2>比赛概况</h2>
  <div class="stat-grid">
    <div class="stat-box"><div class="stat-num">{data.player_a} vs {data.player_b}</div><div class="stat-label">对阵</div></div>
    <div class="stat-box"><div class="stat-num">{data.final_score()}</div><div class="stat-label">最终比分</div></div>
    <div class="stat-box"><div class="stat-num">{data.total_rallies()}</div><div class="stat-label">总回合</div></div>
    <div class="stat-box"><div class="stat-num">{data.avg_rally_duration():.1f}s</div><div class="stat-label">平均回合时长</div></div>
  </div>
</div>
<div class="card"><h2>比分曲线</h2><img src="score_curve.png"></div>
<div class="card"><h2>击球类型分布</h2>
  <table><tr><th>类型</th><th>次数</th><th>占比</th></tr>{dist_rows}</table>
  <img src="shot_distribution.png">
</div>
<div class="card"><h2>回合时长分布</h2><img src="rally_duration.png"></div>
</body>
</html>"""
