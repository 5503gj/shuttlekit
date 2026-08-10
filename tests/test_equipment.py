"""装备推荐模块测试：覆盖正常、边界、异常场景

对应重构后的统一 API：
- recommend(profile, top_k=) 返回 Recommendation 列表（.item / .score / .reasons）
- to_prompt_context(profile | category:str) 返回文本
- 对真实爬取的 None 价格/评分做容错
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from equipment_kb.recommender import (
    EquipmentRecommender, UserProfile, PlayerProfile, LEVEL_MAP,
)


def test_load_data():
    """数据能正常加载，且三类都有"""
    rec = EquipmentRecommender()
    assert len(rec.equipment) > 10
    cats = {e["category"] for e in rec.equipment}
    assert {"racket", "shoe", "shuttlecock"}.issubset(cats)


def test_stats():
    """统计接口返回品牌（价格 None 已做保护）"""
    rec = EquipmentRecommender()
    stats = rec.get_stats()
    assert stats["racket"]["count"] >= 5
    assert len(stats["racket"]["brands"]) >= 3


def test_recommend_racket_normal():
    """正常场景：中级进攻男，预算1000"""
    rec = EquipmentRecommender()
    p = UserProfile("racket", "中级", 1000, "进攻", "男")
    res = rec.recommend(p, top_k=3)
    assert len(res) == 3
    assert res[0].score >= 0
    assert res[0].reasons  # 非空理由列表


def test_recommend_budget_boundary():
    """边界：预算为0（极低）不应崩溃"""
    rec = EquipmentRecommender()
    p = UserProfile("racket", "入门", 0, "娱乐", "男")
    res = rec.recommend(p, top_k=3)
    assert len(res) == 3
    # 超预算的应有相应理由
    assert any("超预算" in "、".join(r.reasons) for r in res)


def test_recommend_shoe():
    """球鞋类推荐正常"""
    rec = EquipmentRecommender()
    p = UserProfile("shoe", "入门", 400, "速度", "女")
    res = rec.recommend(p, top_k=2)
    assert len(res) == 2
    assert all(r.item["category"] == "shoe" for r in res)


def test_recommend_shuttlecock():
    """羽毛球类推荐正常"""
    rec = EquipmentRecommender()
    p = UserProfile("shuttlecock", "高级", 250, "比赛", "男")
    res = rec.recommend(p, top_k=2)
    assert len(res) == 2
    assert all(r.item["category"] == "shuttlecock" for r in res)


def test_recommend_cross_category():
    """PlayerProfile 不指定 category 时跨类推荐"""
    rec = EquipmentRecommender()
    p = PlayerProfile(level="中级", budget=1000, play_style="进攻")
    res = rec.recommend(p, top_k=5)
    assert len(res) == 5


def test_play_style_match():
    """打法匹配：进攻型应命中打法匹配"""
    rec = EquipmentRecommender()
    p = UserProfile("racket", "中级", 1500, "进攻", "男")
    res = rec.recommend(p, top_k=3)
    assert any("打法匹配" in "、".join(r.reasons) for r in res)


def test_prompt_context():
    """AI 接口：装备库能转成 prompt 上下文（分类字符串）"""
    rec = EquipmentRecommender()
    ctx = rec.to_prompt_context("racket")
    assert "YONEX" in ctx
    assert "评分" in ctx


def test_prompt_context_from_profile():
    """AI 接口：传入 profile 对象也能生成上下文"""
    rec = EquipmentRecommender()
    p = UserProfile("racket", "中级", 1000, "进攻", "男")
    ctx = rec.to_prompt_context(p, top_k=3)
    assert "YONEX" in ctx


def test_none_price_tolerance():
    """真实爬取数据价格为 None 时不应崩溃，且仍能返回结果"""
    rec = EquipmentRecommender()
    p = UserProfile("racket", "中级", 1500, "进攻", "男")
    res = rec.recommend(p, top_k=5)
    assert len(res) == 5


def test_level_map():
    """水平映射完整"""
    for lv in ["入门", "初中级", "中级", "高级"]:
        assert lv in LEVEL_MAP


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n结果: {passed} 通过 / {failed} 失败")
