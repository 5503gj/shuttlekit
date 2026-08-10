"""
比赛数据记录模块
功能：记录比赛得分、回合计数、击球类型，生成结构化数据
"""

import csv
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime


@dataclass
class Point:
    """单次得分记录"""
    rally: int            # 第几回合
    server: str           # 发球方 A/B
    winner: str           # 得分方 A/B
    score_a: int           # A 方得分
    score_b: int           # B 方得分
    shot_type: str         # 得分方式（杀球/吊球/网前/推球/对方失误）
    duration: float        # 回合时长（秒）
    timestamp: str = ""   # 记录时间


@dataclass
class MatchData:
    """完整比赛数据"""
    player_a: str
    player_b: str
    points: List[Point] = field(default_factory=list)
    start_time: str = ""

    def total_rallies(self) -> int:
        return len(self.points)

    def final_score(self) -> str:
        if not self.points:
            return "0 - 0"
        last = self.points[-1]
        return f"{last.score_a} - {last.score_b}"

    def shot_distribution(self) -> dict:
        """击球类型分布"""
        dist = {}
        for p in self.points:
            dist[p.shot_type] = dist.get(p.shot_type, 0) + 1
        return dist

    def avg_rally_duration(self) -> float:
        if not self.points:
            return 0
        return sum(p.duration for p in self.points) / len(self.points)


class MatchRecorder:
    """比赛记录器"""

    SHOT_TYPES = ["杀球", "吊球", "网前小球", "推球", "高远球",
                  "扑球", "抽球", "对方失误", "其他"]

    def __init__(self, player_a: str = "A", player_b: str = "B"):
        self.data = MatchData(player_a=player_a, player_b=player_b,
                            start_time=datetime.now().isoformat())
        self._current_rally = 0

    def add_point(self, server: str, winner: str, shot_type: str,
                  duration: float = 0.0) -> Point:
        """记录一次得分"""
        self._current_rally += 1
        score_a = sum(1 for p in self.data.points if p.winner == "A") + (1 if winner == "A" else 0)
        score_b = sum(1 for p in self.data.points if p.winner == "B") + (1 if winner == "B" else 0)

        point = Point(
            rally=self._current_rally,
            server=server,
            winner=winner,
            score_a=score_a,
            score_b=score_b,
            shot_type=shot_type,
            duration=duration,
            timestamp=datetime.now().isoformat(),
        )
        self.data.points.append(point)
        return point

    def export_csv(self, filepath: str):
        """导出 CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["回合", "发球方", "得分方", "A得分", "B得分",
                           "得分方式", "时长(秒)", "时间"])
            for p in self.data.points:
                writer.writerow([p.rally, p.server, p.winner, p.score_a,
                               p.score_b, p.shot_type, p.duration, p.timestamp])

    def export_json(self, filepath: str):
        """导出 JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.data), f, ensure_ascii=False, indent=2)

    def summary(self) -> str:
        """比赛摘要"""
        d = self.data
        lines = [
            f"========== 比赛摘要 ==========",
            f"选手: {d.player_a} vs {d.player_b}",
            f"总回合: {d.total_rallies()}",
            f"最终比分: {d.final_score()}",
            f"平均回合时长: {d.avg_rally_duration():.1f} 秒",
            f"击球类型分布:",
        ]
        for shot, count in sorted(d.shot_distribution().items(),
                                   key=lambda x: -x[1]):
            lines.append(f"  {shot}: {count} 次")
        lines.append("=" * 30)
        return "\n".join(lines)
