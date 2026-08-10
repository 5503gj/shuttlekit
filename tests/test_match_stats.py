"""
match_stats 模块测试
测试用例覆盖：比赛记录、得分计算、击球分布、导出功能
"""

import pytest
import os
import sys
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from match_stats.recorder import MatchRecorder, MatchData, Point


class TestMatchRecorder:
    """比赛记录器测试"""

    def test_add_single_point(self):
        """正常场景：记录单次得分"""
        recorder = MatchRecorder("A", "B")
        recorder.add_point(server="A", winner="A", shot_type="杀球", duration=8.5)
        assert recorder.data.total_rallies() == 1
        assert recorder.data.final_score() == "1 - 0"

    def test_add_multiple_points(self):
        """正常场景：记录多次得分"""
        recorder = MatchRecorder("A", "B")
        recorder.add_point("A", "A", "杀球", 8.0)
        recorder.add_point("A", "B", "吊球", 6.0)
        recorder.add_point("B", "A", "网前小球", 4.0)
        assert recorder.data.total_rallies() == 3
        assert recorder.data.final_score() == "2 - 1"

    def test_shot_distribution(self):
        """正常场景：击球分布统计"""
        recorder = MatchRecorder("A", "B")
        recorder.add_point("A", "A", "杀球", 8.0)
        recorder.add_point("A", "B", "杀球", 6.0)
        recorder.add_point("B", "A", "吊球", 4.0)
        dist = recorder.data.shot_distribution()
        assert dist["杀球"] == 2
        assert dist["吊球"] == 1

    def test_avg_rally_duration(self):
        """正常场景：平均回合时长"""
        recorder = MatchRecorder("A", "B")
        recorder.add_point("A", "A", "杀球", 8.0)
        recorder.add_point("A", "B", "吊球", 6.0)
        assert recorder.data.avg_rally_duration() == 7.0

    def test_empty_match(self):
        """边界场景：空比赛"""
        recorder = MatchRecorder("A", "B")
        assert recorder.data.total_rallies() == 0
        assert recorder.data.final_score() == "0 - 0"
        assert recorder.data.avg_rally_duration() == 0

    def test_export_csv(self, tmp_path):
        """正常场景：CSV 导出"""
        recorder = MatchRecorder("A", "B")
        recorder.add_point("A", "A", "杀球", 8.0)
        recorder.add_point("A", "B", "吊球", 6.0)

        csv_path = str(tmp_path / "test_match.csv")
        recorder.export_csv(csv_path)

        assert os.path.exists(csv_path)
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            assert "回合" in header[0]
            rows = list(reader)
            assert len(rows) == 2

    def test_export_json(self, tmp_path):
        """正常场景：JSON 导出"""
        recorder = MatchRecorder("A", "B")
        recorder.add_point("A", "A", "杀球", 8.0)

        json_path = str(tmp_path / "test_match.json")
        recorder.export_json(json_path)

        assert os.path.exists(json_path)
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data["player_a"] == "A"
            assert len(data["points"]) == 1

    def test_summary_output(self):
        """正常场景：摘要输出"""
        recorder = MatchRecorder("林丹", "李宗伟")
        recorder.add_point("A", "A", "杀球", 8.0)
        summary = recorder.summary()
        assert "林丹" in summary
        assert "李宗伟" in summary
        assert "比赛摘要" in summary
