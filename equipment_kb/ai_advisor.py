"""
AI 装备顾问（智能体骨架）

功能：基于装备库 + 用户画像，调用 LLM 生成「自然语言推荐 + 解释 + 替代方案」。
设计：优先用 LLM（通义/豆包/OpenAI 兼容接口）；无 API Key 时自动回退到规则引擎，
      保证项目在任何环境都能跑、能演示。

使用方式：
  export OPENAI_API_KEY="sk-xxx"   # 可选
  python equipment_kb/ai_advisor.py
"""

import os
import sys
import json

# 兼容中文路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from equipment_kb.recommender import EquipmentRecommender, UserProfile


SYSTEM_PROMPT = """你是一个专业的羽毛球装备顾问。
你的任务是：根据用户画像（水平、预算、打法、性别），从给定的装备库中，
用通俗中文推荐最合适 1-3 件装备，并解释「为什么适合他」，最后给出 1 条替代方案提醒。

要求：
1. 只从提供的装备库中选，不要编造库外型号
2. 解释要结合用户的打法和水平，不说空话
3. 提醒预算与水平的匹配关系
4. 语气像耐心的导购，不是冷冰冰的列表"""


def build_user_message(profile: UserProfile, context: str) -> str:
    cat = {"racket": "球拍", "shoe": "球鞋", "shuttlecock": "羽毛球"}[profile.category]
    return f"""用户想买：{cat}
用户画像：水平 {profile.level}，预算 {profile.budget} 元，主打 {profile.play_style}，性别 {profile.gender}

装备库数据：
{context}

请基于以上数据给出推荐。"""


def recommend_with_llm(profile: UserProfile, api_key: str = None, base_url: str = None) -> str:
    """
    调用 LLM 生成推荐。返回自然语言文本。
    支持任意 OpenAI 兼容接口（OpenAI / 通义千问 / 豆包 等）。
    """
    try:
        from openai import OpenAI
    except ImportError:
        return None  # 没装 openai 库，回退

    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    rec = EquipmentRecommender()
    context = rec.to_prompt_context(profile.category)

    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(profile, context)},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content


def advise(profile: UserProfile) -> str:
    """
    统一入口：有 Key 用 LLM，否则回退规则引擎。
    保证「能跑、能演示、不依赖外部密钥」。
    """
    llm_text = recommend_with_llm(profile)
    if llm_text:
        return "【AI 顾问推荐】\n" + llm_text

    # 回退：规则引擎
    rec = EquipmentRecommender()
    return "【规则引擎推荐（未配置 LLM Key，已自动回退）】\n" + rec.format_recommendation(profile)


def build_user_context(profile, matches: list) -> str:
    """把规则引擎的推荐结果整理成给 LLM 的上下文文本（与 workflow 共用）。"""
    lines = ["基于规则引擎的候选装备："]
    for m in matches:
        item = m.item if hasattr(m, "item") else m
        reasons = m.reasons if hasattr(m, "reasons") else item.get("match_reasons", [])
        score = getattr(m, "score", item.get("match_score", ""))
        lines.append(
            f"- {item.get('brand')} {item.get('model')} | 匹配分 {score} | "
            f"理由：{', '.join(reasons) if reasons else '综合匹配'}"
        )
    return "\n".join(lines)


def fallback_recommendation(profile, matches: list) -> str:
    """无 LLM Key 时的规则引擎回退推荐文本（与 workflow 共用）。"""
    header = ("【规则引擎回退】以下为基于装备库的规则匹配结果"
              "（未调用大模型，建议以实际试打为准）：")
    lines = [header, ""]
    if not matches:
        lines.append("当前样本库暂无完全匹配项，建议放宽预算或打法条件后重试。")
        return "\n".join(lines)
    for i, m in enumerate(matches, 1):
        item = m.item if hasattr(m, "item") else m
        reasons = m.reasons if hasattr(m, "reasons") else item.get("match_reasons", [])
        pmin = item.get("price_min")
        pmax = item.get("price_max")
        price = f"{pmin}-{pmax}元" if (pmin is not None and pmax is not None) else "价格未知"
        lines.append(f"{i}. {item.get('brand')} {item.get('model')}（{price}）")
        lines.append(f"   适配原因: {', '.join(reasons) if reasons else '综合匹配'}")
        if item.get("review_summary"):
            lines.append(f"   评价: {item['review_summary']}")
    return "\n".join(lines)


def demo():
    """演示：三类装备各推荐一次"""
    rec = EquipmentRecommender()
    print("装备库覆盖统计：")
    stats = rec.get_stats()
    for c, s in stats.items():
        name = {"racket": "球拍", "shoe": "球鞋", "shuttlecock": "羽毛球"}[c]
        print(f"  {name}: {s['count']} 款，品牌 {len(s['brands'])} 个（{', '.join(s['brands'])}）")
    print()

    profiles = [
        UserProfile("racket", "中级", 1000, "进攻", "男"),
        UserProfile("shoe", "入门", 400, "速度", "女"),
        UserProfile("shuttlecock", "高级", 250, "比赛", "男"),
    ]
    for p in profiles:
        print(advise(p))
        print()


if __name__ == "__main__":
    demo()
