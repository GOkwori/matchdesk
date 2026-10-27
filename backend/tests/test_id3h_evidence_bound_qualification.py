"""End-to-end disposable ID3H evidence binding; no release execution capability."""

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from matchdesk.domain.id3h_approval_reservations import DisposableApprovalReservationStore
from matchdesk.domain.id3h_ci_evidence import (
    DisposableCIFileEvidenceReader,
    EvidenceBoundCIHostSource,
)
from matchdesk.domain.id3h_qualification_host import DisposableApprovalQualificationHost
from matchdesk.domain.id3h_release_approval import (
    ACTION,
    AUDIENCE,
    ENVIRONMENT,
    ISSUER,
    ObservedReleaseFacts,
    ReleaseDenied,
)

NOW = datetime.fromtimestamp(1_800_000_100, tz=timezone.utc)
FILES = (
    ("tenant_fingerprint", "tenant.identity"),
    ("database_fingerprint", "database.identity"),
    ("migration_sha256", "migration.sql"),
    ("historical_evidence_sha256", "historical.json"),
    ("backup_evidence_sha256", "backup.json"),
    ("catalog_evidence_sha256", "catalog.json"),
    ("cost_decision_sha256", "cost.json"),
)


class SyntheticTrustSource:
    """Model independently acquired host facts; never a production authenticator."""

    def __init__(self, facts: ObservedReleaseFacts, key: Ed25519PrivateKey) -> None:
        """Retain synthetic observations and an ephemeral signing key."""
        self.facts = facts
        self.key = key
        self.actor = facts.operator_id
        self.observations = 0
        self.change_on_second_read: Path | None = None

    def verified_actor(self) -> str:
        """Return the simulated workload identity from the test-only host."""
        return self.actor

    def observe_release(self) -> ObservedReleaseFacts:
        """Optionally mutate the fixture immediately before the second read."""
        self.observations += 1
        if self.observations == 2 and self.change_on_second_read is not None:
            self.change_on_second_read.write_bytes(b"changed-after-reservation")
        return self.facts

    def approval_key(self):
        """Return the synthetic out-of-band verification key."""
        return self.key.public_key()

    def utcnow(self) -> datetime:
        """Return a fixed, timezone-aware CI clock."""
        return NOW


def fixture(tmp_path: Path) -> tuple[Path, ObservedReleaseFacts]:
    """Generate seven private artifacts and derive facts from their real bytes."""
    root = tmp_path / "id3h-evidence"
    root.mkdir(mode=0o700)
    for _, filename in FILES:
        target = root / filename
        target.write_bytes(("synthetic-" + filename).encode("ascii"))
        target.chmod(0o600)
    digests = DisposableCIFileEvidenceReader(root).snapshot()
    facts = ObservedReleaseFacts(
        action=ACTION,
        environment=ENVIRONMENT,
        operator_id="ci-workload:alice",
        tenant_fingerprint=digests.tenant_fingerprint,
        database_fingerprint=digests.database_fingerprint,
        source_commit="3" * 40,
        migration_sha256=digests.migration_sha256,
        historical_evidence_sha256=digests.historical_evidence_sha256,
        backup_evidence_sha256=digests.backup_evidence_sha256,
        catalog_evidence_sha256=digests.catalog_evidence_sha256,
        cost_decision_sha256=digests.cost_decision_sha256,
        change_id="ci-change:alpha",
    )
    return root, facts


def signed_approval(key: Ed25519PrivateKey, facts: ObservedReleaseFacts) -> str:
    """Issue a synthetic approval scoped to every independently observed fact."""
    claims: dict[str, object] = {
        "version": 1,
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "approval_id": "a" * 32,
        "reviewer_id": "human-reviewer:1",
        "issued_at": 1_800_000_000,
        "not_before": 1_800_000_000,
        "expires_at": 1_800_000_300,
        **{name: getattr(facts, name) for name in facts.__dataclass_fields__},
    }
    canonical = json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    signature = base64.urlsafe_b64encode(key.sign(canonical.encode("utf-8"))).decode().rstrip("=")
    return json.dumps({"claims": claims, "signature": signature})


