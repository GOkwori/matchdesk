"""Publication outbox, destinations and the language-review gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_review import record_decision, record_reverification, start_review
from matchdesk.domain.publication import (
    DeliveryError,
    FileFeedDestination,
    InMemoryOutbox,
    LanguageReview,
    OutboxEntry,
    PermanentDeliveryError,
    PublicationDisabled,
    PublicationSettings,
    deliver,
    publication_id,
    queue_publication,
)
from matchdesk.domain.publication_gate import PublicationAuthorization, authorize_publication

ON = PublicationSettings(enabled=True, max_attempts=3)


def _binding(
    language: str = "en", persona: str = "casual_fan", content: str = "c"
) -> ApprovalBinding:
    """One approved story version."""
    return ApprovalBinding(
        item_id="D-031",
        item_version=4,
        replay_id="replay-1",
        content_digest=content * 64,
        evidence_digest="e" * 64,
        language=language,
        persona=persona,
    )


def _authorized(
    binding: ApprovalBinding, publisher: str = "publisher-1"
) -> PublicationAuthorization:
    """A real producer approval, then the publication gate."""
    state = start_review(binding, actor_id="producer-1")
    state = record_reverification(state, binding, actor_id="producer-1")
    state = record_decision(
        state, binding, actor_id="producer-1", decision="approve", reason="Checked"
    )
    return authorize_publication(state, binding, publisher_actor_id=publisher)


def _review(binding: ApprovalBinding, verdict: str = "approved") -> LanguageReview:
    """A native speaker's verdict on exactly this content."""
    return LanguageReview(
        content_digest=binding.content_digest,
        language=binding.language,
        verdict=verdict,
        reviewer_actor_id="reviewer-es",
    )


def test_publication_is_off_unless_the_host_turns_it_on() -> None:
    """The default settings refuse to queue anything."""
    with pytest.raises(PublicationDisabled):
        queue_publication(
            _authorized(_binding()), ("match_centre",), settings=PublicationSettings()
        )


def test_english_content_queues_one_entry_per_destination_with_stable_ids() -> None:
    """Queueing the same approval twice yields the same IDs, so it can never post twice."""
    binding = _binding()
    first = queue_publication(_authorized(binding), ("match_centre", "social"), settings=ON)
    second = queue_publication(_authorized(binding), ("match_centre", "social"), settings=ON)
    assert [e.publication_id for e in first] == [e.publication_id for e in second]
    assert len({e.publication_id for e in first}) == 2
    assert all(e.status == "queued" and e.reviewer_actor_id is None for e in first)
    outbox = InMemoryOutbox()
    outbox.enqueue(first)
    outbox.enqueue(second)
    assert len(outbox.pending()) == 2


def test_spanish_and_french_need_an_approving_review_of_the_exact_content() -> None:
    """No review, a review of other content, or a request for changes: all refused."""
    for language in ("es", "fr"):
        binding = _binding(language)
        authorization = _authorized(binding)
        with pytest.raises(PermissionError, match="language review"):
            queue_publication(authorization, ("match_centre",), settings=ON)
        other = _review(_binding(language, content="d"))
        with pytest.raises(PermissionError, match="language review"):
            queue_publication(authorization, ("match_centre",), reviews=(other,), settings=ON)
        with pytest.raises(PermissionError, match="asked for changes"):
            queue_publication(
                authorization,
                ("match_centre",),
                reviews=(_review(binding, "changes_requested"),),
                settings=ON,
            )
        approved = queue_publication(
            authorization, ("match_centre",), reviews=(_review(binding),), settings=ON
        )
        assert approved[0].reviewer_actor_id == "reviewer-es"


def test_the_latest_review_decides() -> None:
    """An approval followed by a request for changes blocks publication again."""
    binding = _binding("es")
    reviews = (_review(binding), _review(binding, "changes_requested"))
    with pytest.raises(PermissionError, match="asked for changes"):
        queue_publication(_authorized(binding), ("match_centre",), reviews=reviews, settings=ON)


def test_destinations_only_take_the_personas_they_show() -> None:
    """A broadcast caption goes to the overlay, not to the match centre."""
    caption = _authorized(_binding(persona="broadcast_caption"))
    with pytest.raises(PermissionError, match="does not show"):
        queue_publication(caption, ("match_centre",), settings=ON)
    assert (
        queue_publication(caption, ("broadcast_overlay",), settings=ON)[0].destination
        == "broadcast_overlay"
    )
    with pytest.raises(ValueError, match="Unknown destination"):
        queue_publication(caption, ("billboard",), settings=ON)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="once"):
        queue_publication(caption, ("broadcast_overlay", "broadcast_overlay"), settings=ON)


