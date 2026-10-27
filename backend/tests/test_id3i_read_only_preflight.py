"""ID3I read-only, dual-identity, non-execution preflight regressions."""

import base64
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from matchdesk.domain.id3h_approval_reservations import DisposableApprovalReservationStore
from matchdesk.domain.id3h_ci_evidence import (
    DisposableCIFileEvidenceReader,
    EvidenceBoundCIHostSource,
)
from matchdesk.domain.id3h_release_approval import (
    ACTION,
    AUDIENCE,
    ENVIRONMENT,
    ISSUER,
    ObservedReleaseFacts,
    ReleaseDenied,
)
from matchdesk.domain.id3i_read_only_preflight import (
    DisposableReadOnlyHostPreflight,
    ObservedCatalogAccess,
)

NOW = datetime.fromtimestamp(1_800_000_100, tz=timezone.utc)
FILES = {
    "tenant_fingerprint": "tenant.identity",
    "database_fingerprint": "database.identity",
    "migration_sha256": "migration.sql",
    "historical_evidence_sha256": "historical.json",
    "backup_evidence_sha256": "backup.json",
    "catalog_evidence_sha256": "catalog.json",
    "cost_decision_sha256": "cost.json",
}


class SyntheticSource:
    """Disposable test source, deliberately not a genuine identity authority."""

    def __init__(self, facts: ObservedReleaseFacts, key: Ed25519PrivateKey) -> None:
        """Use fixed fixture facts and a fresh signing key per test."""
        self.facts = facts
        self.actor = facts.operator_id
        self.key = key
        self.observations = 0
        self.drift_after_consume = False

    def verified_actor(self) -> str:
        """Simulate the authenticated workload observed outside the request."""
        return self.actor

    def observe_release(self) -> ObservedReleaseFacts:
        """Optionally change observed DB scope after the approval is spent."""
        self.observations += 1
        if self.drift_after_consume and self.observations >= 4:
            return replace(self.facts, database_fingerprint="9" * 64)
        return self.facts

    def approval_key(self):
        """Use the synthetic pinned public key, not the envelope's claims."""
        return self.key.public_key()

    def utcnow(self) -> datetime:
        """Use a deterministic CI-only clock for expiry checks."""
        return NOW


class SyntheticContext:
    """Fake host-owned operator and catalog grants for negative-case testing."""

    def __init__(self, access: ObservedCatalogAccess) -> None:
        """Start in read-only posture, allowing explicit fault injection."""
        self.human = "ci-human:operator"
        self.access = access
        self.access_reads = 0
        self.drift_role = False
        self.human_reads = 0
        self.drift_human = False

    def authenticated_human(self) -> str:
        """Simulate human identity drift after a durable reservation."""
        self.human_reads += 1
        if self.drift_human and self.human_reads >= 2:
            return "ci-human:other"
        return self.human

    def observe_catalog_access(self) -> ObservedCatalogAccess:
        """Simulate a privilege escalation after initial preflight checks."""
        self.access_reads += 1
        if self.drift_role and self.access_reads >= 2:
            return replace(self.access, can_write_data=True)
        return self.access


Sandbox = tuple[
    DisposableReadOnlyHostPreflight,
    SyntheticSource,
    SyntheticContext,
    ObservedReleaseFacts,
    Ed25519PrivateKey,
]


def sandbox(tmp_path: Path) -> Sandbox:
    """Create seven real private files, a signed scope and durable CI ledger."""
    root = tmp_path / "private-evidence"
    root.mkdir(mode=0o700)
    for filename in FILES.values():
        target = root / filename
        target.write_bytes(("synthetic:" + filename).encode("ascii"))
        target.chmod(0o600)
    digests = DisposableCIFileEvidenceReader(root).snapshot()
    facts = ObservedReleaseFacts(
        action=ACTION,
        environment=ENVIRONMENT,
        operator_id="ci-workload:reader",
        tenant_fingerprint=digests.tenant_fingerprint,
        database_fingerprint=digests.database_fingerprint,
        source_commit="3" * 40,
        migration_sha256=digests.migration_sha256,
        historical_evidence_sha256=digests.historical_evidence_sha256,
        backup_evidence_sha256=digests.backup_evidence_sha256,
        catalog_evidence_sha256=digests.catalog_evidence_sha256,
        cost_decision_sha256=digests.cost_decision_sha256,
        change_id="ci-change:read-only",
    )
    key = Ed25519PrivateKey.generate()
    source = SyntheticSource(facts, key)
    context = SyntheticContext(
        ObservedCatalogAccess(
            workload_id=facts.operator_id,
            database_fingerprint=facts.database_fingerprint,
            role_name="ci-catalog-reader",
            can_read_catalog=True,
            can_write_data=False,
            can_manage_roles=False,
            can_edit_migration_receipts=False,
        )
    )
    host = DisposableReadOnlyHostPreflight(
        source=EvidenceBoundCIHostSource(
            delegate=source, reader=DisposableCIFileEvidenceReader(root)
        ),
        context=context,
        reservations=DisposableApprovalReservationStore(tmp_path / "reservations.sqlite3"),
    )
    return host, source, context, facts, key


