"""Deterministic football-state reduction over accepted MatchEvent records.

The reducer assumes temporal ingestion has already produced one accepted sequence-ordered
replay revision. It validates football-state truth that is intentionally outside the
boundary schema: roster membership, substitutions, possession ownership and scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import MatchEvent


@dataclass(frozen=True)
class TeamRoster:
    """Registered players for one team, split into active starters and substitutes."""

    team_id: str
    starters: tuple[str, ...]
    substitutes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject ambiguous or empty roster definitions before reduction begins."""
        if not self.team_id.strip():
            raise ValueError("team_id must not be blank")
        if not self.starters:
            raise ValueError("a roster requires at least one starter")
        players = self.starters + self.substitutes
        if any(not player.strip() for player in players):
            raise ValueError("player identifiers must not be blank")
        if len(set(players)) != len(players):
            raise ValueError("registered player identifiers must be unique per team")


@dataclass(frozen=True)
class MatchState:
    """Immutable snapshot of deterministic football state after accepted events."""

    match_id: str
    last_sequence: int | None
    scores: Mapping[str, int]
    active_players: Mapping[str, frozenset[str]]
    possession_owners: Mapping[int, str]
    scored_shot_ids: frozenset[str]
    processed_event_ids: frozenset[str]


class MatchReducer:
    """Reduce accepted events into auditable score, roster and possession state."""

    def __init__(self, match_id: str, rosters: tuple[TeamRoster, TeamRoster]) -> None:
        """Create an empty match state for exactly two distinct registered teams."""
        if not match_id.strip():
            raise ValueError("match_id must not be blank")
        if len({roster.team_id for roster in rosters}) != 2:
            raise ValueError("exactly two distinct team rosters are required")

        registered_players: dict[str, str] = {}
        for roster in rosters:
            for player in roster.starters + roster.substitutes:
                owner = registered_players.setdefault(player, roster.team_id)
                if owner != roster.team_id:
                    raise ValueError("a player cannot be registered to both teams")

        self._match_id = match_id
        self._rosters = {roster.team_id: roster for roster in rosters}
        self._active_players = {
            roster.team_id: set(roster.starters) for roster in rosters
        }
        self._scores = {roster.team_id: 0 for roster in rosters}
        self._possession_owners: dict[int, str] = {}
        self._events_by_id: dict[str, MatchEvent] = {}
        self._event_digests: dict[str, str] = {}
        self._scored_shot_ids: set[str] = set()
        self._last_sequence: int | None = None

    def snapshot(self) -> MatchState:
        """Return an immutable copy of current reducer state."""
        return MatchState(
            match_id=self._match_id,
            last_sequence=self._last_sequence,
            scores=dict(self._scores),
            active_players={
                team_id: frozenset(players)
                for team_id, players in self._active_players.items()
            },
            possession_owners=dict(self._possession_owners),
            scored_shot_ids=frozenset(self._scored_shot_ids),
            processed_event_ids=frozenset(self._events_by_id),
        )

    def apply(self, event: MatchEvent) -> MatchState:
        """Apply one accepted event or treat an exact duplicate as an idempotent no-op."""
        if event.match_id != self._match_id:
            raise ValueError("event match_id does not match this reducer")

        digest = content_digest(event)
        known_digest = self._event_digests.get(event.event_id)
        if known_digest is not None:
            if known_digest != digest:
                raise ValueError("event_id was reused with different content")
            return self.snapshot()

        if self._last_sequence is not None and event.sequence <= self._last_sequence:
            raise ValueError("events must be reduced in strictly increasing sequence order")

        if event.type not in {"period_start", "period_end"}:
            self._validate_player_event(event)
            self._claim_possession(event)

        if event.type == "substitution":
            self._apply_substitution(event)
        elif event.type == "goal":
            self._apply_goal(event)

        self._events_by_id[event.event_id] = event
        self._event_digests[event.event_id] = digest
        self._last_sequence = event.sequence
        return self.snapshot()

    def _validate_player_event(self, event: MatchEvent) -> None:
        """Require a registered team and a currently active event player."""
        if event.team_id is None or event.player_id is None:
            raise ValueError("player event is missing team or player identity")
        if event.team_id not in self._rosters:
            raise ValueError("event team is not registered for this match")
        if event.player_id not in self._active_players[event.team_id]:
            raise ValueError("event player is not active for this team")

    def _claim_possession(self, event: MatchEvent) -> None:
        """Bind each possession ID to exactly one team for the replay revision."""
        if event.possession_id is None:
            return
        assert event.team_id is not None
        owner = self._possession_owners.setdefault(event.possession_id, event.team_id)
        if owner != event.team_id:
            raise ValueError("possession_id cannot change team ownership")

    def _apply_substitution(self, event: MatchEvent) -> None:
        """Replace one active player with one registered inactive substitute."""
        assert event.team_id is not None
        assert event.player_id is not None
        assert event.related_player_id is not None

        roster = self._rosters[event.team_id]
        registered = set(roster.starters + roster.substitutes)
        incoming = event.related_player_id
        if incoming not in registered:
            raise ValueError("incoming substitute is not registered for this team")
        if incoming in self._active_players[event.team_id]:
            raise ValueError("incoming substitute is already active")

        self._active_players[event.team_id].remove(event.player_id)
        self._active_players[event.team_id].add(incoming)

    def _apply_goal(self, event: MatchEvent) -> None:
        """Validate a goal's shot reference and increment score exactly once."""
        assert event.team_id is not None
        assert event.linked_event_id is not None

        shot = self._events_by_id.get(event.linked_event_id)
        if shot is None:
            raise ValueError("goal references a shot that has not been accepted")
        if shot.type != "shot" or shot.outcome != "goal":
            raise ValueError("goal reference must point to a goal-valued shot")
        if shot.team_id != event.team_id:
            raise ValueError("goal and linked shot must belong to the same team")
        if shot.possession_id != event.possession_id:
            raise ValueError("goal and linked shot must belong to the same possession")
        if shot.event_id in self._scored_shot_ids:
            raise ValueError("linked shot has already produced a score")

        self._scores[event.team_id] += 1
        self._scored_shot_ids.add(shot.event_id)
