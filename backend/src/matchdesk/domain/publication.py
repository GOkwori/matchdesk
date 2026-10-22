"""Publication: an outbox from producer approval to destinations, behind a language-review gate.

``authorize_publication`` (``publication_gate``) proves that one exact approved binding may be
published. This module turns that proof into delivery work:

- Queueing re-runs the approval gate against the producer review state itself, so a caller cannot
  hand in a home-made authorization for content nobody approved.
- Spanish and French content needs a recorded human language review of the exact content digest
  before it can be queued, by someone other than the producer. An AI-assisted translation is not
  a review. The review with the highest
  sequence number is the one that counts; a later "changes requested" blocks the content again.
- Each (binding, destination) pair becomes one outbox entry with a deterministic publication ID, so
  queueing the same approval twice is a no-op, never a second post.
- Destinations accept only the personas they are built for.
- Before every attempt the entry is checked again: if the approval or the language review has
  changed since queueing, the entry is withdrawn instead of sent.
- Delivery sends only a payload whose content digest is the approved one. It is idempotent and
  bounded: any failure counts as an attempt, retries stop at the limit, permanent failures stop at
  once, and a delivered entry is never sent again.
- Publication is off unless the host turns it on. Nothing here authenticates anyone; the host
  establishes the producer, publisher and reviewer identities. PostgreSQL (migration 015) enforces
  the same rules again, against the stored producer audit, and adds what a shared database needs:
  READ COMMITTED only, and a claim with a lease on each attempt so two workers never send at once.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Mapping, Protocol

from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import ApprovalBinding, Contract
from matchdesk.domain.producer_review import ProducerReviewState
from matchdesk.domain.publication_gate import authorize_publication

Language = Literal["en", "es", "fr"]
DestinationName = Literal["match_centre", "social", "broadcast_overlay"]
OutboxStatus = Literal["queued", "delivered", "failed", "abandoned", "withdrawn"]
TERMINAL_STATUSES: frozenset[str] = frozenset({"delivered", "abandoned", "withdrawn"})

# English is written and checked in the studio; other languages need a person who reads them.
LANGUAGES_REQUIRING_REVIEW: frozenset[str] = frozenset({"es", "fr"})

# Which audience versions each destination is built to show.
DESTINATION_PERSONAS: Mapping[str, frozenset[str]] = {
    "match_centre": frozenset({"analyst", "casual_fan"}),
    "social": frozenset({"casual_fan"}),
    "broadcast_overlay": frozenset({"broadcast_caption"}),
}

MAX_REASON_CHARS = 500
_DIGEST = re.compile(r"[0-9a-f]{64}")


class PublicationDisabled(PermissionError):
    """Publication is switched off for this host."""


class DeliveryError(Exception):
    """A destination could not take the content this time; retrying may succeed."""


class PermanentDeliveryError(Exception):
    """A destination refused the content; retrying will not help."""


def same_actor(first: str, second: str) -> bool:
    """Actor IDs that differ only by case or surrounding space are the same person."""
    return first.strip().lower() == second.strip().lower()


@dataclass(frozen=True)
class PublicationSettings:
    """Host policy. Off by default; the host must opt in explicitly."""

    enabled: bool = False
    max_attempts: int = 5

    def __post_init__(self) -> None:
        """Keep the retry budget small and positive."""
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")


@dataclass(frozen=True)
class LanguageReview:
    """One person's verdict on one exact piece of non-English content.

    ``sequence`` is the order the host recorded reviews in (PostgreSQL assigns it); the highest
    sequence for a digest and language is the review that counts.
    """

    sequence: int
    content_digest: str
    language: Language
    verdict: Literal["approved", "changes_requested"]
    reviewer_actor_id: str
    note: str = ""

    def __post_init__(self) -> None:
        """Reject blank reviewers, malformed digests and sequences."""
        if self.sequence < 1:
            raise ValueError("Language review sequence starts at 1")
        if not self.reviewer_actor_id.strip():
            raise ValueError("Language review needs a reviewer")
        if not _DIGEST.fullmatch(self.content_digest):
            raise ValueError("Language review must name a SHA-256 content digest")
        if len(self.note) > MAX_REASON_CHARS:
            raise ValueError("Language review note is too long")


@dataclass(frozen=True)
class OutboxEntry:
    """One approved version bound for one destination, and how its delivery went."""

    publication_id: str
    binding: ApprovalBinding
    destination: DestinationName
    producer_actor_id: str
    publisher_actor_id: str
    reviewer_actor_id: str | None
    status: OutboxStatus = "queued"
    attempts: int = 0
    last_error: str | None = None
    receipt: str | None = None


def publication_id(binding: ApprovalBinding, destination: str) -> str:
    """Deterministic ID: the same approved version to the same destination is one publication.

    Migration 015 computes the identical value (``matchdesk_publication_id``), so the database
    decides the ID rather than trusting the caller's.
    """
    if binding.schema_version != "1.0":  # pragma: no cover - the model only admits 1.0 today
        raise ValueError("Publication IDs are defined for ApprovalBinding 1.0")
    fields = (
        "matchdesk-publication-v1",
        binding.item_id,
        str(binding.item_version),
        binding.replay_id,
        binding.content_digest,
        binding.evidence_digest,
        binding.language,
        binding.persona,
        destination,
    )
    return hashlib.sha256("\x1f".join(fields).encode("utf-8")).hexdigest()


def _review_for(
    binding: ApprovalBinding, reviews: tuple[LanguageReview, ...]
) -> LanguageReview | None:
    """The approving review of this exact content, if the language needs one."""
    if binding.language not in LANGUAGES_REQUIRING_REVIEW:
        return None
    sequences = [r.sequence for r in reviews]
    if len(set(sequences)) != len(sequences):
        raise ValueError("Language review sequence numbers must be unique")
    matching = [
        r
        for r in reviews
        if r.content_digest == binding.content_digest and r.language == binding.language
    ]
    if not matching:
        raise PermissionError(f"{binding.language} content needs a recorded language review")
    latest = max(matching, key=lambda r: r.sequence)
    if latest.verdict != "approved":
        raise PermissionError("The latest language review asked for changes")
    return latest


def queue_publication(
    state: ProducerReviewState,
    binding: ApprovalBinding,
    destinations: tuple[DestinationName, ...],
    *,
    publisher_actor_id: str,
    reviews: tuple[LanguageReview, ...] = (),
    settings: PublicationSettings,
) -> tuple[OutboxEntry, ...]:
    """Turn one producer approval into outbox entries, or refuse.

    Refuses when publication is off, when the binding is not the currently approved version, when
    no destination is named, when a destination does not show this persona, and when non-English
    content lacks an approving review of its exact digest. The publisher must be a different
    person from the producer who approved.
    """
    if not settings.enabled:
        raise PublicationDisabled("Publication is switched off for this host")
    authorization = authorize_publication(state, binding, publisher_actor_id=publisher_actor_id)
    if not destinations or len(set(destinations)) != len(destinations):
        raise ValueError("Name each destination once")
    if same_actor(authorization.publisher_actor_id, authorization.producer_actor_id):
        raise PermissionError("The publisher must not be the producer who approved")
    for destination in destinations:
        allowed = DESTINATION_PERSONAS.get(destination)
        if allowed is None:
            raise ValueError(f"Unknown destination: {destination}")
        if binding.persona not in allowed:
            raise PermissionError(f"{destination} does not show {binding.persona} content")
    review = _review_for(binding, reviews)
    if review is not None and same_actor(review.reviewer_actor_id, authorization.producer_actor_id):
        raise PermissionError("The language reviewer must not be the producer who approved")
    return tuple(
        OutboxEntry(
            publication_id=publication_id(binding, destination),
            binding=binding,
            destination=destination,
            producer_actor_id=authorization.producer_actor_id,
            publisher_actor_id=authorization.publisher_actor_id,
            reviewer_actor_id=None if review is None else review.reviewer_actor_id,
        )
        for destination in destinations
    )


def revalidate(
    entry: OutboxEntry,
    state: ProducerReviewState,
    reviews: tuple[LanguageReview, ...] = (),
) -> OutboxEntry:
    """Withdraw an entry whose approval or language review no longer holds.

    Run immediately before each delivery attempt. A withdrawn entry is final; publishing the
    content again needs a fresh approval and a new queue request.
    """
    if entry.status in TERMINAL_STATUSES:
        return entry
    try:
        authorize_publication(state, entry.binding, publisher_actor_id=entry.publisher_actor_id)
        review = _review_for(entry.binding, reviews)
    except (PermissionError, ValueError) as error:
        return replace(entry, status="withdrawn", last_error=_reason(error))
    if review is not None and not same_actor(
        review.reviewer_actor_id, entry.reviewer_actor_id or ""
    ):
        return replace(
            entry, status="withdrawn", last_error="The approving language review changed"
        )
    return entry


class Destination(Protocol):
    """Somewhere approved content goes. Must be idempotent on publication ID."""

    name: DestinationName

    def deliver(self, publication_id: str, payload: Mapping[str, object]) -> str:
        """Send once; return a receipt. Raise DeliveryError or PermanentDeliveryError."""


def deliver(
    entry: OutboxEntry,
    destination: Destination,
    payload: Contract,
    *,
    settings: PublicationSettings,
) -> OutboxEntry:
    """Attempt one delivery and return the entry's next state.

    Only the approved content is ever sent: the payload's content digest must equal the approved
    binding's. A final entry (delivered, abandoned, withdrawn) is returned unchanged, so nothing is
    ever sent twice. Any failure, expected or not, counts as an attempt against the limit.
    """
    if entry.status in TERMINAL_STATUSES:
        return entry
    if not settings.enabled:
        raise PublicationDisabled("Publication is switched off for this host")
    if destination.name != entry.destination:
        raise ValueError("Destination does not match the outbox entry")
    if content_digest(payload) != entry.binding.content_digest:
        raise PermissionError("Payload is not the approved content")
    attempts = entry.attempts + 1
    try:
        receipt = destination.deliver(entry.publication_id, payload.model_dump(mode="json"))
    except PermanentDeliveryError as error:
        return replace(entry, status="abandoned", attempts=attempts, last_error=_reason(error))
    except Exception as error:  # noqa: BLE001 - every failure must count against the retry budget
        status: OutboxStatus = "abandoned" if attempts >= settings.max_attempts else "failed"
        return replace(entry, status=status, attempts=attempts, last_error=_reason(error))
    return replace(entry, status="delivered", attempts=attempts, last_error=None, receipt=receipt)


def _reason(error: BaseException) -> str:
    """A short, single-line reason for the audit trail."""
    text = " ".join(str(error).split()) or type(error).__name__
    return text[:MAX_REASON_CHARS]


_IMMUTABLE_FIELDS = (
    "publication_id",
    "binding",
    "destination",
    "producer_actor_id",
    "publisher_actor_id",
    "reviewer_actor_id",
)


class InMemoryOutbox:
    """Outbox for tests and single-process hosts; PostgreSQL holds it in production.

    Applies the same transition rules as migration 015: final entries never change, identity
    fields never change, and each delivery result records exactly one attempt.
    """

    def __init__(self) -> None:
        """Start empty."""
        self._entries: dict[str, OutboxEntry] = {}

    def enqueue(self, entries: tuple[OutboxEntry, ...]) -> tuple[OutboxEntry, ...]:
        """Add new entries; an entry already present is kept as it is (idempotent)."""
        for entry in entries:
            if entry.status != "queued" or entry.attempts or entry.receipt is not None:
                raise ValueError("A publication starts queued, unattempted and without a receipt")
            self._entries.setdefault(entry.publication_id, entry)
        return tuple(self._entries[entry.publication_id] for entry in entries)

    def pending(self) -> tuple[OutboxEntry, ...]:
        """Entries still worth trying."""
        return tuple(e for e in self._entries.values() if e.status in ("queued", "failed"))

    def record(self, entry: OutboxEntry) -> None:
        """Store a delivery result or a withdrawal."""
        current = self._entries.get(entry.publication_id)
        if current is None:
            raise KeyError("Unknown publication")
        if current.status in TERMINAL_STATUSES:
            raise ValueError(f"A {current.status} publication is final")
        if any(getattr(entry, f) != getattr(current, f) for f in _IMMUTABLE_FIELDS):
            raise ValueError("Only delivery status may change")
        if entry.status == "withdrawn":
            if entry.attempts != current.attempts:
                raise ValueError("A withdrawal is not a delivery attempt")
        elif entry.status not in ("failed", "delivered", "abandoned"):
            raise ValueError("An attempt ends failed, delivered or abandoned")
        elif entry.attempts != current.attempts + 1:
            raise ValueError("Each result records exactly one delivery attempt")
        if (entry.status == "delivered") != (entry.receipt is not None):
            raise ValueError("A receipt is recorded exactly when delivered")
        self._entries[entry.publication_id] = entry

    def get(self, publication_id: str) -> OutboxEntry:
        """One entry by ID."""
        return self._entries[publication_id]


class FileFeedDestination:
    """Writes each publication as a JSON file in a feed directory, atomically and once.

    Suits a static feed that a site or app reads. Writing the same publication again returns the
    original receipt; different content under the same ID is refused. Files are durable before the
    receipt is returned and readable by the feed's readers.
    """

    def __init__(self, name: DestinationName, directory: Path) -> None:
        """Deliver into one directory."""
        self.name = name
        self._directory = directory

    def deliver(self, publication_id: str, payload: Mapping[str, object]) -> str:
        """Write ``<publication_id>.json`` once; receipt is the file's SHA-256."""
        if not _DIGEST.fullmatch(publication_id):
            raise PermanentDeliveryError("Malformed publication ID")
        body = (json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode(
            "utf-8"
        )
        digest = hashlib.sha256(body).hexdigest()
        target = self._directory / f"{publication_id}.json"
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                raise PermanentDeliveryError("Feed entry is a link")
            if target.exists():
                return self._existing(target, digest)
            fd, temp = tempfile.mkstemp(dir=self._directory, prefix=".pending-")
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(body)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temp, 0o644)
                try:
                    # link() refuses an existing target, so two writers cannot overwrite each other.
                    os.link(temp, target)
                except FileExistsError:
                    return self._existing(target, digest)
            finally:
                Path(temp).unlink(missing_ok=True)
            self._sync_directory()
        except OSError as error:
            raise DeliveryError(f"Feed write failed: {error.strerror or error}") from error
        return digest

    def _existing(self, target: Path, digest: str) -> str:
        """Same content already published returns its receipt; different content is refused."""
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise PermanentDeliveryError("A different payload was already published under this ID")
        return digest

    def _sync_directory(self) -> None:
        """Make the new directory entry durable."""
        fd = os.open(self._directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
