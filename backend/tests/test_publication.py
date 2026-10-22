"""Publication outbox, destinations and the language-review gate."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from matchdesk.domain.broadcast_outputs import ClaimLinkedText, CommentaryPayload
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_review import (
    ProducerReviewState,
    open_revision,
    record_decision,
    record_reverification,
    start_review,
)
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
    revalidate,
)

ON = PublicationSettings(enabled=True, max_attempts=3)


def _payload(text: str = "Okafor scores") -> CommentaryPayload:
    """The approved words themselves."""
    return CommentaryPayload(lines=(ClaimLinkedText(claim_id="claim-1", text=text),))


def _binding(
    language: str = "en", persona: str = "casual_fan", text: str = "Okafor scores"
) -> ApprovalBinding:
    """One story version whose digest is the digest of its payload."""
    return ApprovalBinding(
        item_id="D-031",
        item_version=4,
        replay_id="replay-1",
        content_digest=content_digest(_payload(text)),
        evidence_digest="e" * 64,
        language=language,
        persona=persona,
    )


def _approved(binding: ApprovalBinding, producer: str = "producer-1") -> ProducerReviewState:
    """A real producer approval of exactly this binding."""
    state = start_review(binding, actor_id=producer)
    state = record_reverification(state, binding, actor_id=producer)
    return record_decision(state, binding, actor_id=producer, decision="approve", reason="Checked")


def _queue(binding: ApprovalBinding, destinations=("match_centre",), *, reviews=(), **kw):
    """Queue through the full gate."""
    state = kw.pop("state", None) or _approved(binding)
    return queue_publication(
        state,
        binding,
        destinations,
        publisher_actor_id=kw.pop("publisher", "publisher-1"),
        reviews=reviews,
        settings=kw.pop("settings", ON),
    )


def _review(binding: ApprovalBinding, verdict: str = "approved", sequence: int = 1, **kw):
    """A native speaker's verdict on exactly this content."""
    return LanguageReview(
        sequence=sequence,
        content_digest=binding.content_digest,
        language=binding.language,
        verdict=verdict,
        reviewer_actor_id=kw.get("reviewer", "reviewer-es"),
    )


def test_publication_is_off_unless_the_host_turns_it_on() -> None:
    """The default settings refuse to queue anything."""
    with pytest.raises(PublicationDisabled):
        _queue(_binding(), settings=PublicationSettings())


def test_only_the_currently_approved_version_can_be_queued() -> None:
    """No approval, a different version, or a rejection after approval: all refused."""
    binding = _binding()
    with pytest.raises(PermissionError, match="producer approval"):
        _queue(binding, state=start_review(binding, actor_id="producer-1"))
    with pytest.raises(PermissionError, match="approved current version"):
        _queue(_binding(text="Something nobody approved"), state=_approved(binding))


def test_english_content_queues_one_entry_per_destination_with_stable_ids() -> None:
    """Queueing the same approval twice yields the same IDs, so it can never post twice."""
    binding = _binding()
    first = _queue(binding, ("match_centre", "social"))
    second = _queue(binding, ("match_centre", "social"))
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
        with pytest.raises(PermissionError, match="language review"):
            _queue(binding)
        other = _review(_binding(language, text="Other words"))
        with pytest.raises(PermissionError, match="language review"):
            _queue(binding, reviews=(other,))
        with pytest.raises(PermissionError, match="asked for changes"):
            _queue(binding, reviews=(_review(binding, "changes_requested"),))
        approved = _queue(binding, reviews=(_review(binding),))
        assert approved[0].reviewer_actor_id == "reviewer-es"


def test_the_highest_sequence_review_decides_whatever_the_order() -> None:
    """Order in the tuple does not matter; the sequence number does. Duplicates are refused."""
    binding = _binding("es")
    later_rejection = (_review(binding, "changes_requested", 2), _review(binding, sequence=1))
    with pytest.raises(PermissionError, match="asked for changes"):
        _queue(binding, reviews=later_rejection)
    later_approval = (_review(binding, sequence=3), _review(binding, "changes_requested", 2))
    assert _queue(binding, reviews=later_approval)[0].status == "queued"
    with pytest.raises(ValueError, match="unique"):
        _queue(binding, reviews=(_review(binding), _review(binding, "changes_requested")))


def test_destinations_only_take_the_personas_they_show() -> None:
    """A broadcast caption goes to the overlay, not to the match centre."""
    caption = _binding(persona="broadcast_caption")
    with pytest.raises(PermissionError, match="does not show"):
        _queue(caption, ("match_centre",))
    assert _queue(caption, ("broadcast_overlay",))[0].destination == "broadcast_overlay"
    with pytest.raises(ValueError, match="Unknown destination"):
        _queue(caption, ("billboard",))
    with pytest.raises(ValueError, match="once"):
        _queue(caption, ("broadcast_overlay", "broadcast_overlay"))


@pytest.mark.parametrize("publisher", ["producer-1", "Producer-1", " producer-1 "])
def test_the_publisher_must_be_a_second_person(publisher: str) -> None:
    """The producer who approved cannot also release it, however the ID is spelt."""
    with pytest.raises(PermissionError, match="must not be the producer"):
        _queue(_binding(), ("social",), publisher=publisher)


