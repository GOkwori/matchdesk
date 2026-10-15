#!/usr/bin/env python3
"""Deliver durable MatchDesk owner alerts to existing GitHub issues on explicit opt-in.

Default is a local read-only preview. Explicit delivery requires a separate,
least-privilege token authorised to comment only within GOkwori/matchdesk.
No PR merge, code mutation, deployment or agent execution is performed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from delivery_orchestrator import DEFAULT_MANIFEST
from delivery_supervisor import Supervisor


def deliver_comment(issue: int, fingerprint: str, detail: str, token: str) -> int:
    """Post one exact-issue, bounded escalation and return confirmed comment ID."""
    if not token or not 1 <= issue <= 100000 or len(detail) > 2000:
        raise ValueError("Invalid narrowly scoped alert delivery")
    body = (
        "MatchDesk delivery supervisor — owner action required\n\n"
        + detail
        + f"\n\nTracking issue: #{issue}. "
        + "No permission or production action has been automatically granted.\n\n"
        + f"<!-- matchdesk-owner-alert:{fingerprint} -->"
    )
    request = Request(
        f"https://api.github.com/repos/GOkwori/matchdesk/issues/{issue}/comments",
        data=json.dumps({"body": body}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "matchdesk-delivery-owner-alerts",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            comment = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("GitHub owner alert could not be delivered") from exc
    comment_id = comment.get("id") if isinstance(comment, dict) else None
    if type(comment_id) is not int or comment_id < 1:
        raise RuntimeError("Unverified GitHub alert delivery receipt")
    return comment_id


def main() -> int:
    """Preview undelivered alerts, or send them only with explicit opt-in."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--db", type=Path, default=Path("artifacts/delivery/state.sqlite3"))
    parser.add_argument("--deliver", action="store_true")
    args = parser.parse_args()
    if args.deliver and not os.environ.get("MATCHDESK_ALERT_GITHUB_TOKEN"):
        parser.error("Explicit delivery requires MATCHDESK_ALERT_GITHUB_TOKEN")
    supervisor = Supervisor(args.db, json.loads(args.manifest.read_text(encoding="utf-8")))
    try:
        pending = supervisor.pending_alerts()
        if not args.deliver:
            print(json.dumps({"mode": "DRY_RUN", "alerts": pending}, indent=2))
            return 0
        for alert in pending:
            issue = int(alert["issue"])
            comment_id = deliver_comment(
                issue, str(alert["fingerprint"]), str(alert["detail"]),
                os.environ["MATCHDESK_ALERT_GITHUB_TOKEN"],
            )
            supervisor.mark_alert_delivered(str(alert["fingerprint"]), comment_id)
        print(json.dumps({"mode": "DELIVERED", "count": len(pending)}))
    finally:
        supervisor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
