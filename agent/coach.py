"""A deterministic badminton coach Agent.

It routes a natural-language request to existing local tools: equipment
retrieval, session summary, or a conservative training suggestion. No database
or external model is required; the returned trace makes the workflow easy to
inspect and replace with an LLM later.
"""

from __future__ import annotations

import uuid

from equipment_kb.recommender import EquipmentRecommender, PlayerProfile


def run_coach(message: str, profile: dict | None = None, session: dict | None = None) -> dict:
    text = (message or "").strip()
    profile = profile or {}
    session = session or {}
    lowered = text.lower()
    if any(word in text for word in ("球拍", "球鞋", "羽毛球", "装备", "预算", "推荐")):
        intent = "equipment_recommendation"
        tool = "equipment_catalog_and_ranker"
        player = PlayerProfile(
            level=profile.get("level", "中级"),
            budget=float(profile.get("budget", 800)),
            play_style=profile.get("play_style", "全面"),
            gender=profile.get("gender", "不限"),
            category=profile.get("category"),
        )
        matches = EquipmentRecommender().recommend(player, top_k=3)
        answer = "我根据水平、预算和打法筛了 3 个候选，建议优先结合实际试打感受确认。"
        result = [{"score": round(item.score, 1), "reasons": item.reasons,
                   "brand": item.item.get("brand"), "model": item.item.get("model")}
                  for item in matches]
    elif any(word in text for word in ("球速", "训练", "状态", "这场", "数据")):
        intent = "training_feedback"
        tool = "session_snapshot"
        peak = float(session.get("peak_speed_kmh", 0) or 0)
        average = float(session.get("average_speed_kmh", 0) or 0)
        sample_count = int(session.get("sample_count", 0) or 0)
        answer = (f"当前会话有 {sample_count} 个有效样本，峰值 {peak:.1f} km/h、"
                  f"平均 {average:.1f} km/h。建议先补充稳定样本，再比较不同训练组。")
        result = {"peak_speed_kmh": peak, "average_speed_kmh": average,
                  "sample_count": sample_count}
    else:
        intent = "clarify_goal"
        tool = "safe_clarification"
        answer = "你可以问我三类问题：装备推荐、训练数据解读，或当前会话的球速表现。"
        result = {"supported_intents": ["equipment_recommendation", "training_feedback"]}

    return {
        "trace_id": f"shuttle-{uuid.uuid4().hex[:10]}",
        "intent": intent,
        "steps": ["classify_intent", "select_tool", "execute_local_tool", "compose_feedback"],
        "tool": tool,
        "answer": answer,
        "result": result,
        "guardrails": ["local_data_only", "no_medical_claims", "recommendation_is_not_purchase_advice"],
    }
