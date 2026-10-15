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
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from delivery_orchestrator import DEFAULT_MANIFEST
from delivery_supervisor import Supervisor


def format_alert_body(issue: int, fingerprint: str, detail: str) -> str:
    """Render an exact, validated issue-bound alert for later remote reconciliation."""
    if (
        not 1 <= issue <= 100000
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
        or not 0 < len(detail.strip()) <= 2000
    ):
        raise ValueError("Invalid issue-bound notification identity")
    return (
        "MatchDesk delivery supervisor — owner action required\n\n"
        + detail
        + f"\n\nTracking issue: #{issue}. "
        + "No permission or production action has been automatically granted.\n\n"
        + f"<!-- matchdesk-owner-alert:{fingerprint} -->"
    )


def deliver_comment(issue: int, fingerprint: str, detail: str, token: str) -> int:
    """Post exactly one owner escalation after its durable send claim exists."""
    if not token:
        raise ValueError("Missing alert delivery token")
    body = format_alert_body(issue, fingerprint, detail)
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
        delivered = 0
        for alert in pending:
            fingerprint = str(alert["fingerprint"])
            if not supervisor.claim_alert_send(fingerprint):
                continue
            # The committed send claim survives crashes and ambiguous HTTP outcomes.
            # An uncertain claim must be reconciled, never automatically retried.
            comment_id = deliver_comment(
                int(alert["issue"]),
                fingerprint,
                str(alert["detail"]),
                os.environ["MATCHDESK_ALERT_GITHUB_TOKEN"],
            )
            supervisor.mark_alert_delivered(fingerprint, comment_id)
            delivered += 1
        print(
            json.dumps(
                {
                    "mode": "DELIVERY_ATTEMPTED",
                    "count": delivered,
                    "uncertain": supervisor.claimed_alerts(),
                }
            )
        )
    finally:
        supervisor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