def sign(key: Ed25519PrivateKey, facts: ObservedReleaseFacts, reviewer="ci-human:reviewer") -> str:
    """Sign only test scope with fixed ID3H CI audience and short expiry."""
    claims: dict[str, object] = {
        "version": 1,
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "approval_id": "a" * 32,
        "reviewer_id": reviewer,
        "issued_at": 1_800_000_000,
        "not_before": 1_800_000_000,
        "expires_at": 1_800_000_300,
        **{field: getattr(facts, field) for field in facts.__dataclass_fields__},
    }
    canonical = json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    signature = base64.urlsafe_b64encode(key.sign(canonical.encode("utf-8"))).decode().rstrip("=")
    return json.dumps({"claims": claims, "signature": signature})


def test_receipt_grants_neither_execution_nor_database_writes(tmp_path: Path) -> None:
    """Valid evidence yields a test-only, replay-resistant, non-execution receipt."""
    host, _, _, facts, key = sandbox(tmp_path)
    token = sign(key, facts)
    receipt = host.inspect(token)
    assert receipt.approval_id == "a" * 32
    assert receipt.environment == "disposable-ci"
    assert receipt.execution_authorized is False
    assert receipt.database_writes_authorized is False
    with pytest.raises(ReleaseDenied):
        host.inspect(token)


@pytest.mark.parametrize(
    "change",
    [
        {"can_read_catalog": False},
        {"can_write_data": True},
        {"can_manage_roles": True},
        {"can_edit_migration_receipts": True},
        {"role_name": "ci-migration-admin"},
        {"database_fingerprint": "0" * 64},
        {"workload_id": "ci-workload:other"},
    ],
)
def test_excess_permissions_or_target_mismatch_denied_before_use(
    tmp_path: Path, change: dict[str, object]
) -> None:
    """Read-only privilege or target changes must not consume a valid grant."""
    host, _, context, facts, key = sandbox(tmp_path)
    original = context.access
    context.access = replace(context.access, **change)
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts))
    context.access = original
    assert host.inspect(sign(key, facts)).execution_authorized is False


@pytest.mark.parametrize("identity", ["", "ci-workload:reader", "bad identity"])
def test_unverified_or_colliding_human_denied_before_use(tmp_path: Path, identity: str) -> None:
    """An absent or workload-identical operator cannot act as the human."""
    host, _, context, facts, key = sandbox(tmp_path)
    context.human = identity
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts))
    context.human = "ci-human:operator"
    assert host.inspect(sign(key, facts)).database_writes_authorized is False


def test_self_review_denied_after_signature_and_consumption(tmp_path: Path) -> None:
    """A signed reviewer identical to the operator is rejected, not reusable."""
    host, _, _, facts, key = sandbox(tmp_path)
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts, reviewer="ci-human:operator"))
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts))


@pytest.mark.parametrize("drift", ["drift_human", "drift_role"])
def test_post_reservation_identity_or_role_drift_consumes_and_denies(
    tmp_path: Path, drift: str
) -> None:
    """Do not restore consumed approvals after a post-consumption trust change."""
    host, _, context, facts, key = sandbox(tmp_path)
    setattr(context, drift, True)
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts))
    setattr(context, drift, False)
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts))


def test_observed_target_drift_after_reservation_denied(tmp_path: Path) -> None:
    """Late DB changes cannot be masked by a valid earlier evidence digest."""
    host, source, _, facts, key = sandbox(tmp_path)
    source.drift_after_consume = True
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts))
    source.drift_after_consume = False
    with pytest.raises(ReleaseDenied):
        host.inspect(sign(key, facts))


def test_untrusted_source_and_fake_reservation_store_cannot_be_injected(tmp_path: Path) -> None:
    """A self-asserted source or always-success ledger is not an eligible host."""
    host, _, context, _, _ = sandbox(tmp_path)
    with pytest.raises(ReleaseDenied):
        DisposableReadOnlyHostPreflight(
            source=object(), context=context, reservations=host._reservations
        )
    with pytest.raises(ReleaseDenied):
        DisposableReadOnlyHostPreflight(source=host._source, context=context, reservations=object())
