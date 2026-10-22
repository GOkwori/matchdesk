"""Prove the publication outbox rules on real PostgreSQL (migration 015).

Runs in disposable CI after migrations 001 and 015 are applied by the owner. The owner plays the
producer store (writing approved cases and audit entries) and creates three logins with fresh
random passwords: a publisher, a language reviewer, and an outsider with no capability. Every rule
is exercised through those logins, and each forbidden action must fail for the stated reason,
including a REPEATABLE READ snapshot, an expired lease, a review that races a claim, and a fault
that must not be mistaken for a policy refusal. Synthetic data only.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time

import psycopg
from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.publication import publication_id
from psycopg import sql
from psycopg.types.json import Jsonb

HOST = os.environ.get("MATCHDESK_PG_HOST", "postgres")
PORT = int(os.environ.get("MATCHDESK_PG_PORT", "5432"))
OWNER = os.environ.get("MATCHDESK_PG_OWNER", "matchdesk")
LOGINS = {
    "matchdesk_publisher_ci": "matchdesk_publisher",
    "matchdesk_language_reviewer_ci": "matchdesk_language_reviewer",
    "matchdesk_outsider_ci": None,
}
TENANT = "ci-publication-tenant"
OTHER_TENANT = "ci-publication-other"


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


def check(label: str, condition: bool) -> None:
    """Fail loudly on a broken expectation."""
    if not condition:
        raise SystemExit(f"{label}: expectation failed")


class Run:
    """One run's synthetic producer cases, logins and helpers."""

    def __init__(self) -> None:
        """Create the logins and connect as each of them."""
        self.owner = connect(OWNER, os.environ.get("PGPASSWORD"))
        self.tag = secrets.token_hex(6)  # distinct content per run keeps reruns independent
        passwords = {login: secrets.token_hex(24) for login in LOGINS}
        self.passwords = passwords
        for login, capability in LOGINS.items():
            ident = sql.Identifier(login)
            if self.owner.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (login,)).fetchone():
                self.owner.execute(sql.SQL("DROP OWNED BY {}").format(ident))
                self.owner.execute(sql.SQL("DROP ROLE {}").format(ident))
            self.owner.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    ident, sql.Literal(passwords[login])
                )
            )
            if capability:
                self.owner.execute(
                    sql.SQL("GRANT {} TO {}").format(sql.Identifier(capability), ident)
                )
        self.publisher = connect("matchdesk_publisher_ci", passwords["matchdesk_publisher_ci"])
        self.reviewer = connect(
            "matchdesk_language_reviewer_ci", passwords["matchdesk_language_reviewer_ci"]
        )
        self.outsider = connect("matchdesk_outsider_ci", passwords["matchdesk_outsider_ci"])
        self.cases = 0

    def binding(self, language: str, words: str, persona: str = "casual_fan") -> ApprovalBinding:
        """A synthetic version whose digest is unique to this run."""
        return ApprovalBinding(
            item_id="ci-story",
            item_version=1,
            replay_id="ci-replay",
            content_digest=hashlib.sha256(f"{self.tag}:{words}".encode()).hexdigest(),
            evidence_digest="e" * 64,
            language=language,
            persona=persona,
        )

    def approve(
        self, b: ApprovalBinding, *, tenant: str = TENANT, producer: str = "ci-producer"
    ) -> tuple[str, str]:
        """Write an approved producer case, as the producer store would. Returns its key."""
        self.cases += 1
        session, output = f"ci-session-{self.tag}", f"ci-output-{self.cases}"
        entry = {
            "action": "approved",
            "actor_id": producer,
            "binding": json.loads(b.model_dump_json()),
            "reason": "Checked",
        }
        self.owner.execute(
            "INSERT INTO matchdesk_producer_cases"
            " (tenant_id, session_id, output_id, generation, case_json, audit_digest)"
            " VALUES (%s, %s, %s, 1, '{}', %s)",
            (tenant, session, output, "a" * 64),
        )
        self.owner.execute(
            "INSERT INTO matchdesk_producer_audit"
            " (tenant_id, session_id, output_id, generation, entry_json, audit_digest)"
            " VALUES (%s, %s, %s, 1, %s, %s)",
            (tenant, session, output, Jsonb(entry), "a" * 64),
        )
        return session, output

    def revise(self, key: tuple[str, str], b: ApprovalBinding, *, tenant: str = TENANT) -> None:
        """The producer opens a newer version, which ends the old approval."""
        newer = json.loads(b.model_copy(update={"item_version": 2}).model_dump_json())
        entry = {"action": "revision_opened", "actor_id": "ci-producer", "binding": newer}
        entry["reason"] = "New version"
        self.owner.execute(
            "INSERT INTO matchdesk_producer_audit"
            " (tenant_id, session_id, output_id, generation, entry_json, audit_digest)"
            " VALUES (%s, %s, %s, 2, %s, %s)",
            (tenant, *key, Jsonb(entry), "b" * 64),
        )
        self.owner.execute(
            "UPDATE matchdesk_producer_cases SET generation = 2"
            " WHERE tenant_id = %s AND session_id = %s AND output_id = %s",
            (tenant, *key),
        )

    def queue(self, conn, b, destination, key, *, publisher="ci-publisher", **kw):
        """Queue through the SECURITY DEFINER entry point; returns (publication ID, status)."""
        binding_json = Jsonb(kw.pop("binding_json", None) or json.loads(b.model_dump_json()))
        return conn.execute(
            "SELECT * FROM public.matchdesk_queue_publication(%s, %s, %s, %s, %s, %s, %s)",
            (
                kw.pop("tenant", TENANT),
                *key,
                binding_json,
                destination,
                publisher,
                kw.pop("max_attempts", 3),
            ),
        ).fetchone()

    def review(self, conn, b, verdict, *, reviewer="ci-reviewer", tenant=TENANT) -> int:
        """Record a language review through its entry point."""
        return conn.execute(
            "SELECT public.matchdesk_record_language_review(%s, %s, %s, %s, %s, '')",
            (tenant, b.content_digest, b.language, verdict, reviewer),
        ).fetchone()[0]

    def claim(self, pid, tenant=TENANT, lease=300, conn=None):
        """Claim an attempt; returns {binding, claim_token}, or None when there is nothing to send."""
        return (
            (conn or self.publisher)
            .execute(
                "SELECT public.matchdesk_claim_publication_attempt(%s, %s, %s)",
                (tenant, pid, lease),
            )
            .fetchone()[0]
        )

    def record(self, pid, token, outcome, receipt=None, error=None, tenant=TENANT) -> str:
        """Record a claimed attempt's outcome; returns the new status."""
        return self.publisher.execute(
            "SELECT public.matchdesk_record_publication_attempt(%s, %s, %s, %s, %s, %s)",
            (tenant, pid, token, outcome, receipt, error),
        ).fetchone()[0]

    def attempt(self, pid, outcome, receipt=None, error=None) -> str:
        """Claim, then record one outcome."""
        claimed = self.claim(pid)
        check(f"{pid[:8]} can be claimed", claimed is not None)
        return self.record(pid, claimed["claim_token"], outcome, receipt, error)

    def row(self, pid, tenant=TENANT):
        """The outbox row, read by the owner."""
        return self.owner.execute(
            "SELECT status, attempts, last_error, queued_by, review_id"
            " FROM matchdesk_publication_outbox WHERE tenant_id = %s AND publication_id = %s",
            (tenant, pid),
        ).fetchone()


