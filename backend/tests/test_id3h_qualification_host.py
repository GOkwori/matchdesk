"""Offline ID3H host boundary: actor/target drift never authorizes execution."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from matchdesk.domain.id3h_approval_reservations import DisposableApprovalReservationStore
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
FACTS = ObservedReleaseFacts(
    action=ACTION,
    environment=ENVIRONMENT,
    operator_id="ci-workload:alice",
    tenant_fingerprint="1" * 64,
    database_fingerprint="2" * 64,
    source_commit="3" * 40,
    migration_sha256="4" * 64,
    historical_evidence_sha256="5" * 64,
    backup_evidence_sha256="6" * 64,
    catalog_evidence_sha256="7" * 64,
    cost_decision_sha256="8" * 64,
    change_id="ci-change:alpha",
)


class StubbedCITrust:
    """Synthetic host dependencies, NOT a genuine authentication provider."""

    def __init__(self, key: Ed25519PrivateKey) -> None:
        """Start with stable actor and observed state for the CI simulation."""
        self.actor: object = FACTS.operator_id
        self.facts: object = FACTS
        self.key = key
        self.fail = False
        self.observations = 0
        self.drift_after_reservation = False

    def verified_actor(self) -> object:
        """Return synthetic operator identity or simulate identity-provider outage."""
        if self.fail:
            raise RuntimeError("private operator directory unavailable")
        return self.actor

    def observe_release(self) -> object:
        """Read the test observation; optionally change it after consumption."""
        self.observations += 1
        if self.drift_after_reservation and self.observations > 1:
            return replace(FACTS, database_fingerprint="9" * 64)
        return self.facts

    def approval_key(self):
        """Return a synthetic pinned verification key."""
        return self.key.public_key()

    def utcnow(self) -> datetime:
        """Return a synthetic fixed timestamp for the replay test."""
        return NOW


def envelope(key: Ed25519PrivateKey) -> str:
    """Sign a bounded disposable-only approval with an ephemeral key."""
    fields: dict[str, object] = {
        "version": 1,
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "approval_id": "a" * 32,
        "reviewer_id": "human-reviewer:1",
        "issued_at": 1_800_000_000,
        "not_before": 1_800_000_000,
        "expires_at": 1_800_000_300,
        **{field: getattr(FACTS, field) for field in FACTS.__dataclass_fields__},
    }
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    signature = base64.urlsafe_b64encode(key.sign(canonical.encode("utf-8"))).decode().rstrip("=")
    return json.dumps({"claims": fields, "signature": signature})


def host(tmp_path: Path, source: StubbedCITrust) -> DisposableApprovalQualificationHost:
    """Build a CI-only policy boundary with its own file-backed reservation."""
    return DisposableApprovalQualificationHost(
        source=source,
        reservations=DisposableApprovalReservationStore(tmp_path / "approval.sqlite3"),
    )


def test_qualified_approval_is_not_an_execution_grant(tmp_path: Path) -> None:
    """The host returns a durable offline receipt but cannot deploy or migrate."""
    key = Ed25519PrivateKey.generate()
    signed = envelope(key)
    receipt = host(tmp_path, StubbedCITrust(key)).qualify(signed)
    assert receipt.approval_id == "a" * 32
    assert receipt.execution_authorized is False
    assert receipt.environment == ENVIRONMENT
    with pytest.raises(ReleaseDenied):
        host(tmp_path, StubbedCITrust(key)).qualify(signed)


def test_actor_mismatch_is_denied_without_consuming_approval(tmp_path: Path) -> None:
    """An actor asserted by a caller cannot substitute for the host's actor."""
    key = Ed25519PrivateKey.generate()
    source = StubbedCITrust(key)
    source.actor = "ci-workload:bob"
    with pytest.raises(ReleaseDenied):
        host(tmp_path, source).qualify(envelope(key))
    source.actor = FACTS.operator_id
    assert host(tmp_path, source).qualify(envelope(key)).approval_id == "a" * 32


