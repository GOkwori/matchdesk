"""Phase 2: the match digest fits a specialist's context and holds only computed numbers."""

import pytest
from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS
from matchdesk.domain.match_digest import MAX_DIGEST_CHARS, build_match_digest, digest_json
from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import MatchWindow, Subject

LOG = canonical.generate_canonical_match()


def test_digest_fits_the_context_and_matches_the_registered_metrics() -> None:
    """Every number equals a registered formula over the same events."""
    digest = build_match_digest(LOG, DISPLAY_NAMES, to_ms=REPLAY_END_MS)
    assert len(digest_json(digest)) <= MAX_DIGEST_CHARS
    assert digest["score"] == {"nbr": 2, "riv": 1}
    assert digest["replay_clock"] == "67:12" and digest["event_count"] == 1421
    whole = MatchWindow(from_ms=0, to_ms=REPLAY_END_MS)
    share = compute_metric("possession_time.v1", LOG, Subject(team_id="nbr"), whole)
    assert digest["metrics_whole_match"]["nbr"]["possession_time.v1"] == round(share, 4)


def test_digest_names_the_goal_sequence_the_story_is_about() -> None:
    """The corner before Okafor's header is in the digest as a key event."""
    digest = build_match_digest(LOG, DISPLAY_NAMES, to_ms=REPLAY_END_MS)
    rows = {row["event_id"]: row for row in digest["key_events"]}
    assert rows["E-1366"]["player"] == "Okafor" and rows["E-1366"]["clock"] == "58:17"
    assert rows["E-1359"]["tags"] == ["corner"]


def test_digest_respects_the_replay_point() -> None:
    """At 40:00 only the first goal has happened."""
    digest = build_match_digest(LOG, DISPLAY_NAMES, to_ms=canonical.clock_ms(40, 0))
    assert digest["score"] == {"nbr": 1, "riv": 0}


def test_digest_needs_events() -> None:
    """There is nothing to summarise before kick-off."""
    with pytest.raises(ValueError, match="at least one accepted event"):
        build_match_digest(LOG, DISPLAY_NAMES, to_ms=0)