def approval_rules(r: Run) -> dict:
    """Only the exact version the producer audit currently approves can be queued."""
    pub = r.publisher
    en = r.binding("en", "goal")
    en_key = r.approve(en)
    refused(
        "no producer case",
        lambda: r.queue(pub, en, "match_centre", ("ci-none", "ci-none")),
        "No producer case",
    )
    refused(
        "different content",
        lambda: r.queue(pub, r.binding("en", "never approved"), "match_centre", en_key),
        "has not approved this exact version",
    )
    for field in ("language", "schema_version"):
        partial = json.loads(en.model_dump_json())
        del partial[field]
        refused(
            f"binding without {field}",
            lambda partial=partial: r.queue(pub, en, "match_centre", en_key, binding_json=partial),
            "complete approval binding",
        )
    revised = r.binding("en", "revised later")
    revised_key = r.approve(revised)
    r.revise(revised_key, revised)
    refused(
        "superseded approval",
        lambda: r.queue(pub, revised, "match_centre", revised_key),
        "has not approved this exact version",
    )
    refused(
        "publisher inserting directly",
        lambda: pub.execute(
            "INSERT INTO matchdesk_publication_outbox (tenant_id, publication_id) VALUES ('t', 'p')"
        ),
        "permission denied",
    )
    refused(
        "outsider queueing",
        lambda: r.queue(r.outsider, en, "match_centre", en_key),
        "permission denied",
    )
    with psycopg.connect(
        host=HOST,
        port=PORT,
        dbname="matchdesk",
        user="matchdesk_publisher_ci",
        password=r.passwords["matchdesk_publisher_ci"],
        connect_timeout=10,
    ) as snapshot:
        snapshot.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        refused(
            "queueing under REPEATABLE READ",
            lambda: r.queue(snapshot, en, "match_centre", en_key),
            "requires READ COMMITTED",
        )
    en_id, status = r.queue(pub, en, "match_centre", en_key)
    check("the database computes the ID", en_id == publication_id(en, "match_centre"))
    check("a new publication is queued", status == "queued")
    print("MATCHDESK_PUBLICATION_APPROVAL_PASS: only the version the producer audit approves")
    return {"en": en, "en_key": en_key, "en_id": en_id}


