from backend.utils.ai import normalize_ai_recommendation_tags


def test_childcare_tag_does_not_add_cleaning():
    assert normalize_ai_recommendation_tags(["childcare"], "childcare") == [
        "childcare"
    ]


def test_tag_alias_maps_to_its_standard_tag():
    assert normalize_ai_recommendation_tags(["nanny"], "I need a nanny") == [
        "childcare"
    ]


def test_query_can_supply_tag_when_model_returns_none():
    assert normalize_ai_recommendation_tags([], "I need childcare") == ["childcare"]
