"""Publication: an outbox from producer approval to destinations, behind a language-review gate.

The pure ``authorize_publication`` gate (``publication_gate``) proves that one exact approved
binding may be published. This module turns that proof into delivery work:

- Spanish and French content needs a recorded human language review of the exact content digest
  before it can be queued. An AI-assisted translation is not a review.
- Each (binding, destination) pair becomes one outbox entry with a deterministic publication ID, so
  queueing the same approval twice is a no-op, never a second post.
- Destinations accept only the personas they are built for.
- Delivery is idempotent and bounded: transient failures retry up to a limit, permanent failures
  stop at once, and a delivered entry is never sent again.
- Publication is off unless the host turns it on. Nothing here authenticates anyone; the host
  establishes the producer, publisher and reviewer identities.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Mapping, Protocol

from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.publication_gate import PublicationAuthorization

Language = Literal["en", "es", "fr"]
DestinationName = Literal["match_centre", "social", "broadcast_overlay"]
OutboxStatus = Literal["queued", "delivered", "failed", "abandoned"]

# English is written and checked in the studio; other languages need a person who reads them.
LANGUAGES_REQUIRING_REVIEW: frozenset[str] = frozenset({"es", "fr"})

# Which audience versions each destination is built to show.
DESTINATION_PERSONAS: Mapping[str, frozenset[str]] = {
    "match_centre": frozenset({"analyst", "casual_fan"}),
    "social": frozenset({"casual_fan"}),
    "broadcast_overlay": frozenset({"broadcast_caption"}),
}

MAX_REASON_CHARS = 500


class PublicationDisabled(PermissionError):
    """Publication is switched off for this host."""


class DeliveryError(Exception):
    """A destination could not take the content this time; retrying may succeed."""


class PermanentDeliveryError(Exception):
    """A destination refused the content; retrying will not help."""


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
    """One person's verdict on one exact piece of non-English content."""

    content_digest: str
    language: Language
    verdict: Literal["approved", "changes_requested"]
    reviewer_actor_id: str
    note: str = ""

    def __post_init__(self) -> None:
        """Reject blank reviewers and malformed digests."""
        if not self.reviewer_actor_id.strip():
            raise ValueError("Language review needs a reviewer")
        if len(self.content_digest) != 64 or any(
            c not in "0123456789abcdef" for c in self.content_digest
        ):
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
    """Deterministic ID: the same approved version to the same destination is one publication."""
    canonical = json.dumps(
        {"binding": binding.model_dump(mode="json"), "destination": destination},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _review_for(
    binding: ApprovalBinding, reviews: tuple[LanguageReview, ...]
) -> LanguageReview | None:
    """The approving review of this exact content, if the language needs one."""
    if binding.language not in LANGUAGES_REQUIRING_REVIEW:
        return None
    matching = [
        r
        for r in reviews
        if r.content_digest == binding.content_digest and r.language == binding.language
    ]
    if not matching:
        raise PermissionError(f"{binding.language} content needs a recorded language review")
    latest = matching[-1]
    if latest.verdict != "approved":
        raise PermissionError("The latest language review asked for changes")
    return latest


def queue_publication(
    authorization: PublicationAuthorization,
    destinations: tuple[DestinationName, ...],
    *,
    reviews: tuple[LanguageReview, ...] = (),
    settings: PublicationSettings,
) -> tuple[OutboxEntry, ...]:
    """Turn one publication authorization into outbox entries, or refuse.

    Refuses when publication is off, when no destination is named, when a destination does not
    show this persona, and when non-English content lacks an approving review of its exact digest.
    The publisher must be a different person from the producer who approved.
    """
    if not settings.enabled:
        raise PublicationDisabled("Publication is switched off for this host")
    if not destinations or len(set(destinations)) != len(destinations):
        raise ValueError("Name each destination once")
    if authorization.publisher_actor_id == authorization.producer_actor_id:
        raise PermissionError("The publisher must not be the producer who approved")
    binding = authorization.binding
    for destination in destinations:
        allowed = DESTINATION_PERSONAS.get(destination)
        if allowed is None:
            raise ValueError(f"Unknown destination: {destination}")
        if binding.persona not in allowed:
            raise PermissionError(f"{destination} does not show {binding.persona} content")
    review = _review_for(binding, reviews)
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


class Destination(Protocol):
    """Somewhere approved content goes. Must be idempotent on publication ID."""

    name: DestinationName

    def deliver(self, publication_id: str, payload: Mapping[str, object]) -> str:
        """Send once; return a receipt. Raise DeliveryError or PermanentDeliveryError."""


def deliver(
    entry: OutboxEntry,
    destination: Destination,
    payload: Mapping[str, object],
    *,
    settings: PublicationSettings,
) -> OutboxEntry:
    """Attempt one delivery and return the entry's next state.

    A delivered or abandoned entry is returned unchanged: nothing is ever sent twice, and an
    abandoned entry needs a person to look at it.
    """
    if entry.status in ("delivered", "abandoned"):
        return entry
    if not settings.enabled:
        raise PublicationDisabled("Publication is switched off for this host")
    if destination.name != entry.destination:
        raise ValueError("Destination does not match the outbox entry")
    attempts = entry.attempts + 1
    try:
        receipt = destination.deliver(entry.publication_id, payload)
    except PermanentDeliveryError as error:
        return replace(entry, status="abandoned", attempts=attempts, last_error=_reason(error))
    except DeliveryError as error:
        status: OutboxStatus = "abandoned" if attempts >= settings.max_attempts else "failed"
        return replace(entry, status=status, attempts=attempts, last_error=_reason(error))
    return replace(entry, status="delivered", attempts=attempts, last_error=None, receipt=receipt)


def _reason(error: BaseException) -> str:
    """A short, single-line reason for the audit trail."""
    text = " ".join(str(error).split()) or type(error).__name__
    return text[:MAX_REASON_CHARS]


class InMemoryOutbox:
    """Outbox for tests and single-process hosts; PostgreSQL holds it in production."""

    def __init__(self) -> None:
        """Start empty."""
        self._entries: dict[str, OutboxEntry] = {}

    def enqueue(self, entries: tuple[OutboxEntry, ...]) -> tuple[OutboxEntry, ...]:
        """Add new entries; an entry already present is kept as it is (idempotent)."""
        for entry in entries:
            self._entries.setdefault(entry.publication_id, entry)
        return tuple(self._entries[entry.publication_id] for entry in entries)

    def pending(self) -> tuple[OutboxEntry, ...]:
        """Entries still worth trying."""
        return tuple(e for e in self._entries.values() if e.status in ("queued", "failed"))

    def record(self, entry: OutboxEntry) -> None:
        """Store a delivery result; a delivered entry can never move backwards."""
        current = self._entries.get(entry.publication_id)
        if current is None:
            raise KeyError("Unknown publication")
        if current.status == "delivered" and entry.status != "delivered":
            raise ValueError("A delivered publication cannot change state")
        self._entries[entry.publication_id] = entry

    def get(self, publication_id: str) -> OutboxEntry:
        """One entry by ID."""
        return self._entries[publication_id]


class FileFeedDestination:
    """Writes each publication as a JSON file in a feed directory, atomically and once.

    Suits a static feed that a site or app reads. Writing the same publication again returns the
    original receipt; different content under the same ID is refused.
    """

    def __init__(self, name: DestinationName, directory: Path) -> None:
        """Deliver into one directory."""
        self.name = name
        self._directory = directory

    def deliver(self, publication_id: str, payload: Mapping[str, object]) -> str:
        """Write ``<publication_id>.json`` once; receipt is the file's SHA-256."""
        if len(publication_id) != 64:
            raise PermanentDeliveryError("Malformed publication ID")
        body = (json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode(
            "utf-8"
        )
        digest = hashlib.sha256(body).hexdigest()
        target = self._directory / f"{publication_id}.json"
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise PermanentDeliveryError(
                        "A different payload was already published under this ID"
                    )
                return digest
            fd, temp = tempfile.mkstemp(dir=self._directory, prefix=".pending-")
            with os.fdopen(fd, "wb") as handle:
                handle.write(body)
            os.replace(temp, target)
        except OSError as error:
            raise DeliveryError(f"Feed write failed: {error.strerror or error}") from error
        return digest