def test_entries_are_withdrawn_when_approval_or_review_changes() -> None:
    """A newer version, a later language objection or a different reviewer stops delivery."""
    binding = _binding("es")
    state = _approved(binding)
    entry = _queue(binding, reviews=(_review(binding),), state=state)[0]
    assert revalidate(entry, state, (_review(binding),)) is entry
    revised = open_revision(
        state, binding.model_copy(update={"item_version": 5}), actor_id="producer-1"
    )
    assert revalidate(entry, revised, (_review(binding),)).status == "withdrawn"
    objection = (_review(binding), _review(binding, "changes_requested", 2))
    withdrawn = revalidate(entry, state, objection)
    assert (withdrawn.status, withdrawn.last_error) == (
        "withdrawn",
        "The latest language review asked for changes",
    )
    other_reviewer = (_review(binding), _review(binding, sequence=2, reviewer="reviewer-2"))
    assert revalidate(entry, state, other_reviewer).status == "withdrawn"
    assert revalidate(withdrawn, state, (_review(binding),)) is withdrawn
    assert deliver(withdrawn, _Flaky(0), _payload(), settings=ON) is withdrawn


class _Flaky:
    """A destination that fails a set number of times, then accepts."""

    name = "match_centre"

    def __init__(self, failures: int, error: type[BaseException] = DeliveryError):
        """Fail this many times with this error."""
        self.failures = failures
        self.error = error
        self.sent: list[tuple[str, object]] = []

    def deliver(self, publication_id: str, payload):
        """Fail or accept."""
        if self.failures:
            self.failures -= 1
            raise self.error("rate limited")
        self.sent.append((publication_id, payload))
        return "receipt-1"


def _entry() -> OutboxEntry:
    """One queued match-centre story."""
    return _queue(_binding())[0]


def test_only_the_approved_payload_is_ever_sent() -> None:
    """A payload whose digest differs from the approved one is refused before sending."""
    destination = _Flaky(0)
    with pytest.raises(PermissionError, match="not the approved content"):
        deliver(_entry(), destination, _payload("NOT APPROVED"), settings=ON)
    assert destination.sent == []
    done = deliver(_entry(), destination, _payload(), settings=ON)
    assert done.status == "delivered"
    assert destination.sent == [(done.publication_id, _payload().model_dump(mode="json"))]


def test_transient_failures_retry_then_deliver_exactly_once() -> None:
    """Two failures, then success; a further attempt sends nothing."""
    destination = _Flaky(failures=2)
    entry = _entry()
    for _ in range(2):
        entry = deliver(entry, destination, _payload(), settings=ON)
        assert entry.status == "failed" and entry.last_error == "rate limited"
    entry = deliver(entry, destination, _payload(), settings=ON)
    assert (entry.status, entry.attempts, entry.receipt) == ("delivered", 3, "receipt-1")
    again = deliver(entry, destination, _payload(), settings=ON)
    assert again is entry and len(destination.sent) == 1


def test_retries_are_bounded_and_permanent_failures_stop_at_once() -> None:
    """Out of attempts, or refused outright: the entry is abandoned for a person to check."""
    entry = _entry()
    always = _Flaky(failures=99)
    for _ in range(3):
        entry = deliver(entry, always, _payload(), settings=ON)
    assert (entry.status, entry.attempts) == ("abandoned", 3)
    assert deliver(entry, always, _payload(), settings=ON) is entry
    refused = deliver(_entry(), _Flaky(1, PermanentDeliveryError), _payload(), settings=ON)
    assert (refused.status, refused.attempts) == ("abandoned", 1)


def test_unexpected_errors_still_count_against_the_retry_budget() -> None:
    """A bug in a destination cannot cause endless retries."""
    entry = _entry()
    broken = _Flaky(failures=99, error=TypeError)
    for _ in range(3):
        entry = deliver(entry, broken, _payload(), settings=ON)
    assert (entry.status, entry.attempts, entry.last_error) == ("abandoned", 3, "rate limited")


def test_delivery_stops_when_publication_is_switched_off() -> None:
    """Turning the switch off halts the outbox too; the destination must match the entry."""
    with pytest.raises(PublicationDisabled):
        deliver(_entry(), _Flaky(0), _payload(), settings=PublicationSettings())
    social = _Flaky(0)
    social.name = "social"
    with pytest.raises(ValueError, match="does not match"):
        deliver(_entry(), social, _payload(), settings=ON)