def host(
    tmp_path: Path, root: Path, source: SyntheticTrustSource
) -> DisposableApprovalQualificationHost:
    """Wire actual file re-observation to durable CI-only single-use storage."""
    return DisposableApprovalQualificationHost(
        source=EvidenceBoundCIHostSource(
            delegate=source, reader=DisposableCIFileEvidenceReader(root)
        ),
        reservations=DisposableApprovalReservationStore(tmp_path / "approvals.sqlite3"),
    )


def test_valid_evidence_bound_grant_produces_non_execution_receipt(tmp_path: Path) -> None:
    """Signed, matching evidence yields a receipt but no execution authority."""
    root, facts = fixture(tmp_path)
    key = Ed25519PrivateKey.generate()
    token = signed_approval(key, facts)
    receipt = host(tmp_path, root, SyntheticTrustSource(facts, key)).qualify(token)
    assert receipt.approval_id == "a" * 32
    assert receipt.environment == ENVIRONMENT
    assert receipt.execution_authorized is False
    with pytest.raises(ReleaseDenied):
        host(tmp_path, root, SyntheticTrustSource(facts, key)).qualify(token)


@pytest.mark.parametrize("field", [name for name, _ in FILES])
def test_each_tampered_evidence_file_denies_before_reservation(tmp_path: Path, field: str) -> None:
    """All seven evidence inputs must be re-read, not copied from the grant."""
    root, facts = fixture(tmp_path)
    key = Ed25519PrivateKey.generate()
    token = signed_approval(key, facts)
    filename = dict(FILES)[field]
    target = root / filename
    original = target.read_bytes()
    target.write_bytes(b"tampered-evidence")
    with pytest.raises(ReleaseDenied):
        host(tmp_path, root, SyntheticTrustSource(facts, key)).qualify(token)
    # A denial before reservation must not consume the one-time approval.
    target.write_bytes(original)
    assert host(tmp_path, root, SyntheticTrustSource(facts, key)).qualify(token).approval_id


def test_evidence_change_after_reservation_consumes_but_denies(tmp_path: Path) -> None:
    """An approval cannot be replayed after evidence changes during qualification."""
    root, facts = fixture(tmp_path)
    key = Ed25519PrivateKey.generate()
    token = signed_approval(key, facts)
    source = SyntheticTrustSource(facts, key)
    target = root / "backup.json"
    original = target.read_bytes()
    source.change_on_second_read = target
    with pytest.raises(ReleaseDenied):
        host(tmp_path, root, source).qualify(token)
    target.write_bytes(original)
    with pytest.raises(ReleaseDenied):
        host(tmp_path, root, SyntheticTrustSource(facts, key)).qualify(token)


def test_untrusted_actor_denied_before_approval_is_spent(tmp_path: Path) -> None:
    """Evidence hashes alone never substitute for the observed workload actor."""
    root, facts = fixture(tmp_path)
    key = Ed25519PrivateKey.generate()
    token = signed_approval(key, facts)
    source = SyntheticTrustSource(facts, key)
    source.actor = "ci-workload:other"
    with pytest.raises(ReleaseDenied):
        host(tmp_path, root, source).qualify(token)
    source.actor = facts.operator_id
    receipt = host(tmp_path, root, source).qualify(token)
    assert receipt.execution_authorized is False


def test_missing_evidence_denies_without_spending_approval(tmp_path: Path) -> None:
    """Unavailability of a required private file must fail closed."""
    root, facts = fixture(tmp_path)
    key = Ed25519PrivateKey.generate()
    token = signed_approval(key, facts)
    target = root / "catalog.json"
    original = target.read_bytes()
    target.unlink()
    with pytest.raises(ReleaseDenied):
        host(tmp_path, root, SyntheticTrustSource(facts, key)).qualify(token)
    target.write_bytes(original)
    target.chmod(0o600)
    assert host(tmp_path, root, SyntheticTrustSource(facts, key)).qualify(token).approval_id
