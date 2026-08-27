from content_ops.material_curation import curate_materials, parse_curation
from content_ops.models import ModelConfig, Source, SourceItem, Strategy
from content_ops.providers import CompletionResponse, FakeProvider


def test_parse_curation_accepts_only_known_material_ids():
    result = parse_curation(
        '{"materials":[{"id":"known","decision":"select","score":91,"reason":"useful"},{"id":"unknown","decision":"select"}]}',
        {"known"},
        12,
    )
    assert result[0]["id"] == "known"
    assert len(result) == 1



def test_parse_curation_accepts_fenced_array_and_normalizes_score():
    result = parse_curation(
        '```json\n[{"material_id":"known","decision":"keep","score":8,"rationale":"useful"}]\n```',
        {"known"},
        12,
    )

    assert result == [{"id": "known", "decision": "select", "score": 80.0, "reason": "useful"}]


def test_curate_materials_moves_selected_items_into_retained_pool(db):
    source = Source(name="curation source", source_type="manual", url="")
    strategy = Strategy(name="curation strategy", objective="Select useful material")
    model = ModelConfig(provider="fake", name="curation model", enabled=True)
    db.add_all([source, strategy, model])
    db.flush()
    item = SourceItem(
        source_id=source.id,
        title="Useful item",
        url="",
        canonical_url="manual://curation-item",
        content="A verified material with enough context for selection.",
        content_hash="a" * 64,
        status="verified",
        triage_status="inbox",
    )
    db.add(item)
    db.flush()

    selected = curate_materials(db, None, strategy, [item], FakeProvider(), model)

    assert selected[0]["id"] == item.id
    assert item.triage_status == "selected"


def test_curate_materials_uses_the_production_token_budget(db):
    class CapturingProvider:
        request = None

        def complete(self, request):
            self.request = request
            return CompletionResponse(
                text='{"materials":[{"id":"material","decision":"select","score":80,"reason":"useful"}]}'
            )

    source = Source(name="budget source", source_type="manual", url="")
    strategy = Strategy(name="budget strategy", objective="Keep enough context")
    model = ModelConfig(provider="fake", name="budget model", enabled=True)
    db.add_all([source, strategy, model])
    db.flush()
    item = SourceItem(
        id="material",
        source_id=source.id,
        title="Longer context item",
        url="",
        canonical_url="manual://budget-item",
        content="verified material",
        content_hash="c" * 64,
        status="verified",
        triage_status="inbox",
    )
    db.add(item)
    db.flush()

    provider = CapturingProvider()
    curate_materials(db, None, strategy, [item], provider, model)

    assert provider.request is not None
    assert provider.request.max_tokens == 6000

def test_curate_materials_falls_back_when_ai_output_is_invalid(db):
    class InvalidCurationProvider:
        def complete(self, _):
            return CompletionResponse(text="not-json")

    source = Source(name="fallback source", source_type="manual", url="")
    strategy = Strategy(name="fallback strategy", objective="Keep automatic workflow moving")
    model = ModelConfig(provider="fake", name="fallback model", enabled=True)
    db.add_all([source, strategy, model])
    db.flush()
    item = SourceItem(
        source_id=source.id,
        title="Fallback item",
        url="",
        canonical_url="manual://fallback-item",
        content="A verified candidate used when AI curation is unavailable.",
        content_hash="b" * 64,
        status="verified",
        triage_status="inbox",
    )
    db.add(item)
    db.flush()

    selected = curate_materials(db, None, strategy, [item], InvalidCurationProvider(), model)

    assert selected[0]["id"] == item.id
    assert selected[0]["reason"].startswith("AI curation unavailable")
    assert item.triage_status == "selected"