def test_production_or_untrusted_facts_are_denied(tmp_path: Path) -> None:
    """No CI signature provides a production or forged-target authorization."""
    key = Ed25519PrivateKey.generate()
    source = StubbedCITrust(key)
    source.facts = replace(FACTS, environment="production")
    with pytest.raises(ReleaseDenied):
        host(tmp_path, source).qualify(envelope(key))
    source.facts = {"operator_id": FACTS.operator_id}
    with pytest.raises(ReleaseDenied):
        host(tmp_path, source).qualify(envelope(key))


def test_host_outage_fails_closed(tmp_path: Path) -> None:
    """Loss of externally provided actor authority never permits a migration."""
    key = Ed25519PrivateKey.generate()
    source = StubbedCITrust(key)
    source.fail = True
    with pytest.raises(ReleaseDenied, match="qualification approval denied"):
        host(tmp_path, source).qualify(envelope(key))


def test_observed_target_change_after_reservation_denies(tmp_path: Path) -> None:
    """If the target changes mid-review, the consumed ID is not reusable."""
    key = Ed25519PrivateKey.generate()
    source = StubbedCITrust(key)
    source.drift_after_reservation = True
    with pytest.raises(ReleaseDenied):
        host(tmp_path, source).qualify(envelope(key))
    source.drift_after_reservation = False
    with pytest.raises(ReleaseDenied):
        host(tmp_path, source).qualify(envelope(key))


def test_caller_cannot_replace_durable_store_with_an_accept_all_mock() -> None:
    """An in-memory or caller-owned reservation implementation is not accepted."""

    class ForgedStore:
        """Simulate an always-approve store with no durable state."""

        def reserve_once(self, approval_id: str, expires_at: int) -> bool:
            """Incorrectly claim that every grant was reserved."""
            del approval_id, expires_at
            return True

    key = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="approved disposable CI reservation store"):
        DisposableApprovalQualificationHost(source=StubbedCITrust(key), reservations=ForgedStore())


def test_actor_change_after_reservation_consumes_but_denies(tmp_path: Path) -> None:
    """If operator identity changes during qualification the grant stays spent."""
    key = Ed25519PrivateKey.generate()
    source = StubbedCITrust(key)
    original_verified_actor = source.verified_actor
    calls = 0

    def changed_actor() -> str:
        """Simulate a revoked workload identity after durable consumption."""
        nonlocal calls
        calls += 1
        return original_verified_actor() if calls == 1 else "ci-workload:bob"

    source.verified_actor = changed_actor
    signed = envelope(key)
    with pytest.raises(ReleaseDenied):
        host(tmp_path, source).qualify(signed)
    source.verified_actor = original_verified_actor
    with pytest.raises(ReleaseDenied):
        host(tmp_path, source).qualify(signed)


def test_untrusted_signature_key_provider_outage_denied(tmp_path: Path) -> None:
    """Loss of the independently pinned approval key does not permit qualification."""
    key = Ed25519PrivateKey.generate()
    source = StubbedCITrust(key)

    def unavailable_key() -> None:
        """Simulate an approval-key provider outage."""
        raise RuntimeError("private approval authority unavailable")

    source.approval_key = unavailable_key
    with pytest.raises(ReleaseDenied, match="qualification approval denied"):
        host(tmp_path, source).qualify(envelope(key))


def test_competing_offline_hosts_reserve_one_signed_approval(tmp_path: Path) -> None:
    """Independent host instances must share one durable replay boundary."""
    key = Ed25519PrivateKey.generate()
    source = StubbedCITrust(key)
    signed = envelope(key)

    def attempt(_: int) -> bool:
        """Return whether this isolated offline host got a test-only receipt."""
        try:
            receipt = host(tmp_path, source).qualify(signed)
            assert receipt.execution_authorized is False
            return True
        except ReleaseDenied:
            return False

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(attempt, range(12))) == 1
