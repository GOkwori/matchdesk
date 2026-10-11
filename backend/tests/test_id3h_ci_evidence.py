"""Negative-case checks for private, read-only ID3H CI evidence."""

import hashlib
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from matchdesk.domain.id3h_ci_evidence import (
    DisposableCIFileEvidenceReader,
    EvidenceBoundCIHostSource,
)
from matchdesk.domain.id3h_release_approval import ReleaseDenied
from test_id3h_qualification_host import StubbedCITrust

NAMES = (
    "tenant.identity",
    "database.identity",
    "migration.sql",
    "historical.json",
    "backup.json",
    "catalog.json",
    "cost.json",
)


def fixtures(root: Path) -> Path:
    """Create seven private, synthetic evidence files in an isolated directory."""
    directory = root / "evidence"
    directory.mkdir(mode=0o700)
    for name in NAMES:
        path = directory / name
        path.write_bytes(name.encode("ascii"))
        path.chmod(0o600)
    return directory


def test_private_evidence_digests(tmp_path: Path) -> None:
    """Each digest must represent the file bytes rather than a caller assertion."""
    directory = fixtures(tmp_path)
    observed = DisposableCIFileEvidenceReader(directory).snapshot()
    assert observed.migration_sha256 == hashlib.sha256(b"migration.sql").hexdigest()
    assert observed.backup_evidence_sha256 == hashlib.sha256(b"backup.json").hexdigest()


def test_changed_evidence_denied(tmp_path: Path) -> None:
    """An altered file cannot satisfy a previously observed release fingerprint."""
    directory = fixtures(tmp_path)
    reader = DisposableCIFileEvidenceReader(directory)
    source = StubbedCITrust(Ed25519PrivateKey.generate())
    from dataclasses import replace
    from test_id3h_qualification_host import FACTS

    observed = reader.snapshot()
    source.facts = replace(
        FACTS, **{name: getattr(observed, name) for name in observed.__dataclass_fields__}
    )
    bound = EvidenceBoundCIHostSource(delegate=source, reader=reader)
    assert bound.observe_release() == source.facts
    (directory / "backup.json").write_bytes(b"changed")
    with pytest.raises(ReleaseDenied):
        bound.observe_release()


def test_missing_or_linked_evidence_denied(tmp_path: Path) -> None:
    """Missing and symbolic-link fixtures must fail closed."""
    directory = fixtures(tmp_path)
    reader = DisposableCIFileEvidenceReader(directory)
    (directory / "catalog.json").unlink()
    with pytest.raises(ReleaseDenied):
        reader.snapshot()
    (directory / "catalog.json").symlink_to(directory / "backup.json")
    with pytest.raises(ReleaseDenied):
        reader.snapshot()


def test_replaced_directory_denied(tmp_path: Path) -> None:
    """Rebinding the evidence directory after reader construction is forbidden."""
    directory = fixtures(tmp_path)
    reader = DisposableCIFileEvidenceReader(directory)
    directory.rename(tmp_path / "old-evidence")
    directory.mkdir(mode=0o700)
    with pytest.raises(ReleaseDenied):
        reader.snapshot()


@pytest.mark.parametrize("mode", [0o644, 0o666])
def test_public_evidence_denied(tmp_path: Path, mode: int) -> None:
    """World-readable or writable fixtures cannot qualify."""
    directory = fixtures(tmp_path)
    (directory / "migration.sql").chmod(mode)
    with pytest.raises(ReleaseDenied):
        DisposableCIFileEvidenceReader(directory).snapshot()


def test_untrusted_reader_denied(tmp_path: Path) -> None:
    """A caller-provided fake digest source cannot replace the pinned reader."""
    source = StubbedCITrust(Ed25519PrivateKey.generate())
    with pytest.raises(ReleaseDenied):
        EvidenceBoundCIHostSource(delegate=source, reader=object())


def test_empty_evidence_denied(tmp_path: Path) -> None:
    """Empty evidence is not a valid historical or backup attestation."""
    directory = fixtures(tmp_path)
    (directory / "historical.json").write_bytes(b"")
    with pytest.raises(ReleaseDenied):
        DisposableCIFileEvidenceReader(directory).snapshot()
