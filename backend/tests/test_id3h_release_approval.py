"""Offline, ephemeral-keys-only acceptance of the ID3H release grant contract."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from matchdesk.domain.id3h_release_approval import (
    ACTION,
    AUDIENCE,
    ENVIRONMENT,
    ISSUER,
    ObservedReleaseFacts,
    ReleaseDenied,
    reserve_disposable_release_approval,
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


class ReservationStore:
    """Ephemeral test double; the real trusted host must own its durable store."""

    def __init__(self) -> None:
        """Seed an empty store with an atomic lock for concurrency tests."""
        self.lock = Lock()
        self.used: set[str] = set()
        self.fail = False

    def reserve_once(self, approval_id: str, expires_at: int) -> bool:
        """Reserve an ID exactly once, irrespective of concurrent callers."""
        assert expires_at == 1_800_000_300
        with self.lock:
            if self.fail:
                raise RuntimeError("backend unreachable")
            if approval_id in self.used:
                return False
            self.used.add(approval_id)
            return True


def claims(facts: ObservedReleaseFacts = FACTS) -> dict[str, object]:
    """Create synthetic approval claims without production actor credentials."""
    return {
        "version": 1,
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "approval_id": "a" * 32,
        "reviewer_id": "human-reviewer:1",
        "issued_at": 1_800_000_000,
        "not_before": 1_800_000_000,
        "expires_at": 1_800_000_300,
        **{field: getattr(facts, field) for field in facts.__dataclass_fields__},
    }


def signed(key: Ed25519PrivateKey, payload: dict[str, object]) -> str:
    """Sign deterministic JSON with a disposable test key generated in memory."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    signature = base64.urlsafe_b64encode(key.sign(canonical.encode("utf-8"))).decode().rstrip("=")
    return json.dumps({"claims": payload, "signature": signature})


def verify(
    envelope: str,
    key: Ed25519PrivateKey,
    store: ReservationStore | None = None,
    facts: ObservedReleaseFacts = FACTS,
    now: datetime = NOW,
) -> str:
    """Call the policy with isolated test host facts and a test reservation."""
    return reserve_disposable_release_approval(
        envelope,
        observed=facts,
        trusted_public_key=key.public_key(),
        reservation_store=store if store is not None else ReservationStore(),
        now=now,
    )


def test_exact_synthetic_signed_grant_is_reserved_once() -> None:
    """A valid CI-only approval is single-use, not an execution permission."""
    key, store = Ed25519PrivateKey.generate(), ReservationStore()
    envelope = signed(key, claims())
    assert verify(envelope, key, store) == "a" * 32
    with pytest.raises(ReleaseDenied):
        verify(envelope, key, store)
    assert store.used == {"a" * 32}


@pytest.mark.parametrize(
    "field",
    [
        "operator_id",
        "tenant_fingerprint",
        "database_fingerprint",
        "source_commit",
        "migration_sha256",
        "historical_evidence_sha256",
        "backup_evidence_sha256",
        "catalog_evidence_sha256",
        "cost_decision_sha256",
        "change_id",
    ],
)
def test_scope_substitution_is_denied(field: str) -> None:
    """Approvals must bind every target, code, actor, cost and evidence input."""
    key = Ed25519PrivateKey.generate()
    fake = claims()
    fake[field] = "untrusted-field"
    with pytest.raises(ReleaseDenied):
        verify(signed(key, fake), key)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("action", "id3h.run-original-backfill"),
        ("issuer", "another-authority"),
        ("audience", "arbitrary-agent"),
        ("reviewer_id", FACTS.operator_id),
        ("reviewer_id", ""),
        ("approval_id", "not-an-id"),
        ("version", 2),
        ("issued_at", 1_800_000_200),
        ("not_before", 1_800_000_200),
        ("expires_at", 1_800_001_000),
        ("expires_at", True),
    ],
)
def test_malformed_or_unauthorized_claims_are_denied(field: str, value: object) -> None:
    """Unsupported privilege, actor, realm, version and time all fail closed."""
    key = Ed25519PrivateKey.generate()
    bad = claims()
    bad[field] = value
    with pytest.raises(ReleaseDenied):
        verify(signed(key, bad), key)


def test_prod_host_facts_are_blocked_even_with_matching_signature() -> None:
    """No signature issued for a synthetic environment permits production use."""
    key = Ed25519PrivateKey.generate()
    production = replace(FACTS, environment="production")
    with pytest.raises(ReleaseDenied):
        verify(signed(key, claims(production)), key, facts=production)


def test_missing_untrusted_or_expired_grant_is_denied() -> None:
    """A valid signature cannot be reused under another key or after expiry."""
    key = Ed25519PrivateKey.generate()
    approval = signed(key, claims())
    with pytest.raises(ReleaseDenied):
        verify(approval, Ed25519PrivateKey.generate())
    with pytest.raises(ReleaseDenied):
        verify(approval, key, now=datetime.fromtimestamp(1_800_000_300, tz=timezone.utc))
    with pytest.raises(ReleaseDenied):
        verify("", key)


def test_payload_change_unknown_field_and_duplicate_json_are_denied() -> None:
    """Strict JSON, schema and Ed25519 verification reject token substitution."""
    key = Ed25519PrivateKey.generate()
    valid = signed(key, claims())
    token = json.loads(valid)
    token["claims"]["database_fingerprint"] = "9" * 64
    with pytest.raises(ReleaseDenied):
        verify(json.dumps(token), key)
    altered = claims()
    altered["admin"] = True
    with pytest.raises(ReleaseDenied):
        verify(signed(key, altered), key)
    duplicate = valid.replace('"signature":', '"claims": {}, "signature":')
    with pytest.raises(ReleaseDenied):
        verify(duplicate, key)
    with pytest.raises(ReleaseDenied):
        verify(valid + " " * 9000, key)


def test_invalid_host_evidence_and_clock_are_denied() -> None:
    """A verifier is not a replacement for trustworthy upstream observations."""
    key, approval = Ed25519PrivateKey.generate(), claims()
    with pytest.raises(ReleaseDenied):
        verify(signed(key, approval), key, facts=replace(FACTS, source_commit="UPPER"))
    with pytest.raises(ReleaseDenied):
        verify(signed(key, approval), key, now=datetime(2026, 1, 1))


def test_reservation_outage_never_becomes_success() -> None:
    """An unavailable atomic-grant store must fail closed without leaking errors."""
    key, store = Ed25519PrivateKey.generate(), ReservationStore()
    store.fail = True
    with pytest.raises(ReleaseDenied, match="qualification approval denied"):
        verify(signed(key, claims()), key, store)


def test_concurrent_reservations_allow_exactly_one() -> None:
    """Two callers racing with the same grant cannot both reserve it."""
    key, store = Ed25519PrivateKey.generate(), ReservationStore()
    approval = signed(key, claims())

    def attempt(_: int) -> bool:
        """Return whether a synthetic trusted host obtained one reservation."""
        try:
            verify(approval, key, store)
            return True
        except ReleaseDenied:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(20))) == 1
