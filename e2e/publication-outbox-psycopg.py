"""Prove the publication outbox rules on real PostgreSQL (migration 015).

Runs in disposable CI after the migration is applied by the owner. The owner creates two restricted
logins with fresh random passwords: a publisher (outbox only) and a language reviewer (reviews only).
Every rule is exercised through those logins, and each forbidden action must fail. Synthetic data only.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets

import psycopg
from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.publication import publication_id
from psycopg import sql
from psycopg.types.json import Jsonb

HOST = os.environ.get("MATCHDESK_PG_HOST", "postgres")
PORT = int(os.environ.get("MATCHDESK_PG_PORT", "5432"))
OWNER = os.environ.get("MATCHDESK_PG_OWNER", "matchdesk")
PUBLISHER = "matchdesk_publisher_ci"
REVIEWER = "matchdesk_language_reviewer_ci"
TENANT = "ci-publication-tenant"


def connect(user: str, password: str | None) -> psycopg.Connection:
    """One real TCP login per role; no SET ROLE."""
    return psycopg.connect(
        host=HOST,
        port=PORT,
        dbname="matchdesk",
        user=user,
        password=password,
        sslmode="prefer",
        connect_timeout=10,
        autocommit=True,
    )


def binding(language: str, content: str) -> ApprovalBinding:
    """A synthetic approved version; the content digest is unique to this run."""
    return ApprovalBinding(
        item_id="ci-story",
        item_version=1,
        replay_id="ci-replay",
        content_digest=hashlib.sha256(content.encode()).hexdigest(),
        evidence_digest="e" * 64,
        language=language,
        persona="casual_fan",
    )


def insert_entry(
    conn,
    b: ApprovalBinding,
    destination: str,
    *,
    producer="ci-producer",
    publisher="ci-publisher",
    reviewer=None,
) -> str:
    """Queue one publication through the publisher login."""
    pid = publication_id(b, destination)
    conn.execute(
        "INSERT INTO matchdesk_publication_outbox (publication_id, tenant_id, binding_json, destination,"
        " producer_actor_id, publisher_actor_id, reviewer_actor_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            pid,
            TENANT,
            Jsonb(json.loads(b.model_dump_json())),
            destination,
            producer,
            publisher,
            reviewer,
        ),
    )
    return pid


def review(conn, b: ApprovalBinding, verdict: str, reviewer="ci-reviewer") -> None:
    """Record a language review through the reviewer login."""
    conn.execute(
        "INSERT INTO matchdesk_language_reviews (tenant_id, content_digest, language, verdict, reviewer_actor_id)"
        " VALUES (%s, %s, %s, %s, %s)",
        (TENANT, b.content_digest, b.language, verdict, reviewer),
    )


def refused(label: str, action, fragment: str) -> None:
    """The action must fail with a message containing ``fragment``."""
    try:
        action()
    except psycopg.Error as error:
        message = str(error)
        if fragment.lower() not in message.lower():
            raise SystemExit(f"{label}: failed for the wrong reason: {message}") from error
        return
    raise SystemExit(f"{label}: was allowed")


def main() -> None:
    """Create restricted logins, then exercise every rule."""
    owner = connect(OWNER, os.environ.get("PGPASSWORD"))
    passwords = {PUBLISHER: secrets.token_hex(24), REVIEWER: secrets.token_hex(24)}
    for role, password in passwords.items():
        if owner.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone():
            # A previous run's role: drop its grants, then the role itself.
            owner.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
            owner.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        owner.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
    owner.execute(
        "REVOKE ALL ON matchdesk_publication_outbox, matchdesk_language_reviews FROM PUBLIC"
    )
    owner.execute(
        sql.SQL("GRANT SELECT, INSERT, UPDATE ON matchdesk_publication_outbox TO {}").format(
            sql.Identifier(PUBLISHER)
        )
    )
    owner.execute(
        sql.SQL("GRANT SELECT ON matchdesk_language_reviews TO {}").format(
            sql.Identifier(PUBLISHER)
        )
    )
    owner.execute(
        sql.SQL("GRANT SELECT, INSERT ON matchdesk_language_reviews TO {}").format(
            sql.Identifier(REVIEWER)
        )
    )
    publisher = connect(PUBLISHER, passwords[PUBLISHER])
    reviewer = connect(REVIEWER, passwords[REVIEWER])
    run = secrets.token_hex(8)  # distinct content per run keeps reruns independent
    en, es, fr = binding("en", run), binding("es", run), binding("fr", run)

    # Gate: English queues; Spanish and French need the latest review of the exact content to approve.
    en_id = insert_entry(publisher, en, "match_centre")
    refused(
        "es without review",
        lambda: insert_entry(publisher, es, "match_centre", reviewer="ci-reviewer"),
        "needs a recorded language review",
    )
    review(reviewer, es, "approved")
    refused(
        "es without naming reviewer",
        lambda: insert_entry(publisher, es, "match_centre"),
        "matchdesk_outbox_reviewed_language",
    )
    insert_entry(publisher, es, "match_centre", reviewer="ci-reviewer")
    refused(
        "es naming another reviewer",
        lambda: insert_entry(publisher, es, "social", reviewer="someone-else"),
        "does not approve",
    )
    review(reviewer, es, "changes_requested")
    refused(
        "es after changes requested",
        lambda: insert_entry(publisher, es, "social", reviewer="ci-reviewer"),
        "does not approve",
    )
    review(reviewer, fr, "approved")
    insert_entry(publisher, fr, "social", reviewer="ci-reviewer")
    print(
        "MATCHDESK_PUBLICATION_LANGUAGE_GATE_PASS: es/fr need the latest approving review of the exact content"
    )

    # Four eyes and one row per (version, destination).
    refused(
        "producer publishes own approval",
        lambda: insert_entry(publisher, en, "social", producer="ci-same", publisher="ci-same"),
        "matchdesk_outbox_second_person",
    )
    refused(
        "duplicate publication",
        lambda: insert_entry(publisher, en, "match_centre"),
        "duplicate key",
    )
    print(
        "MATCHDESK_PUBLICATION_FOUR_EYES_PASS: publisher differs from producer; one row per version and destination"
    )

    # Delivery bookkeeping: one attempt per update, terminal rows are final.
    def attempt(status: str, attempts: int, receipt=None):
        publisher.execute(
            "UPDATE matchdesk_publication_outbox SET status=%s, attempts=%s, receipt=%s WHERE publication_id=%s",
            (status, attempts, receipt, en_id),
        )

    refused("skipping attempts", lambda: attempt("failed", 2), "exactly one delivery attempt")
    attempt("failed", 1)
    refused(
        "delivered without receipt",
        lambda: attempt("delivered", 2),
        "matchdesk_outbox_receipt_when_delivered",
    )
    attempt("delivered", 2, "receipt-ci")
    refused("changing a delivered row", lambda: attempt("failed", 3), "is final")
    refused(
        "rewriting the destination",
        lambda: publisher.execute(
            "UPDATE matchdesk_publication_outbox SET destination='match_centre', attempts=attempts+1, status='failed'"
            " WHERE binding_json->>'language'='fr' AND tenant_id=%s",
            (TENANT,),
        ),
        "Only delivery status may change",
    )
    print(
        "MATCHDESK_PUBLICATION_TRANSITIONS_PASS: one attempt per update, receipts on delivery, final rows frozen"
    )

    # History and privileges.
    refused(
        "deleting a publication",
        lambda: publisher.execute(
            "DELETE FROM matchdesk_publication_outbox WHERE publication_id=%s", (en_id,)
        ),
        "permission denied",
    )
    refused(
        "owner deleting a publication",
        lambda: owner.execute(
            "DELETE FROM matchdesk_publication_outbox WHERE publication_id=%s", (en_id,)
        ),
        "append-only",
    )
    refused(
        "owner rewriting a review",
        lambda: owner.execute(
            "UPDATE matchdesk_language_reviews SET verdict='approved' WHERE tenant_id=%s", (TENANT,)
        ),
        "append-only",
    )
    refused(
        "publisher writing a review", lambda: review(publisher, en, "approved"), "permission denied"
    )
    refused(
        "reviewer queueing a publication",
        lambda: insert_entry(reviewer, binding("en", run + "-other"), "social"),
        "permission denied",
    )
    print(
        "MATCHDESK_PUBLICATION_HISTORY_PASS: append-only history, separate publisher and reviewer privileges"
    )

    for conn in (publisher, reviewer):
        conn.close()
    owner.close()


if __name__ == "__main__":
    main()
