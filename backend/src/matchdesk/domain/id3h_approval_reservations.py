"""Durable, one-use ID3H approval reservations for isolated CI qualification.

This SQLite implementation is NOT a production release-approval store. A future
trusted host must use separately approved, independently authenticated storage
and authorization before any actual migration or customer-provider activation.
"""

from __future__ import annotations

import os
import re
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

_APPROVAL_ID = re.compile(r"[a-f0-9]{32}\Z")


class DisposableApprovalReservationStore:
    """Reserve a synthetic approval once in a private persistent CI database.

    The caller owns the private directory. SQLite's BEGIN IMMEDIATE and UNIQUE
    index arbitrate competing threads, processes and connections atomically.
    Failed/ambiguous database operations never grant an approval to the caller.
    """

    def __init__(self, database_path: Path) -> None:
        """Reject insecure locations and initialise a private on-disk ledger.

        Keep the store within a caller-created, user-owned mode-0700 directory.
        Never accept an attacker-writable path or an in-memory database.
        """
        if not isinstance(database_path, Path) or not database_path.is_absolute():
            raise ValueError("A private absolute CI database path is required")
        if database_path.name in ("", ".", "..") or database_path.is_symlink():
            raise ValueError("A regular CI database file is required")
        parent = database_path.parent
        attributes = parent.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(attributes.st_mode)
            or attributes.st_uid != os.geteuid()
            or stat.S_IMODE(attributes.st_mode) & 0o077
        ):
            raise PermissionError("A private operator-owned directory is required")
        self._path = database_path
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        try:
            descriptor = os.open(self._path, flags, 0o600)
        except FileExistsError:
            descriptor = None
        if descriptor is not None:
            os.close(descriptor)
        attributes = self._path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(attributes.st_mode)
            or attributes.st_uid != os.geteuid()
            or stat.S_IMODE(attributes.st_mode) != 0o600
            or attributes.st_nlink != 1
        ):
            raise PermissionError("The CI ledger file is not private")
        with closing(self._connect()) as connection:
            # BEGIN IMMEDIATE serializes competing table creation and reserves.
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS id3h_approval_reservations ("
                    " approval_id TEXT PRIMARY KEY NOT NULL,"
                    " expires_at INTEGER NOT NULL CHECK (expires_at > 0)"
                    ") WITHOUT ROWID"
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def _connect(self) -> sqlite3.Connection:
        """Open a fresh isolated connection for each atomic reservation."""
        return sqlite3.connect(self._path, timeout=5.0, isolation_level=None)

    def reserve_once(self, approval_id: str, expires_at: int) -> bool:
        """Atomically persist a new ID, denying duplicates even after reopening.

        Never prune used identifiers: expiry limits signature use but must not
        permit a previously consumed approval to be reused later.
        """
        if (
            type(approval_id) is not str
            or _APPROVAL_ID.fullmatch(approval_id) is None
            or type(expires_at) is not int
            or expires_at <= 0
        ):
            raise ValueError("Invalid CI approval reservation scope")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                result = connection.execute(
                    "INSERT INTO id3h_approval_reservations (approval_id, expires_at) "
                    "VALUES (?, ?) ON CONFLICT(approval_id) DO NOTHING",
                    (approval_id, expires_at),
                )
                inserted = result.rowcount == 1
                connection.commit()
                return inserted
            except BaseException:
                connection.rollback()
                raise