def language_rules(r: Run) -> dict:
    """The latest review of the exact content, in this tenant, by a second person, must approve."""
    pub = r.publisher
    es = r.binding("es", "gol")
    es_key = r.approve(es)
    refused(
        "es without review",
        lambda: r.queue(pub, es, "match_centre", es_key),
        "needs a recorded language review",
    )
    r.review(r.reviewer, es, "approved")
    es_id, _ = r.queue(pub, es, "match_centre", es_key)
    check("es names its review", r.row(es_id)[4] is not None)
    r.review(r.reviewer, es, "changes_requested")
    refused(
        "es after changes requested",
        lambda: r.queue(pub, es, "social", es_key),
        "does not approve",
    )
    refused(
        "reviewer forging the review number",
        lambda: r.reviewer.execute(
            "INSERT INTO matchdesk_language_reviews (review_id, tenant_id, content_digest, language,"
            " verdict, reviewer_actor_id, recorded_by, reviewed_at) OVERRIDING SYSTEM VALUE"
            " VALUES (9223372036854775807, %s, %s, 'es', 'approved', 'x', 'x', now())",
            (TENANT, es.content_digest),
        ),
        "permission denied",
    )
    fr = r.binding("fr", "but")
    fr_key = r.approve(fr)
    pub.execute(
        "CREATE TEMP TABLE matchdesk_language_reviews (review_id bigint, tenant_id text,"
        " content_digest text, language text, verdict text, reviewer_actor_id text)"
    )
    pub.execute(
        "INSERT INTO matchdesk_language_reviews VALUES (1, %s, %s, 'fr', 'approved', 'x')",
        (TENANT, fr.content_digest),
    )
    refused(
        "temporary table shadowing reviews",
        lambda: r.queue(pub, fr, "social", fr_key),
        "needs a recorded language review",
    )
    r.review(r.reviewer, fr, "approved", tenant=OTHER_TENANT)
    refused(
        "another tenant's review",
        lambda: r.queue(pub, fr, "social", fr_key),
        "needs a recorded language review",
    )
    r.review(r.reviewer, fr, "approved", reviewer="CI-Producer")
    refused(
        "producer reviewing their own approval",
        lambda: r.queue(pub, fr, "social", fr_key),
        "reviewer must not be the producer",
    )
    r.review(r.reviewer, fr, "approved")
    fr_id, _ = r.queue(pub, fr, "social", fr_key)
    print(
        "MATCHDESK_PUBLICATION_LANGUAGE_GATE_PASS: es/fr need the latest approving review"
        " of the exact content"
    )
    return {"es": es, "es_key": es_key, "es_id": es_id, "fr": fr, "fr_key": fr_key, "fr_id": fr_id}


