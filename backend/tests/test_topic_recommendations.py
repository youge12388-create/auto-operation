import json

import pytest

from content_ops.models import Job, ModelConfig, Source, SourceItem, Strategy
from content_ops.providers import CompletionResponse
from content_ops.topic_recommendations import parse_recommendations, recommend_topics


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


def test_recommend_topics_uses_the_production_token_budget(db):
    class CapturingProvider:
        request = None

        def complete(self, request):
            self.request = request
            material_id = json.loads(request.user)["materials"][0]["id"]
            return CompletionResponse(
                text=json.dumps(
                    {
                        "topics": [
                            {
                                "title": "有依据的选题",
                                "rationale": "来自已验证素材",
                                "material_ids": [material_id],
                                "score": 90,
                                "scores": {"heat": 90, "timeliness": 90, "reader_value": 90, "strategy_fit": 90},
                            }
                        ]
                    }
                )
            )

    source = Source(name="topic budget source", source_type="manual", url="")
    strategy = Strategy(name="topic budget strategy", objective="Select grounded topics")
    model = ModelConfig(provider="fake", name="topic budget model", enabled=True)
    db.add_all([source, strategy, model])
    db.flush()
    job = Job(strategy_id=strategy.id, idempotency_key="topic-budget-job")
    item = SourceItem(
        source_id=source.id,
        title="Verified topic material",
        url="",
        canonical_url="manual://topic-budget-item",
        content="Material used to verify the production recommendation request budget.",
        content_hash="d" * 64,
        status="verified",
        triage_status="inbox",
    )
    db.add_all([job, item])
    db.flush()

    provider = CapturingProvider()
    topics = recommend_topics(db, job, strategy, [item], provider, model)

    assert topics
    assert provider.request is not None
    assert provider.request.max_tokens == 3200
