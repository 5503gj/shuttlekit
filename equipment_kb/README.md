# 器材知识库与推荐模块（装备智能推荐核心）

> 把 ShuttleKit 从「技术工具箱」升级为「装备推荐产品」的核心模块。

## 功能

- **三类装备统一数据**：球拍 / 球鞋 / 羽毛球
- **结构化数据集** `equipment.json`：品牌、型号、价格、参数、打法适配、大众评分、评价摘要、来源标注
- **规则推荐引擎**：按 水平 + 预算 + 打法 三维匹配，输出匹配分与理由
- **AI 顾问接口** `ai_advisor.py`：调用 LLM 生成自然语言推荐（无 Key 自动回退规则引擎）

## 数据规模（当前版本）

| 类别 | 款数 | 品牌 |
|------|------|------|
| 球拍 | 7 | YONEX / VICTOR / LI-NING / KAWASAKI |
| 球鞋 | 5 | YONEX / VICTOR / LI-NING / ASICS |
| 羽毛球 | 4 | YONEX / VICTOR / LI-NING |

> 数据来源：品牌官网规格 + 中羽在线等公开评测**整理**，非实时爬取。
> 标注为「样本库」，覆盖头部品牌（约占市面 80% 销量），后续将持续扩充。

## 快速使用

```python
from equipment_kb.recommender import EquipmentRecommender, UserProfile

rec = EquipmentRecommender()
profile = UserProfile("racket", "中级", 1000, "进攻", "男")
print(rec.format_recommendation(profile))

# AI 自然语言推荐（需配置 OPENAI_API_KEY 等）
from equipment_kb.ai_advisor import advise
print(advise(profile))
```

## AI 智能体（下一步）

`ai_advisor.py` 已预留 LLM 接口：装备库通过 `to_prompt_context()` 转为文本上下文，
LLM 据此生成「为什么适合你 + 替代方案」的自然语言建议。可对接：
- OpenAI / 通义千问 / 豆包 等兼容接口（设置环境变量 `OPENAI_API_KEY`、`OPENAI_MODEL`）
- 或 Coze / Dify 无代码搭建对话机器人（拖拽，不用写代码）

## 诚实声明（重要）

本项目**不实时爬取**中羽在线等网站（涉及服务条款与法律风险）。
装备数据由公开评测人工整理并标注来源，作为「样本库」展示推荐逻辑。
若需实时/全量数据，应在获得授权后通过官方 API 或合规渠道获取。
