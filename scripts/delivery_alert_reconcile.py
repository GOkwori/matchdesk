"""Read-only verification of uncertain MatchDesk GitHub owner-alert sends.

Never retry an uncertain POST. Reconcile only exact body/fingerprint, issue
and a separately configured expected bot login. Ambiguity remains quarantined.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from delivery_alerts import format_alert_body
from delivery_orchestrator import DEFAULT_MANIFEST
from delivery_supervisor import Supervisor


def identify_comment(
    comments: list[dict], *, issue: int, fingerprint: str, detail: str, actor: str
) -> int | None:
    """Return a single trusted exact-body match, failing closed on duplicates."""
    expected = format_alert_body(issue, fingerprint, detail)
    matched = [
        entry["id"]
        for entry in comments
        if (
            isinstance(entry, dict)
            and entry.get("body") == expected
            and isinstance(entry.get("user"), dict)
            and entry["user"].get("login") == actor
            and type(entry.get("id")) is int
            and entry["id"] > 0
        )
    ]
    if len(matched) > 1:
        raise ValueError("Ambiguous duplicate owner-alert comments")
    return matched[0] if matched else None


def read_comments(issue: int, token: str, *, max_pages: int = 10) -> list[dict]:
    """Read bounded GitHub issue history; refuse an incomplete search."""
    if not token or not 1 <= issue <= 100000 or not 1 <= max_pages <= 10:
        raise ValueError("Invalid constrained comment query")
    found: list[dict] = []
    for page in range(1, max_pages + 1):
        req = Request(
            f"https://api.github.com/repos/GOkwori/matchdesk/issues/{issue}/comments"
            f"?per_page=100&page={page}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "matchdesk-alert-reconciliation",
            },
        )
        with urlopen(req, timeout=15) as response:
            records = json.load(response)
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise ValueError("Unexpected GitHub comment response")
        found.extend(records)
        if len(records) < 100:
            return found
    raise ValueError("Issue history exceeded bounded reconciliation pages")


def reconcile(supervisor: Supervisor, token: str, actor: str) -> dict:
    """Checkpoint only exact remote evidence; do not release uncertain claims."""
    if (
        not actor
        or len(actor) > 39
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
            for c in actor
        )
    ):
        raise ValueError("Expected alert sender login must be verified")
    checked = 0
    confirmed = 0
    for item in supervisor.claimed_alerts():
        issue = int(item["issue"])
        comments = read_comments(issue, token)
        comment_id = identify_comment(
            comments,
            issue=issue,
            fingerprint=str(item["fingerprint"]),
            detail=str(item["detail"]),
            actor=actor,
        )
        checked += 1
        if comment_id is not None:
            supervisor.mark_alert_delivered(str(item["fingerprint"]), comment_id)
            confirmed += 1
    return {"checked": checked, "confirmed": confirmed, "quarantined": supervisor.claimed_alerts()}


def main() -> int:
    """Require explicit authenticated reconciliation; default to local preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--db", type=Path, default=Path("artifacts/delivery/state.sqlite3"))
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args()
    supervisor = Supervisor(args.db, json.loads(args.manifest.read_text(encoding="utf-8")))
    try:
        if not args.reconcile:
            print(json.dumps({"mode": "DRY_RUN", "quarantined": supervisor.claimed_alerts()}))
            return 0
        token = os.getenv("MATCHDESK_ALERT_GITHUB_TOKEN", "")
        actor = os.getenv("MATCHDESK_ALERT_SENDER_LOGIN", "")
        if not token or not actor:
            parser.error("Authenticated reconciliation requires token and verified sender login")
        print(json.dumps(reconcile(supervisor, token, actor)))
    finally:
        supervisor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
