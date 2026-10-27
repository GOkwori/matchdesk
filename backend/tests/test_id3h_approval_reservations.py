"""Exercise durable single-use approval reservations on disposable SQLite."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from matchdesk.domain.id3h_approval_reservations import DisposableApprovalReservationStore

APPROVAL = "a" * 32
EXPIRY = 1_800_000_300


def new_store(tmp_path: Path) -> DisposableApprovalReservationStore:
    """Open the same privately stored ledger using a fresh connection."""
    return DisposableApprovalReservationStore(tmp_path / "approval-ledger.sqlite3")


def test_atomic_reservation_survives_reopening(tmp_path: Path) -> None:
    """Consumed approvals must stay consumed when the store is reopened."""
    assert new_store(tmp_path).reserve_once(APPROVAL, EXPIRY) is True
    assert new_store(tmp_path).reserve_once(APPROVAL, EXPIRY) is False
    assert new_store(tmp_path).reserve_once("b" * 32, EXPIRY) is True
    assert (tmp_path / "approval-ledger.sqlite3").stat().st_mode & 0o777 == 0o600


def test_cross_connection_race_allows_one_commit(tmp_path: Path) -> None:
    """Two independent database connections cannot reserve the same grant."""

    def attempt(_: int) -> bool:
        """Open a new private ledger handle for each simulated worker."""
        return new_store(tmp_path).reserve_once(APPROVAL, EXPIRY)

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(20))) == 1
    assert new_store(tmp_path).reserve_once(APPROVAL, EXPIRY) is False


@pytest.mark.parametrize(
    ("approval", "expiry"),
    [
        ("wrong", EXPIRY),
        ("A" * 32, EXPIRY),
        ("x" * 32, EXPIRY),
        (APPROVAL, 0),
        (APPROVAL, True),
        (None, EXPIRY),
    ],
)
def test_invalid_reservation_is_not_accepted(
    tmp_path: Path, approval: object, expiry: object
) -> None:
    """Invalid identifiers and expiration fields must never mutate the store."""
    with pytest.raises(ValueError):
        new_store(tmp_path).reserve_once(approval, expiry)
    assert new_store(tmp_path).reserve_once(APPROVAL, EXPIRY) is True


def test_untrusted_location_or_symlink_is_rejected(tmp_path: Path) -> None:
    """Refuse redirecting approval storage through untrusted locations."""
    path = tmp_path / "ledger.sqlite3"
    path.symlink_to(tmp_path / "destination.sqlite3")
    with pytest.raises(ValueError):
        DisposableApprovalReservationStore(path)
    public = tmp_path / "public"
    public.mkdir(mode=0o777)
    public.chmod(0o777)
    with pytest.raises(PermissionError):
        DisposableApprovalReservationStore(public / "ledger.sqlite3")
    with pytest.raises(ValueError):
        DisposableApprovalReservationStore(Path("relative.sqlite3"))


def test_ledger_error_never_returns_success(tmp_path: Path) -> None:
    """Database corruption may error but must not grant a reservation."""
    path = tmp_path / "approval-ledger.sqlite3"
    store = new_store(tmp_path)
    path.write_bytes(b"not a database")
    with pytest.raises(Exception):
        store.reserve_once(APPROVAL, EXPIRY)
