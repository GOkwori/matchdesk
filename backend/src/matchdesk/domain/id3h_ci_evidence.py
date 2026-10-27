"""Re-observe private, disposable CI evidence bytes before approval qualification.

This does NOT verify historical migration provenance, a real tenant or database,
operator identity, backup restorability, or consent to incur cloud costs. It only
prevents the offline host from relying solely on digests copied from a signed
approval. A separate trusted execution host is needed for any live release.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from matchdesk.domain.id3h_qualification_host import TrustedCIHostSource
from matchdesk.domain.id3h_release_approval import (
    DENIAL,
    ObservedReleaseFacts,
    ReleaseDenied,
)

_MAX_EVIDENCE_BYTES = 1_048_576
# Fixed names prevent an approval or caller claim from selecting arbitrary files.
_EVIDENCE_FILES = (
    ("tenant_fingerprint", "tenant.identity"),
    ("database_fingerprint", "database.identity"),
    ("migration_sha256", "migration.sql"),
    ("historical_evidence_sha256", "historical.json"),
    ("backup_evidence_sha256", "backup.json"),
    ("catalog_evidence_sha256", "catalog.json"),
    ("cost_decision_sha256", "cost.json"),
)


@dataclass(frozen=True, slots=True)
class CIFileEvidenceSnapshot:
    """Content digests observed from CI-only private files, not live attestations."""

    tenant_fingerprint: str
    database_fingerprint: str
    migration_sha256: str
    historical_evidence_sha256: str
    backup_evidence_sha256: str
    catalog_evidence_sha256: str
    cost_decision_sha256: str


class DisposableCIFileEvidenceReader:
    """Fingerprint fixed evidence files without trusting token-provided paths.

    Parent and file paths must be owned by this OS identity and inaccessible
    to other users; all reads are O_NOFOLLOW and checked against the original
    directory inode. Two identical scans reject ordinary concurrent edits.
    Neither mode checks nor two scans make a historical record authoritative.
    """

    def __init__(self, root: Path) -> None:
        """Pin the private fixture-directory identity before reading any content."""
        if not isinstance(root, Path) or not root.is_absolute():
            raise ReleaseDenied(DENIAL)
        self._root = root
        self._identity: tuple[int, int] | None = None
        fd = self._open_dir()
        os.close(fd)

    def _open_dir(self) -> int:
        """Open only the original, private directory without following symlinks."""
        try:
            fd = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            attributes = os.fstat(fd)
            if (
                not stat.S_ISDIR(attributes.st_mode)
                or attributes.st_uid != os.geteuid()
                or stat.S_IMODE(attributes.st_mode) & 0o077
                or (
                    self._identity is not None
                    and (attributes.st_dev, attributes.st_ino) != self._identity
                )
            ):
                os.close(fd)
                raise ReleaseDenied(DENIAL)
            if self._identity is None:
                self._identity = (attributes.st_dev, attributes.st_ino)
            return fd
        except OSError:
            raise ReleaseDenied(DENIAL) from None

    @staticmethod
    def _digest_file(directory_fd: int, name: str) -> str:
        """Hash one bounded regular file, checking mode, inode and mutation."""
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            try:
                initial = os.fstat(fd)
                if (
                    not stat.S_ISREG(initial.st_mode)
                    or initial.st_uid != os.geteuid()
                    or stat.S_IMODE(initial.st_mode) & 0o077
                    or initial.st_nlink != 1
                    or not 0 < initial.st_size <= _MAX_EVIDENCE_BYTES
                ):
                    raise ReleaseDenied(DENIAL)
                digest = hashlib.sha256()
                count = 0
                while count <= _MAX_EVIDENCE_BYTES:
                    piece = os.read(fd, min(65536, _MAX_EVIDENCE_BYTES + 1 - count))
                    if not piece:
                        break
                    count += len(piece)
                    digest.update(piece)
                final = os.fstat(fd)
                if count != initial.st_size or (
                    initial.st_dev,
                    initial.st_ino,
                    initial.st_size,
                    initial.st_mtime_ns,
                    initial.st_ctime_ns,
                ) != (
                    final.st_dev,
                    final.st_ino,
                    final.st_size,
                    final.st_mtime_ns,
                    final.st_ctime_ns,
                ):
                    raise ReleaseDenied(DENIAL)
                return digest.hexdigest()
            finally:
                os.close(fd)
        except OSError:
            raise ReleaseDenied(DENIAL) from None

    def snapshot(self) -> CIFileEvidenceSnapshot:
        """Recompute every CI fixture digest twice to detect ordinary TOCTOU."""
        directory_fd = self._open_dir()
        try:
            first = {
                field: self._digest_file(directory_fd, name) for field, name in _EVIDENCE_FILES
            }
            second = {
                field: self._digest_file(directory_fd, name) for field, name in _EVIDENCE_FILES
            }
            if first != second:
                raise ReleaseDenied(DENIAL)
            return CIFileEvidenceSnapshot(**second)
        finally:
            os.close(directory_fd)


class EvidenceBoundCIHostSource:
    """Wrap a host-owned source with independent CI file-content observations.

    The delegate still supplies actor/key/clock and must be backed by genuine
    trust services in a future release; this adapter does not authenticate it.
    """

    def __init__(
        self, *, delegate: TrustedCIHostSource, reader: DisposableCIFileEvidenceReader
    ) -> None:
        """Require the exact offline reader rather than a fake digest acceptor."""
        if type(reader) is not DisposableCIFileEvidenceReader:
            raise ReleaseDenied(DENIAL)
        self._delegate = delegate
        self._reader = reader

    def verified_actor(self) -> str:
        """Delegate actor authentication to the enclosing trusted host."""
        return self._delegate.verified_actor()

    def observe_release(self) -> ObservedReleaseFacts:
        """Require current evidence bytes to match all host-observed digests."""
        observed = self._delegate.observe_release()
        if type(observed) is not ObservedReleaseFacts:
            raise ReleaseDenied(DENIAL)
        current = self._reader.snapshot()
        for field, _ in _EVIDENCE_FILES:
            expected = getattr(observed, field)
            actual = getattr(current, field)
            if type(expected) is not str or not hmac.compare_digest(expected, actual):
                raise ReleaseDenied(DENIAL)
        return observed

    def approval_key(self) -> Ed25519PublicKey:
        """Delegate pinned key discovery; never take the key from the token."""
        return self._delegate.approval_key()

    def utcnow(self) -> datetime:
        """Delegate the verified wall clock to the trusted host."""
        return self._delegate.utcnow()