def test_the_outbox_applies_the_same_transition_rules_as_the_database() -> None:
    """Final entries never change, identity never changes, one attempt per result."""
    outbox = InMemoryOutbox()
    entry = outbox.enqueue((_entry(),))[0]
    with pytest.raises(ValueError, match="starts queued"):
        outbox.enqueue((replace(entry, publication_id="f" * 64, attempts=1),))
    with pytest.raises(KeyError):
        outbox.record(replace(entry, publication_id="f" * 64))
    with pytest.raises(ValueError, match="exactly one delivery attempt"):
        outbox.record(replace(entry, status="failed", attempts=2))
    with pytest.raises(ValueError, match="Only delivery status"):
        outbox.record(replace(entry, destination="social", status="failed", attempts=1))
    with pytest.raises(ValueError, match="ends failed"):
        outbox.record(replace(entry, status="queued", attempts=1))
    with pytest.raises(ValueError, match="receipt"):
        outbox.record(replace(entry, status="delivered", attempts=1))
    with pytest.raises(ValueError, match="not a delivery attempt"):
        outbox.record(replace(entry, status="withdrawn", attempts=1))
    failed = deliver(entry, _Flaky(1), _payload(), settings=ON)
    outbox.record(failed)
    done = deliver(failed, _Flaky(0), _payload(), settings=ON)
    outbox.record(done)
    assert outbox.pending() == () and outbox.get(done.publication_id) == done
    for status in ("failed", "queued"):
        with pytest.raises(ValueError, match="is final"):
            outbox.record(replace(done, status=status, attempts=done.attempts + 1))


def test_the_file_feed_writes_each_publication_once(tmp_path: Path) -> None:
    """Same payload again returns the same receipt; a different payload under the ID is refused."""
    feed = FileFeedDestination("match_centre", tmp_path / "feed")
    pid = publication_id(_binding(), "match_centre")
    receipt = feed.deliver(pid, {"headline": "58′ Goal for Northbridge FC"})
    written = tmp_path / "feed" / f"{pid}.json"
    assert json.loads(written.read_text())["headline"].startswith("58")
    assert written.stat().st_mode & 0o777 == 0o644
    assert feed.deliver(pid, {"headline": "58′ Goal for Northbridge FC"}) == receipt
    with pytest.raises(PermanentDeliveryError, match="different payload"):
        feed.deliver(pid, {"headline": "Something else"})
    assert not [p for p in (tmp_path / "feed").iterdir() if p.name.startswith(".pending-")]


@pytest.mark.parametrize("bad", ["../" * 20 + "evil", "A" * 64, "a" * 63, "a" * 64 + "/"])
def test_the_file_feed_refuses_ids_that_are_not_digests(tmp_path: Path, bad: str) -> None:
    """Only a lowercase SHA-256 can name a feed file, so no path can escape the directory."""
    with pytest.raises(PermanentDeliveryError, match="Malformed"):
        FileFeedDestination("match_centre", tmp_path / "feed").deliver(bad, {})


def test_the_file_feed_does_not_follow_links_or_overwrite_a_racing_writer(tmp_path: Path) -> None:
    """A planted link is refused; a file that appears mid-write is compared, not replaced."""
    feed_dir = tmp_path / "feed"
    feed_dir.mkdir()
    pid = "a" * 64
    (feed_dir / f"{pid}.json").symlink_to(tmp_path / "elsewhere.json")
    with pytest.raises(PermanentDeliveryError, match="link"):
        FileFeedDestination("match_centre", feed_dir).deliver(pid, {})
    assert not (tmp_path / "elsewhere.json").exists()

    racer = "b" * 64

    class _Racing(FileFeedDestination):
        """Another writer publishes between the existence check and the link."""

        def _sync_directory(self) -> None:
            """The losing writer must stop before syncing."""
            raise AssertionError("must not reach the sync after losing the race")

    feed = _Racing("match_centre", feed_dir)
    real_link = os.link

    def _link_after_rival(src, dst):
        """A rival writes the target just before this writer links."""
        Path(dst).write_text("rival\n")
        return real_link(src, dst)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os, "link", _link_after_rival)
        with pytest.raises(PermanentDeliveryError, match="different payload"):
            feed.deliver(racer, {"headline": "mine"})
    assert (feed_dir / f"{racer}.json").read_text() == "rival\n"
    assert not [p for p in feed_dir.iterdir() if p.name.startswith(".pending-")]


def test_feed_write_failures_are_retryable(tmp_path: Path) -> None:
    """A full disk or missing permission is a transient delivery error, not a crash."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    with pytest.raises(DeliveryError, match="Feed write failed"):
        FileFeedDestination("match_centre", blocker / "feed").deliver("c" * 64, {})


def test_language_reviews_and_settings_must_be_well_formed() -> None:
    """A reviewer, a SHA-256 digest, a positive sequence and a short note are required."""
    good = {"sequence": 1, "content_digest": "a" * 64, "language": "es", "verdict": "approved"}
    with pytest.raises(ValueError, match="reviewer"):
        LanguageReview(**good, reviewer_actor_id=" ")
    with pytest.raises(ValueError, match="SHA-256"):
        LanguageReview(**{**good, "content_digest": "xyz"}, reviewer_actor_id="r")
    with pytest.raises(ValueError, match="sequence"):
        LanguageReview(**{**good, "sequence": 0}, reviewer_actor_id="r")
    with pytest.raises(ValueError, match="too long"):
        LanguageReview(**good, reviewer_actor_id="r", note="x" * 501)
    with pytest.raises(ValueError, match="max_attempts"):
        PublicationSettings(enabled=True, max_attempts=0)
