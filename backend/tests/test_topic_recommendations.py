import json

import pytest

from content_ops.topic_recommendations import parse_recommendations


def test_recommendation_parser_rejects_unknown_material_ids():
    response = json.dumps(
        {
            "topics": [
                {
                    "title": "Unsupported claim",
                    "rationale": "Uses a material that was not supplied",
                    "material_ids": ["unknown"],
                    "score": 95,
                    "scores": {},
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="usable topic recommendations"):
        parse_recommendations(response, {"known"}, 4)


def test_recommendation_parser_clamps_scores_and_deduplicates_materials():
    response = json.dumps(
        {
            "topics": [
                {
                    "title": "Grounded topic",
                    "rationale": "Backed by the supplied material",
                    "material_ids": ["known", "known"],
                    "score": 120,
                    "scores": {
                        "heat": 110,
                        "timeliness": -2,
                        "reader_value": 80,
                        "strategy_fit": 90,
                    },
                }
            ]
        }
    )

    recommendation = parse_recommendations(response, {"known"}, 4)[0]

    assert recommendation["material_ids"] == ["known"]
    assert recommendation["score"] == 100
    assert recommendation["scores"]["heat"] == 100
    assert recommendation["scores"]["timeliness"] == 0


def test_recommendation_parser_uses_custom_relative_weights_for_total_score():
    response = json.dumps(
        {
            "topics": [
                {
                    "title": "Reader-first topic",
                    "rationale": "Useful to the intended audience",
                    "material_ids": ["known"],
                    "score": 99,
                    "scores": {"heat": 100, "timeliness": 0, "reader_value": 80, "strategy_fit": 40},
                }
            ]
        }
    )

    recommendation = parse_recommendations(
        response,
        {"known"},
        4,
        {"heat": 0, "timeliness": 0, "reader_value": 75, "strategy_fit": 25},
    )[0]

    assert recommendation["score"] == 70