def four_eyes_rules(r: Run, s: dict) -> None:
    """The publisher is a second person; one row per version and destination, per tenant."""
    pub, en, en_key = r.publisher, s["en"], s["en_key"]
    refused(
        "producer publishing own approval",
        lambda: r.queue(pub, en, "social", en_key, publisher=" CI-Producer "),
        "must not be the producer",
    )
    again = r.queue(pub, en, "match_centre", en_key)
    check("a second request returns the first publication", again == (s["en_id"], "queued"))
    count = r.owner.execute(
        "SELECT count(*) FROM matchdesk_publication_outbox WHERE tenant_id = %s"
        " AND destination = 'match_centre' AND content_digest = %s",
        (TENANT, en.content_digest),
    ).fetchone()[0]
    check("one row per version and destination", count == 1)
    refused(
        "owner inserting a squatting ID",
        lambda: r.owner.execute(
            "INSERT INTO matchdesk_publication_outbox SELECT tenant_id, %s, session_id, output_id,"
            " producer_generation, binding_json, language, content_digest, persona, 'social',"
            " producer_actor_id, publisher_actor_id, review_id, reviewer_actor_id, max_attempts,"
            " 'queued', 0, NULL, NULL, NULL, NULL, queued_by, created_at, updated_at"
            " FROM matchdesk_publication_outbox WHERE tenant_id = %s AND publication_id = %s",
            ("f" * 64, TENANT, s["en_id"]),
        ),
        "matchdesk_outbox_computed_id",
    )
    other_tenant_key = r.approve(en, tenant=OTHER_TENANT)
    other_id, _ = r.queue(pub, en, "match_centre", other_tenant_key, tenant=OTHER_TENANT)
    check("tenants do not collide", other_id == s["en_id"])
    s["other_tenant_id"] = other_id
    print(
        "MATCHDESK_PUBLICATION_FOUR_EYES_PASS: publisher differs from producer;"
        " one row per version and destination"
    )


