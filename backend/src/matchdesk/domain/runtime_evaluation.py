"""P2-05 bounded runtime evaluation controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from matchdesk.domain.models import EvidenceRecord, MatchEvent, VerificationResult
from matchdesk.domain.specialists import SpecialistResponse
from matchdesk.domain.verification import verify_claim

EvaluationStatus = Literal["pass", "needs_revision", "blocked"]


@dataclass(frozen=True)
class ModelEvaluation:
    """Deterministic evaluation of one specialist proposal."""

    status: EvaluationStatus
    verification_results: tuple[VerificationResult, ...]
    reason: str


def evaluate_specialist_response(
    response: SpecialistResponse,
    evidence: EvidenceRecord,
    events: tuple[MatchEvent, ...],
) -> ModelEvaluation:
    """Evaluate each proposed claim against deterministic evidence."""
    if not response.proposed_claims:
        return ModelEvaluation(
            status="needs_revision",
            verification_results=(),
            reason="Evaluation requires at least one evidence-bound claim",
        )

    results = tuple(verify_claim(claim, evidence, events) for claim in response.proposed_claims)
    if any(result.status == "blocked" for result in results):
        return ModelEvaluation(
            status="blocked",
            verification_results=results,
            reason="At least one claim failed evidence binding",
        )
    if any(result.status == "needs_revision" for result in results):
        return ModelEvaluation(
            status="needs_revision",
            verification_results=results,
            reason="At least one claim requires deterministic revision",
        )
    return ModelEvaluation(
        status="pass",
        verification_results=results,
        reason="All proposed claims passed deterministic verification",
    )
