# equipment_kb - 器材知识库

根据玩家水平、预算、打法推荐合适的羽毛球装备。

## 功能

1. **球拍推荐**：按水平/预算/打法匹配，给出匹配分和理由
2. **参数知识**：重量、平衡点、中杆硬度的含义和选择指南
3. **新手避坑**：常见选购误区提示

## 用法

```python
from equipment_kb import EquipmentRecommender, PlayerProfile

# 描述你的情况
profile = PlayerProfile(
    level="中级",
    budget=800,
    play_style="进攻",
    gender="男"
)

# 获取推荐
recommender = EquipmentRecommender()
print(recommender.format_recommendation(profile))
```

## 球拍参数说明

| 参数 | 含义 | 选择建议 |
|------|------|---------|
| 重量 | 2U>3U>4U>5U | 新手选4U或5U，女性选5U |
| 平衡点 | 头重/平衡/头轻 | 进攻选头重，前场快攻选头轻 |
| 中杆硬度 | 硬/适中/软 | 新手选中杆适中或偏软，力量足选偏硬 |
| 握把粗细 | G4/G5/G6 | 手小选G6细，手大选G4 |

## 新手避坑

1. 不要盲目追求贵拍，300-500 的入门碳纤维拍足够
2. 先确定打法再选拍，别"看哪个帅买哪个"
3. 球线比球拍更影响手感，建议用 BG65 或 BG65Ti 入门
4. 球鞋比球拍更重要，专业羽毛球鞋防滑防扭伤，别穿跑鞋打