def test_the_publisher_must_be_a_second_person() -> None:
    """The producer who approved cannot also release it."""
    with pytest.raises(PermissionError, match="must not be the producer"):
        queue_publication(_authorized(_binding(), publisher="producer-1"), ("social",), settings=ON)


class _Flaky:
    """A destination that fails a set number of times, then accepts."""

    name = "social"

    def __init__(self, failures: int, permanent: bool = False):
        """Fail this many times."""
        self.failures = failures
        self.permanent = permanent
        self.sent: list[str] = []

    def deliver(self, publication_id: str, payload):
        """Fail or accept."""
        if self.failures:
            self.failures -= 1
            raise (PermanentDeliveryError if self.permanent else DeliveryError)("rate limited")
        self.sent.append(publication_id)
        return "receipt-1"


def _entry() -> OutboxEntry:
    """One queued social post."""
    return queue_publication(_authorized(_binding()), ("social",), settings=ON)[0]


def test_transient_failures_retry_then_deliver_exactly_once() -> None:
    """Two failures, then success; a further attempt sends nothing."""
    destination = _Flaky(failures=2)
    entry = _entry()
    for _ in range(2):
        entry = deliver(entry, destination, {"text": "Okafor scores"}, settings=ON)
        assert entry.status == "failed" and entry.last_error == "rate limited"
    entry = deliver(entry, destination, {"text": "Okafor scores"}, settings=ON)
    assert (entry.status, entry.attempts, entry.receipt) == ("delivered", 3, "receipt-1")
    again = deliver(entry, destination, {"text": "Okafor scores"}, settings=ON)
    assert again is entry and destination.sent == [entry.publication_id]


def test_retries_are_bounded_and_permanent_failures_stop_at_once() -> None:
    """Out of attempts, or refused outright: the entry is abandoned for a person to check."""
    entry = _entry()
    always = _Flaky(failures=99)
    for _ in range(3):
        entry = deliver(entry, always, {}, settings=ON)
    assert (entry.status, entry.attempts) == ("abandoned", 3)
    assert deliver(entry, always, {}, settings=ON) is entry
    refused = deliver(_entry(), _Flaky(failures=1, permanent=True), {}, settings=ON)
    assert (refused.status, refused.attempts) == ("abandoned", 1)


def test_delivery_stops_when_publication_is_switched_off() -> None:
    """Turning the switch off halts the outbox too."""
    with pytest.raises(PublicationDisabled):
        deliver(_entry(), _Flaky(0), {}, settings=PublicationSettings())


def test_the_outbox_never_moves_a_delivered_entry_backwards() -> None:
    """Once delivered, always delivered."""
    outbox = InMemoryOutbox()
    entry = outbox.enqueue((_entry(),))[0]
    done = deliver(entry, _Flaky(0), {}, settings=ON)
    outbox.record(done)
    assert outbox.pending() == ()
    from dataclasses import replace

    with pytest.raises(ValueError, match="cannot change"):
        outbox.record(replace(done, status="failed"))


def test_the_file_feed_writes_each_publication_once(tmp_path: Path) -> None:
    """Same payload again returns the same receipt; a different payload under the ID is refused."""
    feed = FileFeedDestination("match_centre", tmp_path / "feed")
    pid = publication_id(_binding(), "match_centre")
    receipt = feed.deliver(pid, {"headline": "58′ Goal for Northbridge FC"})
    assert json.loads((tmp_path / "feed" / f"{pid}.json").read_text())["headline"].startswith("58")
    assert feed.deliver(pid, {"headline": "58′ Goal for Northbridge FC"}) == receipt
    with pytest.raises(PermanentDeliveryError, match="different payload"):
        feed.deliver(pid, {"headline": "Something else"})
    assert not [p for p in (tmp_path / "feed").iterdir() if p.name.startswith(".pending-")]


def test_language_reviews_must_be_well_formed() -> None:
    """A reviewer is required, and the digest must be a SHA-256."""
    with pytest.raises(ValueError, match="reviewer"):
        LanguageReview(
            content_digest="a" * 64, language="es", verdict="approved", reviewer_actor_id=" "
        )
    with pytest.raises(ValueError, match="SHA-256"):
        LanguageReview(
            content_digest="xyz", language="es", verdict="approved", reviewer_actor_id="r"
        )
    with pytest.raises(ValueError, match="max_attempts"):
        PublicationSettings(enabled=True, max_attempts=0)
