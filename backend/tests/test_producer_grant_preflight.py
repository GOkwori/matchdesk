"""Offline tests for non-minting signed producer confirmation preflight."""

import base64
import hashlib
import json
from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from jwt import PyJWK
from matchdesk.domain.postgres_producer_store import _audit_digest, _case_json
from matchdesk.domain.producer_commands import HostVerifiedActor, open_producer_case
from matchdesk.domain.producer_grant_preflight import (
    GrantPreflightDenied,
    qualify_producer_grant_preflight,
)
from matchdesk.domain.producer_identity import ProducerIdentityPolicy, StaticTrustedKeys
from matchdesk.domain.producer_preview import build_producer_desk_preview

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
CLIENT = "matchdesk-grant-ci"
NOW = datetime.now(timezone.utc)
TIMESTAMP = int(NOW.timestamp())


class Grants:
    """Host-owned grants never come from JWT roles or a request payload."""

    def resolve(self, *, tenant_id, subject):
        """Resolve only the synthetic actor's exact tenant and session."""
        if (tenant_id, subject) == (TENANT, "ci-producer"):
            return frozenset({"producer"}), frozenset({"demo-preview-only"})
        return None


class Digest:
    """Only a fake digest provider, not PostgreSQL canonicalization evidence."""

    def digest_case_jsonb(self, case_json: str) -> str:
        """Return deterministic 64-hex for scope comparison in unit tests."""
        return hashlib.sha256(case_json.encode()).hexdigest()


