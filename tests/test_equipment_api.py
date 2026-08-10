from speed_api import EquipmentRecommendPayload, equipment_recommend, equipment_stats


def test_equipment_stats_exposes_source_policy():
    result = equipment_stats()
    assert result["total"] > 0
    assert "非实时爬取" in result["data_policy"]


def test_equipment_recommend_returns_provenance():
    result = equipment_recommend(EquipmentRecommendPayload(
        category="racket", level="中级", budget=1000, play_style="进攻", top_k=3,
    ))
    assert result["count"] == 3
    assert all(item["item"]["source"] for item in result["results"])
    assert all("score" in item and "reasons" in item for item in result["results"])