def delivery_rules(r: Run, s: dict) -> None:
    """Claims are exclusive and re-checked; one attempt per outcome; final rows frozen."""
    pub, en, en_key, en_id = r.publisher, s["en"], s["en_key"], s["en_id"]
    refused(
        "recording without a claim",
        lambda: r.record(en_id, "00000000-0000-0000-0000-000000000000", "delivered", "x"),
        "No attempt is in flight under this claim",
    )
    claimed = r.claim(en_id)
    check(
        "a claim returns the approved binding",
        claimed["binding"]["content_digest"] == en.content_digest,
    )
    check("a second worker cannot claim a live attempt", r.claim(en_id) is None)
    refused(
        "recording under another claim",
        lambda: r.record(en_id, "00000000-0000-0000-0000-000000000000", "failed"),
        "No attempt is in flight under this claim",
    )
    check(
        "failure recorded",
        r.record(en_id, claimed["claim_token"], "failed", error="timeout") == "failed",
    )
    refused(
        "recording twice under one claim",
        lambda: r.record(en_id, claimed["claim_token"], "delivered", "x"),
        "No attempt is in flight under this claim",
    )
    claimed = r.claim(en_id)
    refused(
        "delivered without receipt",
        lambda: r.record(en_id, claimed["claim_token"], "delivered"),
        "matchdesk_outbox_receipt_when_delivered",
    )
    check(
        "delivered",
        r.record(en_id, claimed["claim_token"], "delivered", "receipt-ci") == "delivered",
    )
    refused(
        "changing a delivered row",
        lambda: r.record(en_id, claimed["claim_token"], "failed"),
        "is final",
    )
    check("no claim after delivery", r.claim(en_id) is None)

    social_id, _ = r.queue(pub, en, "social", en_key, max_attempts=2)
    r.attempt(social_id, "failed", error="timeout")
    check("abandoned at the budget", r.attempt(social_id, "failed", error="t") == "abandoned")
    check("no claim after abandonment", r.claim(social_id) is None)
    check(
        "re-queueing reports the final status",
        r.queue(pub, en, "social", en_key) == (social_id, "abandoned"),
    )

    lease_b = r.binding("en", "lease")
    lease_key = r.approve(lease_b)
    lease_id, _ = r.queue(pub, lease_b, "match_centre", lease_key, max_attempts=2)
    stale = r.claim(lease_id, lease=5)
    check("a short lease is granted", stale is not None)
    refused("a lease below the floor", lambda: r.claim(lease_id, lease=1), "between 5 and 3600")
    time.sleep(6)
    fresh = r.claim(lease_id)
    check("an expired lease is reclaimed", fresh is not None)
    check("the lost attempt was counted", r.row(lease_id)[1] == 1)
    refused(
        "the expired claim cannot record",
        lambda: r.record(lease_id, stale["claim_token"], "delivered", "late"),
        "No attempt is in flight under this claim",
    )
    r.record(lease_id, fresh["claim_token"], "delivered", "receipt-lease")

    check("withdrawn after a language objection", r.claim(s["es_id"]) is None)
    status, _, reason, _, _ = r.row(s["es_id"])
    check("withdrawal is recorded", status == "withdrawn" and "does not approve" in reason)
    late = r.binding("en", "revised after queueing")
    late_key = r.approve(late)
    late_id, _ = r.queue(pub, late, "match_centre", late_key)
    r.revise(late_key, late)
    check("withdrawn after a revision", r.claim(late_id) is None)
    check("revision withdrawal recorded", r.row(late_id)[0] == "withdrawn")

    # A review recorded while a claim waits on the review lock is seen by that claim.
    race = r.binding("es", "carrera")
    race_key = r.approve(race)
    r.review(r.reviewer, race, "approved")
    race_id, _ = r.queue(pub, race, "match_centre", race_key)
    holder = psycopg.connect(
        host=HOST,
        port=PORT,
        dbname="matchdesk",
        user="matchdesk_language_reviewer_ci",
        password=r.passwords["matchdesk_language_reviewer_ci"],
        connect_timeout=10,
    )
    r.review(holder, race, "changes_requested")  # transaction left open: holds the review lock
    outcome: list[object] = []
    waiter = threading.Thread(target=lambda: outcome.append(r.claim(race_id)))
    waiter.start()
    waiter.join(1.5)
    check("the claim waits for the open review", waiter.is_alive())
    holder.commit()
    waiter.join(10)
    holder.close()
    check("the claim saw the review committed while it waited", outcome == [None])
    check("raced claim withdrawn", r.row(race_id)[0] == "withdrawn")

    # A fault is not a policy decision: it must be raised, never turned into a withdrawal.
    fault = r.binding("en", "fault")
    fault_key = r.approve(fault)
    fault_id, _ = r.queue(pub, fault, "match_centre", fault_key)
    r.owner.execute(
        "REVOKE SELECT ON matchdesk_producer_audit FROM matchdesk_publication_guard_owner"
    )
    try:
        refused("claim during a fault", lambda: r.claim(fault_id), "permission denied")
    finally:
        r.owner.execute(
            "GRANT SELECT ON matchdesk_producer_audit TO matchdesk_publication_guard_owner"
        )
    check("a fault leaves the row queued", r.row(fault_id)[0] == "queued")

    refused(
        "owner rewriting the destination",
        lambda: r.owner.execute(
            "UPDATE matchdesk_publication_outbox SET destination = 'social', status = 'failed',"
            " attempts = attempts + 1 WHERE tenant_id = %s AND publication_id = %s",
            (OTHER_TENANT, s["other_tenant_id"]),
        ),
        "Only delivery status may change",
    )
    refused(
        "owner recording an unclaimed outcome",
        lambda: r.owner.execute(
            "UPDATE matchdesk_publication_outbox SET status = 'delivered', receipt = 'x',"
            " attempts = attempts + 1 WHERE tenant_id = %s AND publication_id = %s",
            (OTHER_TENANT, s["other_tenant_id"]),
        ),
        "must be claimed",
    )
    refused(
        "publisher updating directly",
        lambda: pub.execute(
            "UPDATE matchdesk_publication_outbox SET status = 'failed' WHERE publication_id = %s",
            (s["fr_id"],),
        ),
        "permission denied",
    )
    print(
        "MATCHDESK_PUBLICATION_TRANSITIONS_PASS: re-checked before each attempt,"
        " one attempt per result, final rows frozen"
    )


