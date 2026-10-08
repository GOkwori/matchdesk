"""Ordered, idempotent replay ingestion for deterministic MatchDesk event streams.

The ingestor accepts already-validated MatchEvent records. It does not enforce roster,
score or possession truth; those responsibilities belong to the later reducer. This
module handles arrival order, duplicate identity, sequence gaps and replay resets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import MatchEvent


DecisionStatus = Literal["accepted", "buffered", "duplicate", "reset"]


@dataclass(frozen=True)
class IngestionDecision:
    """Result of one arrival, preserving arrival order separately from event order."""

    status: DecisionStatus
    arrival_index: int
    replay_id: str
    revision: int
    event_id: str
    accepted_event_ids: tuple[str, ...]
    missing_sequences: tuple[int, ...]


@dataclass(frozen=True)
class IngestionSnapshot:
    """Immutable view of the current replay revision and its accepted event order."""

    match_id: str
    replay_id: str
    revision: int
    expected_sequence: int
    accepted_events: tuple[MatchEvent, ...]
    buffered_sequences: tuple[int, ...]
    missing_sequences: tuple[int, ...]


class ReplayIngestor:
    """Ingest one match stream deterministically with explicit replay revision resets."""

    def __init__(self, match_id: str) -> None:
        """Create an empty first replay revision for one match identifier."""
        if not match_id:
            raise ValueError("match_id must not be blank")
        self._match_id = match_id
        self._revision = 1
        self._arrival_index = 0
        self._expected_sequence = 0
        self._accepted_by_sequence: dict[int, MatchEvent] = {}
        self._buffered_by_sequence: dict[int, MatchEvent] = {}
        self._known_by_event_id: dict[str, str] = {}

    @property
    def replay_id(self) -> str:
        """Return the deterministic replay identifier for the active revision."""
        return f"{self._match_id}-r{self._revision}"

    def snapshot(self) -> IngestionSnapshot:
        """Return accepted order, pending sequences and all currently visible gaps."""
        return IngestionSnapshot(
            match_id=self._match_id,
            replay_id=self.replay_id,
            revision=self._revision,
            expected_sequence=self._expected_sequence,
            accepted_events=tuple(
                self._accepted_by_sequence[index]
                for index in sorted(self._accepted_by_sequence)
            ),
            buffered_sequences=tuple(sorted(self._buffered_by_sequence)),
            missing_sequences=self._missing_sequences(),
        )

    def ingest(self, event: MatchEvent) -> IngestionDecision:
        """Ingest one arrival without hiding duplicates, gaps or replay boundaries."""
        if event.match_id != self._match_id:
            raise ValueError("event match_id does not match this ingestor")

        arrival_index = self._arrival_index
        self._arrival_index += 1
        digest = content_digest(event)

        known_digest = self._known_by_event_id.get(event.event_id)
        if known_digest is not None:
            if known_digest != digest:
                raise ValueError("event_id was reused with different content")
            return self._decision(
                status="duplicate",
                arrival_index=arrival_index,
                event=event,
                accepted_event_ids=(),
            )

        if event.sequence == 0 and (
            self._accepted_by_sequence or self._buffered_by_sequence
        ):
            self._start_new_revision()
            accepted_ids = self._accept_and_flush(event, digest)
            return self._decision(
                status="reset",
                arrival_index=arrival_index,
                event=event,
                accepted_event_ids=accepted_ids,
            )

        if event.sequence < self._expected_sequence:
            raise ValueError("sequence is behind the accepted replay position")

        accepted = self._accepted_by_sequence.get(event.sequence)
        if accepted is not None:
            raise ValueError("sequence is already occupied by another event")

        buffered = self._buffered_by_sequence.get(event.sequence)
        if buffered is not None:
            if content_digest(buffered) != digest:
                raise ValueError("sequence collision has different content")
            self._known_by_event_id[event.event_id] = digest
            return self._decision(
                status="duplicate",
                arrival_index=arrival_index,
                event=event,
                accepted_event_ids=(),
            )

        if event.sequence > self._expected_sequence:
            self._buffered_by_sequence[event.sequence] = event
            self._known_by_event_id[event.event_id] = digest
            return self._decision(
                status="buffered",
                arrival_index=arrival_index,
                event=event,
                accepted_event_ids=(),
            )

        accepted_ids = self._accept_and_flush(event, digest)
        return self._decision(
            status="accepted",
            arrival_index=arrival_index,
            event=event,
            accepted_event_ids=accepted_ids,
        )

    def _start_new_revision(self) -> None:
        """Discard current accepted/pending state and advance the replay revision."""
        self._revision += 1
        self._expected_sequence = 0
        self._accepted_by_sequence.clear()
        self._buffered_by_sequence.clear()
        self._known_by_event_id.clear()

    def _accept_and_flush(self, event: MatchEvent, digest: str) -> tuple[str, ...]:
        """Accept the expected event, then drain any now-contiguous pending events."""
        accepted_ids = [event.event_id]
        self._accepted_by_sequence[event.sequence] = event
        self._known_by_event_id[event.event_id] = digest
        self._expected_sequence += 1

        while self._expected_sequence in self._buffered_by_sequence:
            pending = self._buffered_by_sequence.pop(self._expected_sequence)
            self._accepted_by_sequence[pending.sequence] = pending
            accepted_ids.append(pending.event_id)
            self._expected_sequence += 1

        return tuple(accepted_ids)

    def _missing_sequences(self) -> tuple[int, ...]:
        """Return holes between the next expected sequence and furthest buffered event."""
        if not self._buffered_by_sequence:
            return ()
        furthest = max(self._buffered_by_sequence)
        return tuple(
            sequence
            for sequence in range(self._expected_sequence, furthest + 1)
            if sequence not in self._buffered_by_sequence
        )

    def _decision(
        self,
        *,
        status: DecisionStatus,
        arrival_index: int,
        event: MatchEvent,
        accepted_event_ids: tuple[str, ...],
    ) -> IngestionDecision:
        """Build one immutable decision against the state after this arrival."""
        return IngestionDecision(
            status=status,
            arrival_index=arrival_index,
            replay_id=self.replay_id,
            revision=self._revision,
            event_id=event.event_id,
            accepted_event_ids=accepted_event_ids,
            missing_sequences=self._missing_sequences(),
        )
