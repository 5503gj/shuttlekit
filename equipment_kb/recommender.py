"""
器材推荐模块（统一三类装备：球拍 / 鞋 / 球）

设计要点：
- 数据来源 equipment.json（结构化、标注来源），非实时爬取
- 推荐逻辑：水平 + 预算 + 打法 三维匹配，输出匹配分与理由
- 为 AI 层预留 to_prompt_context() 接口，便于 LLM 读取装备库做自然语言推荐
- 兼容两套调用方：
  * agent/workflow.py   -> PlayerProfile(无 category，跨类推荐) / recommend(profile, top_k=) /
                          to_prompt_context(profile, top_k=)
  * equipment_kb/ai_advisor.py -> UserProfile(category 必填) / recommend(profile, top_k=) /
                          to_prompt_context(category:str) / format_recommendation / get_stats
- 容错：真实爬取的装备（intobadminton）价格/规格常为 null，所有用到数值的地方都做 None 保护。
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union

# ── 用户画像 ──────────────────────────────────
@dataclass
class PlayerProfile:
    """通用用户画像（agent 工作流用，可不指定 category，跨类推荐）。"""
    level: str = "中级"          # 新手 / 入门 / 中级 / 高级
    budget: float = 800.0        # 预算（元）
    play_style: str = "全面"      # 进攻 / 速度 / 全面 / 双打前场 / 比赛 / 训练 / 娱乐 ...
    gender: str = "不限"          # 性别（影响球拍重量偏好）
    category: Optional[str] = None  # racket / shoe / shuttlecock，留空=跨类推荐


@dataclass
class UserProfile:
    """带分类的用户画像（ai_advisor 用，category 必填）。"""
    category: str = "racket"      # racket / shoe / shuttlecock
    level: str = "中级"
    budget: float = 800.0
    play_style: str = "全面"
    gender: str = "男"


@dataclass
class Recommendation:
    """单条推荐结果（携带匹配分与理由，供工作流序列化）。"""
    item: Dict
    score: float
    reasons: List[str] = field(default_factory=list)


# 水平等级映射（数值越大越高级）
LEVEL_MAP = {"入门": 0, "娱乐": 0, "新手": 0, "初中级": 1, "初级": 1,
             "中级": 2, "进阶": 2, "高级": 3, "专业": 3, "资深": 3, "中高级": 3}

# 用户口语 -> 库内标准水平词
LEVEL_ALIAS = {
    "新手": "入门", "初学者": "入门", "入门": "入门", "业余": "中级",
    "中级": "中级", "进阶": "中级", "高级": "高级", "专业": "高级", "资深": "高级",
}


class EquipmentRecommender:
    """统一装备推荐器"""

    def __init__(self, equipment_path: Optional[str] = None):
        if equipment_path is None:
            equipment_path = os.path.join(os.path.dirname(__file__), "equipment.json")
        with open(equipment_path, 'r', encoding='utf-8') as f:
            self.equipment: List[Dict] = json.load(f)

    # ── 工具 ──────────────────────────────────
    @staticmethod
    def _norm_level(level: Optional[str]) -> str:
        if not level:
            return "中级"
        return LEVEL_ALIAS.get(level.strip(), level.strip())

    # ── 数据查询 ──────────────────────────────
    def get_by_category(self, category: str) -> List[Dict]:
        return [e for e in self.equipment if e.get("category") == category]

    def get_stats(self) -> Dict:
        """统计装备库覆盖情况（用于产品展示），对 None 价格做保护。"""
        stats: Dict = {}
        for e in self.equipment:
            c = e.get("category")
            if c not in stats:
                stats[c] = {"count": 0, "brands": set()}
            stats[c]["count"] += 1
            if e.get("brand"):
                stats[c]["brands"].add(e["brand"])
        for c in stats:
            stats[c]["brands"] = sorted(stats[c]["brands"])
        return stats

    # ── 核心推荐 ──────────────────────────────
    def recommend(self, profile: Union[PlayerProfile, UserProfile], top_k: int = 5) -> List[Recommendation]:
        """
        按用户画像推荐装备。
        - profile 带 category -> 仅该类；category 为空/未知 -> 跨类（用于通用顾问）。
        """
        cat = getattr(profile, "category", None)
        if cat:
            items = self.get_by_category(cat)
            if not items:            # 未知分类回退到全部，避免空结果
                items = self.equipment
        else:
            items = self.equipment

        scored = []
        for item in items:
            score, reasons = self._score(item, profile)
            scored.append((score, reasons, item))

        # 先按分数，再按评分（None 视为 0）
        scored.sort(key=lambda x: (x[0], (x[2].get("rating") or 0)), reverse=True)
        return [Recommendation(item=it, score=s, reasons=r) for s, r, it in scored[:top_k]]

    def _score(self, item: Dict, profile) -> tuple:
        """三维匹配打分：水平 + 预算 + 打法（+ 评分加权）。对 None 价格/评分容错。"""
        score = 0.0
        reasons: List[str] = []

        # 1. 水平匹配（取 item 各水平与用户水平最小差距）
        player_lvl = LEVEL_MAP.get(self._norm_level(getattr(profile, "level", None)), 2)
        item_lvls = item.get("levels") or []
        best_diff = None
        for lv in item_lvls:
            diff = abs(LEVEL_MAP.get(lv, 2) - player_lvl)
            if best_diff is None or diff < best_diff:
                best_diff = diff
        if best_diff == 0:
            score += 30
            reasons.append("水平匹配")
        elif best_diff == 1:
            score += 15
            reasons.append("水平相近")

        # 2. 预算匹配（价格区间为空时跳过，不做惩罚）
        pmin = item.get("price_min")
        pmax = item.get("price_max")
        budget = getattr(profile, "budget", None)
        if pmin is not None and pmax is not None and budget is not None:
            if pmin <= budget <= pmax:
                score += 30
                reasons.append("价格在预算内")
            elif budget >= pmax:
                score += 12
                reasons.append("预算充足，可上探更高端")
            elif budget < pmin:
                score -= 15
                reasons.append("超预算，需加钱")

        # 3. 打法匹配
        pstyle = getattr(profile, "play_style", None) or ""
        if pstyle and pstyle in (item.get("play_styles") or []):
            score += 25
            reasons.append(f"打法匹配（{pstyle}）")

        # 4. 评分加成（大众评价，None 视为 0）
        try:
            score += float(item.get("rating") or 0) * 2
        except (TypeError, ValueError):
            pass

        return max(score, 0.0), reasons

    # ── 输出格式化 ────────────────────────────
    @staticmethod
    def _price_str(item: Dict) -> str:
        pmin = item.get("price_min")
        pmax = item.get("price_max")
        if pmin is not None and pmax is not None:
            return f"{pmin}-{pmax}元"
        return "价格未知（以实际渠道为准）"

    def format_recommendation(self, profile, top_k: int = 3) -> str:
        cat_name = {"racket": "球拍", "shoe": "球鞋", "shuttlecock": "羽毛球"}.get(
            getattr(profile, "category", None), "装备")
        recs = self.recommend(profile, top_k)
        lines = [
            f"========== {cat_name}推荐 ==========",
            f"用户画像: {getattr(profile, 'level', '')} | {getattr(profile, 'play_style', '')} "
            f"| 预算{getattr(profile, 'budget', '')}元 | {getattr(profile, 'gender', '')}",
            "-" * 40,
        ]
        if not recs:
            lines.append("当前样本库暂无完全匹配项，建议放宽预算或打法条件后重试。")
            return "\n".join(lines)
        for i, r in enumerate(recs, 1):
            it = r.item
            specs = "、".join(f"{k}:{v}" for k, v in (it.get("specs") or {}).items())
            lines.append(f"推荐 {i}: {it.get('brand')} {it.get('model')}")
            if specs:
                lines.append(f"  参数: {specs}")
            lines.append(f"  价格: {self._price_str(it)} | 评分: {it.get('rating')}")
            lines.append(f"  匹配分: {r.score:.0f} | 理由: {'、'.join(r.reasons) if r.reasons else '综合匹配'}")
            if it.get("review_summary"):
                lines.append(f"  评价: {it['review_summary']}")
            lines.append("")
        lines.append("=" * 40)
        return "\n".join(lines)

    # ── AI 层接口 ──────────────────────────────
    def to_prompt_context(self, profile=None, top_k: int = 5) -> str:
        """
        把装备库转成文本，供 LLM 作为上下文做自然语言推荐。
        兼容两种调用：
          to_prompt_context("racket")          -> 该分类全部
          to_prompt_context(profile)           -> 该画像的推荐结果（优先）
          to_prompt_context()                  -> 全库
        """
        if isinstance(profile, str):
            items = self.get_by_category(profile)
        elif profile is None:
            items = self.equipment
        else:
            recs = self.recommend(profile, top_k=top_k)
            items = [r.item for r in recs]
            if not items:
                items = self.equipment

        ctx = "羽毛球装备库（结构化数据，含品牌/型号/价格/参数/打法/评分/评价）：\n"
        for e in items:
            specs = "、".join(f"{k}:{v}" for k, v in (e.get("specs") or {}).items())
            ctx += (
                f"[{e.get('category')}] {e.get('brand')} {e.get('model')} | "
                f"价格{self._price_str(e)} | "
                f"水平{'/'.join(e.get('levels') or [])} | "
                f"打法{'/'.join(e.get('play_styles') or [])} | "
                f"评分{e.get('rating')} | 参数{specs} | 评价：{e.get('review_summary', '')}\n"
            )
        return ctx


if __name__ == "__main__":
    rec = EquipmentRecommender()
    print("装备库统计:")
    for c, s in rec.get_stats().items():
        name = {"racket": "球拍", "shoe": "球鞋", "shuttlecock": "羽毛球"}.get(c, c)
        print(f"  {name}: {s['count']} 款，品牌 {len(s['brands'])} 个（{', '.join(s['brands'])}）")
    print("\n--- 跨类顾问示例（中级 / 1000元 / 进攻）---")
    print(rec.format_recommendation(PlayerProfile(level="中级", budget=1000, play_style="进攻")))