def history_rules(r: Run, s: dict) -> None:
    """Append-only history and separate publisher and reviewer privileges."""
    pub, fr_id = r.publisher, s["fr_id"]
    refused(
        "publisher deleting",
        lambda: pub.execute(
            "DELETE FROM matchdesk_publication_outbox WHERE publication_id = %s", (fr_id,)
        ),
        "permission denied",
    )
    refused(
        "owner deleting",
        lambda: r.owner.execute(
            "DELETE FROM matchdesk_publication_outbox WHERE publication_id = %s", (fr_id,)
        ),
        "append-only",
    )
    refused(
        "owner truncating",
        lambda: r.owner.execute("TRUNCATE matchdesk_publication_outbox"),
        "append-only",
    )
    refused(
        "owner rewriting a review",
        lambda: r.owner.execute(
            "UPDATE matchdesk_language_reviews SET verdict = 'approved' WHERE tenant_id = %s",
            (TENANT,),
        ),
        "append-only",
    )
    refused("publisher reviewing", lambda: r.review(pub, s["fr"], "approved"), "permission denied")
    refused(
        "reviewer queueing",
        lambda: r.queue(r.reviewer, s["en"], "social", s["en_key"]),
        "permission denied",
    )
    r.owner.execute("GRANT matchdesk_publication_guard_owner TO matchdesk_outsider_ci")
    try:
        refused(
            "a member added to the guard owner",
            lambda: r.queue(pub, s["en"], "match_centre", s["en_key"]),
            "guard owner has role members",
        )
    finally:
        r.owner.execute("REVOKE matchdesk_publication_guard_owner FROM matchdesk_outsider_ci")
    check("the queueing login is recorded", r.row(fr_id)[3] == "matchdesk_publisher_ci")
    recorded_by = r.owner.execute(
        "SELECT DISTINCT recorded_by FROM matchdesk_language_reviews WHERE content_digest = %s",
        (s["fr"].content_digest,),
    ).fetchall()
    check("the reviewing login is recorded", recorded_by == [("matchdesk_language_reviewer_ci",)])
    print(
        "MATCHDESK_PUBLICATION_HISTORY_PASS: append-only history, separate publisher"
        " and reviewer privileges"
    )


def main() -> None:
    """Exercise every rule through the restricted logins."""
    r = Run()
    state = approval_rules(r)
    state |= language_rules(r)
    four_eyes_rules(r, state)
    delivery_rules(r, state)
    history_rules(r, state)
    for conn in (r.publisher, r.reviewer, r.outsider, r.owner):
        conn.close()


if __name__ == "__main__":
    main()
