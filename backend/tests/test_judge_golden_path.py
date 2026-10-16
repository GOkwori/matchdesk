"""Judge golden-path fixture regression: verified facts without live authority."""

import json

from matchdesk.domain.judge_golden_path import build_judge_golden_path


def test_golden_path_is_deterministic_and_truthful() -> None:
    """Rebuilding the same fixture must not change its evidence-bound contract."""
    first = build_judge_golden_path()
    again = build_judge_golden_path()
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert first["mode"] == "synthetic_local_read_only"
    assert first["source_events"]
    assert first["detected_moments"]
    assert first["registered_metric"]["observed"] == 1.0
    assert first["verified_claim"]["status"] == "verified"
    assert first["controlled_error"]["status"] == "needs_revision"
    assert first["controlled_error"]["published"] is False


def test_all_nine_scripted_variants_remain_unreviewed() -> None:
    """Language and persona variation cannot acquire producer authority."""
    data = build_judge_golden_path()
    variants = data["audience_variants"]
    assert len(variants) == 9
    assert len({(v["language"], v["persona"]) for v in variants}) == 9
    assert all(v["semantic_language_review"] == "NOT_RUN" for v in variants)
    assert all(v["publishable"] is False for v in variants)
    assert all(v["evidence_digest"] == data["verified_claim"]["evidence_digest"] for v in variants)
    assert data["producer_review"]["authenticated"] is False
    assert data["producer_review"]["approval_enabled"] is False
    assert data["real_publication"] is False
    assert data["live_model_executed"] is False
