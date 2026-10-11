"""Enforce the development-only, fail-closed MatchDesk customer release baseline.

This structural guard does not authorize any future release. A reviewed,
separately approved patch must deliberately change it before live activation.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shipped_customer_authentication_remains_unmounted() -> None:
    """Do not expose optional customer session or OIDC routers by default."""
    source = (ROOT / "backend/src/matchdesk/api/app.py").read_text(encoding="utf-8")
    assert "app = create_app()" in source
    assert "app = create_app(customer_" not in source
    assert "customer_session_router: APIRouter | None = None" in source
    assert "customer_oidc_router: APIRouter | None = None" in source


def test_no_implicit_deployment_and_no_migration_replacement() -> None:
    """Require an explicit new release decision for any change to live controls."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'BLOCKED: deployment implementation' in makefile
    assert "@exit 2" in makefile
    original = ROOT / "backend/postgres/migrations/005_customer_account_revocation.sql"
    review = ROOT / "qualification/id3g/005_customer_account_revocation.sql"
    assert original.read_bytes() == review.read_bytes()
    assert "UPDATE public.matchdesk_customer_sessions\nSET revoked = TRUE" in original.read_text(
        encoding="utf-8"
    )


def test_release_runbook_remains_explicitly_blocked() -> None:
    """CI passing cannot replace external historical proof or human approval."""
    runbook = (ROOT / "docs/operations/id3h-controlled-release.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "LIVE EXECUTION BLOCKED",
        "Historical provenance",
        "Human decision",
    ):
        assert required in runbook