def _fixture():
    """Build a signed token, exact case, signature and pinned test authorities."""
    producer = HostVerifiedActor(
        subject="ci-producer",
        tenant_id=TENANT,
        issuer=ISSUER,
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )
    preview = build_producer_desk_preview()
    case = open_producer_case(
        actor=producer,
        tenant_id=TENANT,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def encode_number(number):
        """Convert an unsigned RSA public integer to a JWK field."""
        raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(raw).decode()

    public = PyJWK.from_dict(
        {
            "kty": "RSA", "alg": "RS256", "use": "sig", "kid": "ci-kid",
            "n": encode_number(numbers.n), "e": encode_number(numbers.e),
        }
    )
    policy = ProducerIdentityPolicy(
        issuer=ISSUER, tenant_id=TENANT, audience="api://matchdesk-ci",
        client_ids=frozenset({CLIENT}), required_auth_context="c1",
        max_token_age_seconds=300,
    )
    claims = {
        "iss": ISSUER, "aud": policy.audience, "tid": TENANT,
        "sub": producer.subject, "azp": CLIENT, "scp": policy.required_scope,
        "acrs": ["c1"], "iat": TIMESTAMP - 10,
        "nbf": TIMESTAMP - 10, "exp": TIMESTAMP + 100,
    }
    token = jwt.encode(claims, private, algorithm="RS256", headers={"kid": "ci-kid"})
    signing = ed25519.Ed25519PrivateKey.generate()
    human_claims = {
        "version": 1,
        "issuer": "matchdesk-trusted-producer-confirmation-v1",
        "audience": "matchdesk-producer-grant-issuer",
        "confirmation_id": "a" * 32,
        "confirmation_method": "custom-dialog-execution",
        "actor_id": producer.subject,
        "token_issuer": ISSUER,
        "tenant_id": TENANT,
        "session_id": case.output.session_id,
        "output_id": case.output.output_id,
        "action": "create",
        "expected_generation": 0,
        "authorized_case_sha256": Digest().digest_case_jsonb(_case_json(case)),
        "authorized_audit_digest": _audit_digest(case.review.audit),
        "issued_at": TIMESTAMP - 10,
        "not_before": TIMESTAMP - 10,
        "expires_at": TIMESTAMP + 60,
    }

    def envelope(modification=None, signing_key=None):
        """Sign controlled exact claims for positive and negative cases."""
        altered = dict(human_claims)
        if modification:
            altered.update(modification)
        body = json.dumps(
            altered, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode()
        signature = (signing_key or signing).sign(body)
        return json.dumps({
            "claims": altered,
            "signature": base64.urlsafe_b64encode(signature).decode().rstrip("="),
        })

    args = dict(
        access_token=token, policy=policy, keys=StaticTrustedKeys(
            ISSUER, {"ci-kid": public}
        ), entitlements=Grants(), case=case, action="create",
        expected_generation=0, confirmation_public_key=signing.public_key(),
        case_hash=Digest(), now=NOW,
    )
    return args, envelope, claims, private


def test_exact_signed_step_up_confirmation_returns_only_inert_preflight():
    """Valid evidence returns scope, not a usable grant or writer operation."""
    args, envelope, _, _ = _fixture()
    result = qualify_producer_grant_preflight(
        **args, signed_confirmation=envelope()
    )
    assert result.action == "create"
    assert result.expected_generation == 0
    assert result.authorized_audit_digest == _audit_digest(args["case"].review.audit)
    assert not hasattr(result, "grant_id")


@pytest.mark.parametrize(
    "changed",
    [
        {"actor_id": "forged-actor"},
        {"tenant_id": "other"},
        {"session_id": "other-session"},
        {"output_id": "other-output"},
        {"action": "approve"},
        {"expected_generation": 1},
        {"authorized_case_sha256": "d" * 64},
        {"authorized_audit_digest": "d" * 64},
        {"confirmation_id": "invalid"},
        {"expires_at": TIMESTAMP - 1},
        {"issued_at": TIMESTAMP + 30},
        {"confirmation_method": "system-dialog"},
    ],
)
def test_signed_but_out_of_scope_confirmation_is_denied(changed):
    """Even a genuine signature cannot authorize a different exact action."""
    args, envelope, _, _ = _fixture()
    with pytest.raises(GrantPreflightDenied):
        qualify_producer_grant_preflight(
            **args, signed_confirmation=envelope(changed)
        )


def test_untrusted_confirmation_signer_cannot_authorize_action():
    """A perfectly formed attacker-signed confirmation cannot pass."""
    args, envelope, _, _ = _fixture()
    with pytest.raises(GrantPreflightDenied):
        qualify_producer_grant_preflight(
            **args, signed_confirmation=envelope(
                signing_key=ed25519.Ed25519PrivateKey.generate()
            )
        )


def test_missing_authentication_context_denies_human_confirmation():
    """Signed human approval cannot replace missing signed Entra step-up."""
    args, envelope, claims, private = _fixture()
    without = dict(claims)
    without.pop("acrs")
    args["access_token"] = jwt.encode(
        without, private, algorithm="RS256", headers={"kid": "ci-kid"}
    )
    with pytest.raises(GrantPreflightDenied):
        qualify_producer_grant_preflight(
            **args, signed_confirmation=envelope()
        )


def test_read_only_policy_cannot_be_used_for_grant_issuance():
    """A read-only verifier cannot silently disable step-up for this gate."""
    args, envelope, _, _ = _fixture()
    args["policy"] = ProducerIdentityPolicy(
        issuer=ISSUER, tenant_id=TENANT, audience="api://matchdesk-ci",
        client_ids=frozenset({CLIENT}),
    )
    with pytest.raises(GrantPreflightDenied):
        qualify_producer_grant_preflight(
            **args, signed_confirmation=envelope()
        )


def test_untrusted_digest_provider_result_and_duplicate_json_are_denied():
    """A malformed digest or duplicate envelope keys cannot become authority."""
    args, envelope, _, _ = _fixture()

    class BadDigest:
        """Intentionally invalid host-provided digest stub."""

        def digest_case_jsonb(self, case_json):
            """Return an untrusted non-SHA placeholder."""
            return "not-a-sha"

    args["case_hash"] = BadDigest()
    with pytest.raises(GrantPreflightDenied):
        qualify_producer_grant_preflight(
            **args, signed_confirmation=envelope()
        )
    args["case_hash"] = Digest()
    with pytest.raises(GrantPreflightDenied):
        qualify_producer_grant_preflight(
            **args, signed_confirmation=envelope().replace(
                '{"claims":', '{"claims":{},"claims":', 1
            )
        )
