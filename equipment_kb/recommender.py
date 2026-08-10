"""
器材推荐模块
功能：根据玩家水平、预算、打法推荐合适的球拍/球鞋/球
"""

import json
import os
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class PlayerProfile:
    """玩家画像"""
    level: str          # 入门 / 初级 / 中级 / 高级
    budget: int          # 预算（元）
    play_style: str      # 打法: 进攻 / 防守 / 全能 / 前场快攻
    gender: str = "男"  # 性别（影响推荐重量）


class EquipmentRecommender:
    """器材推荐器"""

    LEVEL_MAP = {"入门": 0, "初级": 1, "中级": 2, "高级": 3, "中高级": 3}
    STYLE_MAP = {
        "进攻": ["头重", "平衡偏头重"],
        "防守": ["平衡", "头轻"],
        "全能": ["平衡", "平衡偏头重"],
        "前场快攻": ["头轻"],
    }

    def __init__(self):
        self.rackets = self._load_rackets()

    def _load_rackets(self) -> List[Dict]:
        """加载球拍数据"""
        json_path = os.path.join(os.path.dirname(__file__), "rackets.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def recommend_rackets(self, profile: PlayerProfile, top_n: int = 3) -> List[Dict]:
        """
        推荐球拍

        Args:
            profile: 玩家画像
            top_n: 返回前 N 个推荐

        Returns:
            推荐列表（含匹配理由）
        """
        scored = []
        for racket in self.rackets:
            score, reasons = self._score_racket(racket, profile)
            scored.append((racket, score, reasons))

        scored.sort(key=lambda x: -x[1])

        results = []
        for racket, score, reasons in scored[:top_n]:
            r = dict(racket)
            r["match_score"] = score
            r["match_reasons"] = reasons
            results.append(r)

        return results

    def _score_racket(self, racket: Dict, profile: PlayerProfile) -> tuple:
        """给球拍打匹配分"""
        score = 0
        reasons = []

        # 1. 水平匹配
        racket_level = self.LEVEL_MAP.get(racket.get("level", "初级"), 1)
        player_level = self.LEVEL_MAP.get(profile.level, 0)
        level_diff = abs(racket_level - player_level)
        if level_diff == 0:
            score += 30
            reasons.append("水平匹配")
        elif level_diff == 1:
            score += 15
            reasons.append("水平相近")

        # 2. 预算匹配
        price_str = racket.get("price_range", "0-0")
        prices = [int(p.strip()) for p in price_str.split("-")]
        if prices and len(prices) == 2:
            if prices[0] <= profile.budget <= prices[1]:
                score += 30
                reasons.append("价格在预算内")
            elif prices[0] <= profile.budget:
                score += 10
            else:
                score -= 20
                reasons.append("超预算")

        # 3. 打法匹配
        preferred_balance = self.STYLE_MAP.get(profile.play_style, ["平衡"])
        racket_balance = racket.get("balance", "平衡")
        if racket_balance in preferred_balance:
            score += 25
            reasons.append(f"打法匹配（{racket_balance}）")

        # 4. 性别重量匹配
        if profile.gender == "女":
            if "5U" in racket.get("weight", ""):
                score += 10
                reasons.append("轻量适合女性")
        else:
            if "4U" in racket.get("weight", ""):
                score += 5

        return max(score, 0), reasons

    def format_recommendation(self, profile: PlayerProfile, top_n: int = 3) -> str:
        """格式化推荐结果为可读文本"""
        recs = self.recommend_rackets(profile, top_n)
        lines = [
            "========== 球拍推荐 ==========",
            f"玩家画像: {profile.level} | {profile.play_style} | 预算{profile.budget}元 | {profile.gender}",
            "-" * 35,
        ]
        for i, r in enumerate(recs, 1):
            lines.append(f"推荐 {i}: {r['name']}")
            lines.append(f"  品牌: {r['brand']} | 重量: {r['weight']} | 平衡: {r['balance']}")
            lines.append(f"  价格: {r['price_range']}元 | 适合: {r['suitable_for']}")
            lines.append(f"  匹配分: {r['match_score']} | 理由: {'、'.join(r['match_reasons'])}")
            if r.get('tips'):
                lines.append(f"  小贴士: {r['tips']}")
            lines.append("")
        lines.append("=" * 35)
        return "\n".join(lines)
