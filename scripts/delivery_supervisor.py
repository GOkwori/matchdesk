#!/usr/bin/env python3
"""Durable, fail-closed MatchDesk delivery supervisor.

This coordinator maintains a restartable work queue. It does not run an AI
coding agent, mutate GitHub, approve changes, publish or deploy. Its claim
operation is an internal reservation, not evidence that work is executing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

from delivery_orchestrator import DEFAULT_MANIFEST, validate_manifest

MAX_ATTEMPTS = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  issue INTEGER NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('engineering','human')),
  status TEXT NOT NULL CHECK(status IN
    ('QUEUED','LEASED','WAITING_INPUT','BLOCKED','REVIEW_REQUIRED','VERIFIED')),
  owner TEXT,
  lease_until INTEGER,
  attempts INTEGER NOT NULL DEFAULT 0,
  receipt TEXT,
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  fingerprint TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  detail TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_deliveries (
  fingerprint TEXT PRIMARY KEY REFERENCES alerts(fingerprint),
  comment_id INTEGER NOT NULL CHECK(comment_id > 0),
  delivered_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_send_claims (
  fingerprint TEXT PRIMARY KEY REFERENCES alerts(fingerprint),
  claimed_at INTEGER NOT NULL
);
"""


class Supervisor:
    """Own an exclusively transactional local queue and evidence ledger."""

    def __init__(self, db: Path, manifest: dict, *, clock: int | None = None) -> None:
        """Open or create persistent storage and validate the task graph."""
        self.manifest = validate_manifest(manifest)
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db, timeout=15, isolation_level=None)
        self.conn.execute("PRAGMA busy_timeout=15000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.now = int(time.time()) if clock is None else clock
        self._init_tasks()

    def _init_tasks(self) -> None:
        """Import new declared tasks without resetting prior work receipts."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            for task in self.manifest["tasks"]:
                status = "WAITING_INPUT" if task["kind"] == "human" else "QUEUED"
                self.conn.execute(
                    """INSERT OR IGNORE INTO tasks
                    (id,issue,kind,status,updated_at) VALUES (?,?,?,?,?)""",
                    (task["id"], task["issue"], task["kind"], status, self.now),
                )
                row = self.conn.execute(
                    "SELECT issue, kind FROM tasks WHERE id=?", (task["id"],)
                ).fetchone()
                if row != (task["issue"], task["kind"]):
                    raise ValueError(
                        "Persisted task authority changed; manual reconciliation required"
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def recover(self) -> int:
        """Recover expired leases, escalating exhausted retries atomically."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            expired = self.conn.execute(
                """SELECT id, attempts FROM tasks
                WHERE status='LEASED' AND lease_until<=?""",
                (self.now,),
            ).fetchall()
            for task_id, attempts in expired:
                exhausted = attempts >= MAX_ATTEMPTS
                self.conn.execute(
                    """UPDATE tasks SET status=?, owner=NULL, lease_until=NULL,
                    updated_at=? WHERE id=?""",
                    ("BLOCKED" if exhausted else "QUEUED", self.now, task_id),
                )
                if exhausted:
                    self._queue_alert(task_id, "Worker lease expired after three attempts.")
            self.conn.commit()
            return len(expired)
        except Exception:
            self.conn.rollback()
            raise

    def claim(self, worker: str, *, max_attempts: int = 3, lease_seconds: int = 600) -> str | None:
        """Reserve one dependency-cleared engineering task; no worker is launched."""
        if (
            not worker
            or len(worker) > 80
            or max_attempts != MAX_ATTEMPTS
            or not 30 <= lease_seconds <= 3600
        ):
            raise ValueError("Invalid bounded worker claim")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            active = self.conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status='LEASED'"
            ).fetchone()[0]
            if active >= self.manifest["max_parallel"]:
                self.conn.commit()
                return None
            for task in self.manifest["tasks"]:
                if task["kind"] != "engineering":
                    continue
                row = self.conn.execute(
                    "SELECT status,attempts FROM tasks WHERE id=?", (task["id"],)
                ).fetchone()
                if row[0] != "QUEUED" or row[1] >= max_attempts:
                    continue
                if any(
                    self.conn.execute("SELECT status FROM tasks WHERE id=?", (dep,)).fetchone()
                    != ("VERIFIED",)
                    for dep in task["depends_on"]
                ):
                    continue
                self.conn.execute(
                    """UPDATE tasks SET status='LEASED',owner=?,lease_until=?,
                    attempts=attempts+1,updated_at=? WHERE id=?""",
                    (worker, self.now + lease_seconds, self.now, task["id"]),
                )
                self.conn.commit()
                return task["id"]
            self.conn.commit()
            return None
        except Exception:
            self.conn.rollback()
            raise

    def release(self, task_id: str, worker: str, state: str, *, receipt: str | None = None) -> None:
        """Checkpoint a review-only worker outcome, never acceptance or approval."""
        if state not in ("QUEUED", "BLOCKED", "REVIEW_REQUIRED"):
            raise ValueError("Cannot certify task by a worker result")
        if receipt is not None:
            if state != "REVIEW_REQUIRED" or not 1 <= len(receipt) <= 4096:
                raise ValueError("Only reviewed proposal outcomes may carry a bounded receipt")
            try:
                details = json.loads(receipt)
            except (ValueError, TypeError) as exc:
                raise ValueError("Malformed proposal receipt") from exc
            if (
                type(details) is not dict
                or details.get("authority") != "PATCH_REVIEW_ONLY"
                or details.get("task_id") != task_id
                or type(details.get("patch_sha256")) is not str
                or re.fullmatch(r"[0-9a-f]{64}", details["patch_sha256"]) is None
            ):
                raise ValueError("Untrusted or unbound proposal receipt")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                """SELECT attempts FROM tasks WHERE id=? AND status='LEASED'
                AND owner=? AND lease_until>?""",
                (task_id, worker, self.now),
            ).fetchone()
            if row is None:
                raise PermissionError("Missing or expired worker reservation")
            exhausted = state == "QUEUED" and row[0] >= MAX_ATTEMPTS
            final_state = "BLOCKED" if exhausted else state
            result = self.conn.execute(
                """UPDATE tasks SET status=?,receipt=?,owner=NULL,lease_until=NULL,
                updated_at=? WHERE id=? AND status='LEASED' AND owner=?
                AND lease_until>?""",
                (final_state, receipt, self.now, task_id, worker, self.now),
            )
            if result.rowcount != 1:
                raise PermissionError("Missing or expired worker reservation")
            if exhausted:
                self._queue_alert(task_id, "Execution retry limit reached after three attempts.")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _queue_alert(self, task_id: str, detail: str) -> bool:
        """Deduplicate an alert inside the caller's current SQLite transaction."""
        fingerprint = hashlib.sha256(f"{task_id}\0{detail}".encode()).hexdigest()
        result = self.conn.execute(
            "INSERT OR IGNORE INTO alerts(fingerprint,task_id,detail,created_at) VALUES(?,?,?,?)",
            (fingerprint, task_id, detail, self.now),
        )
        return result.rowcount == 1

    def request_input(self, task_id: str, detail: str) -> bool:
        """Record one justified owner action without automatically contacting them."""
        if not detail.strip() or len(detail) > 2000:
            raise ValueError("Invalid escalation text")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown task")
            created = self._queue_alert(task_id, detail)
            self.conn.commit()
            return created
        except Exception:
            self.conn.rollback()
            raise

    def pending_alerts(self, limit: int = 10) -> list[dict[str, object]]:
        """List only undelivered, bounded notifications with manifest-linked issues."""
        if not 1 <= limit <= 50:
            raise ValueError("Alert page size must be between 1 and 50")
        rows = self.conn.execute(
            """SELECT a.fingerprint, a.task_id, t.issue, a.detail, a.created_at
            FROM alerts a JOIN tasks t ON t.id=a.task_id
            LEFT JOIN alert_deliveries d ON d.fingerprint=a.fingerprint
            WHERE d.fingerprint IS NULL
            ORDER BY a.created_at, a.fingerprint LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            dict(zip(("fingerprint", "task_id", "issue", "detail", "created_at"), row))
            for row in rows
        ]

    def claim_alert_send(self, fingerprint: str) -> bool:
        """Commit an immutable send claim before any non-idempotent GitHub POST.

        A crashed, timed-out or concurrently running sender must never acquire
        the same claim again. Uncertain claims require remote reconciliation,
        not automatic reposting or a time-based lease expiry.
        """
        if re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
            raise ValueError("Malformed alert fingerprint")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            known = self.conn.execute(
                "SELECT 1 FROM alerts WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if known is None:
                raise ValueError("Unknown alert fingerprint")
            delivered = self.conn.execute(
                "SELECT 1 FROM alert_deliveries WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if delivered is not None:
                self.conn.commit()
                return False
            result = self.conn.execute(
                """INSERT OR IGNORE INTO alert_send_claims
                (fingerprint,claimed_at) VALUES (?,?)""",
                (fingerprint, self.now),
            )
            self.conn.commit()
            return result.rowcount == 1
        except Exception:
            self.conn.rollback()
            raise

    def claimed_alerts(self, limit: int = 10) -> list[dict[str, object]]:
        """Expose quarantined sends for safe remote read-only reconciliation."""
        if not 1 <= limit <= 50:
            raise ValueError("Claim page size must be between 1 and 50")
        rows = self.conn.execute(
            """SELECT a.fingerprint, t.issue, a.detail
            FROM alert_send_claims c JOIN alerts a ON c.fingerprint=a.fingerprint
            JOIN tasks t ON a.task_id=t.id
            LEFT JOIN alert_deliveries d ON d.fingerprint=a.fingerprint
            WHERE d.fingerprint IS NULL ORDER BY c.claimed_at,c.fingerprint LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(zip(("fingerprint", "issue", "detail"), row)) for row in rows]

    def mark_alert_delivered(self, fingerprint: str, comment_id: int) -> None:
        """Checkpoint a confirmed external issue comment, not a transport attempt."""
        if (
            re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            or type(comment_id) is not int
            or comment_id < 1
        ):
            raise ValueError("Malformed alert delivery receipt")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            claimed = self.conn.execute(
                "SELECT 1 FROM alert_send_claims WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if claimed is None:
                raise PermissionError("An alert requires a durable send claim before delivery")
            self.conn.execute(
                """INSERT OR IGNORE INTO alert_deliveries
                (fingerprint,comment_id,delivered_at) VALUES (?,?,?)""",
                (fingerprint, comment_id, self.now),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def status(self) -> dict:
        """Report genuine queued/leased/blocked state, never job execution."""
        tasks = [
            dict(zip(("id", "issue", "kind", "status", "owner", "attempts", "receipt"), row))
            for row in self.conn.execute(
                "SELECT id,issue,kind,status,owner,attempts,receipt FROM tasks ORDER BY issue"
            )
        ]
        return {
            "execution_mode": "SUPERVISOR_RESERVATIONS_ONLY_NO_CODING_EXECUTOR",
            "complete": all(row["status"] == "VERIFIED" for row in tasks),
            "tasks": tasks,
            "pending_owner_alerts": self.conn.execute(
                """SELECT COUNT(*) FROM alerts a LEFT JOIN alert_deliveries d
                ON a.fingerprint=d.fingerprint WHERE d.fingerprint IS NULL"""
            ).fetchone()[0],
            "uncertain_owner_alerts": self.conn.execute(
                """SELECT COUNT(*) FROM alert_send_claims c
                LEFT JOIN alert_deliveries d ON c.fingerprint=d.fingerprint
                WHERE d.fingerprint IS NULL"""
            ).fetchone()[0],
        }

    def close(self) -> None:
        """Close storage without silently changing task state."""
        self.conn.close()


def main() -> int:
    """Expose non-privileged local commands, with no network side effects."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--db", type=Path, default=Path("artifacts/delivery/state.sqlite3"))
    parser.add_argument("--at", type=int)
    parser.add_argument("--worker", help="Reserve work only; does not execute code")
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    supervisor = Supervisor(args.db, manifest, clock=args.at)
    try:
        if args.recover:
            print(f"Recovered expired reservations: {supervisor.recover()}")
        if args.worker:
            print(f"Reserved work: {supervisor.claim(args.worker) or 'NONE'}")
        print(json.dumps(supervisor.status(), indent=2))
    finally:
        supervisor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
