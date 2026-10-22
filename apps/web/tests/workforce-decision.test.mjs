/** Exact binding tests; no browser token, authentication or network. */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  lockProducerDecision, decisionStillCurrent, prepareProducerDecision,
} from "../src/workforce/decision-confirmation.ts";

const A = "a".repeat(64), B = "b".repeat(64);
function snapshot() {
  return {
    session_id: "session01", output_id: "D-031", generation: 4,
    review_status: "ready_for_decision",
    binding: {
      item_id: "D-031", item_version: 4, replay_id: "replay01",
      content_digest: A, evidence_digest: B,
      language: "en", persona: "analyst",
    },
  };
}

test("deep snapshot copy is immutable despite source mutation", () => {
  const source = snapshot();
  const intent = lockProducerDecision(source, "approve");
  source.binding.content_digest = "c".repeat(64);
  source.generation = 5;
  assert.equal(intent.snapshot.generation, 4);
  assert.equal(intent.snapshot.binding.content_digest, A);
  assert.equal(Object.isFrozen(intent.snapshot), true);
  assert.equal(Object.isFrozen(intent.snapshot.binding), true);
  assert.equal(Object.isFrozen(intent), true);
  assert.equal(decisionStillCurrent(intent, snapshot()), true);
});

test("payload has exact backend decision fields and no client authority", () => {
  const locked = lockProducerDecision(snapshot(), "reject");
  const result = prepareProducerDecision(locked, snapshot(), "  Evidence discrepancy  ");
  assert.equal(result.action, "reject");
  assert.equal(result.session_id, "session01");
  assert.equal(result.output_id, "D-031");
  assert.deepEqual(result.body, {
    binding: snapshot().binding, expected_generation: 4,
    reason: "Evidence discrepancy",
  });
  assert.deepEqual(Object.keys(result.body).sort(),
    ["binding", "expected_generation", "reason"]);
  assert.equal("publication_enabled" in result.body, false);
  assert.equal(Object.isFrozen(result.body.binding), true);
});

test("all scope, generation, review-state and digest changes deny confirmation", () => {
  const locked = lockProducerDecision(snapshot(), "approve");
  const variants = [
    { session_id: "another_session" },
    { output_id: "D-032", binding: { ...snapshot().binding, item_id: "D-032" } },
    { generation: 5 },
    { review_status: "approved" },
    { binding: { ...snapshot().binding, item_id: "D-032" } },
    { binding: { ...snapshot().binding, item_version: 5 } },
    { binding: { ...snapshot().binding, replay_id: "replay02" } },
    { binding: { ...snapshot().binding, content_digest: "c".repeat(64) } },
    { binding: { ...snapshot().binding, evidence_digest: "d".repeat(64) } },
    { binding: { ...snapshot().binding, language: "es" } },
    { binding: { ...snapshot().binding, persona: "casual_fan" } },
  ];
  for (const partial of variants) {
    const now = { ...snapshot(), ...partial };
    assert.equal(decisionStillCurrent(locked, now), false, JSON.stringify(partial));
    assert.throws(() => prepareProducerDecision(locked, now, "Reviewed"), /exact-version/);
  }
  assert.throws(() => prepareProducerDecision(locked, null, "Reviewed"), /exact-version/);
});

test("rejects malformed and incomplete snapshots and unapproved actions", () => {
  const bad = [
    { session_id: "" }, { session_id: "out/side" },
    { output_id: "D-999" }, { generation: 0 },
    { generation: 2.5 }, { generation: "4" },
    { review_status: "pending_verification" },
    { binding: { ...snapshot().binding, item_version: 0 } },
    { binding: { ...snapshot().binding, item_version: true } },
    { binding: { ...snapshot().binding, replay_id: "../escape" } },
    { binding: { ...snapshot().binding, content_digest: "invalid" } },
    { binding: { ...snapshot().binding, evidence_digest: "A".repeat(64) } },
    { binding: { ...snapshot().binding, language: "xx" } },
    { binding: { ...snapshot().binding, persona: "publisher" } },
    { binding: null },
  ];
  for (const change of bad) {
    assert.throws(() => lockProducerDecision({ ...snapshot(), ...change }, "approve"),
      /exact-version/, JSON.stringify(change));
  }
  assert.throws(() => lockProducerDecision(snapshot(), "publish"), /exact-version/);
  assert.throws(() => lockProducerDecision(snapshot(), "edit"), /exact-version/);
});

test("bounded printable reason required at the moment of confirmation", () => {
  const intent = lockProducerDecision(snapshot(), "approve");
  for (const reason of ["", " \t ", "a".repeat(257), "line\nbreak", "bad\u0000null", null]) {
    assert.throws(() => prepareProducerDecision(intent, snapshot(), reason), /exact-version/);
  }
  assert.equal(prepareProducerDecision(intent, snapshot(), "x".repeat(256)).body.reason.length, 256);
});

test("extra browser claims are not forwarded to the host/backend", () => {
  const snap = {
    ...snapshot(), roles: ["publisher"], publication_enabled: true,
    binding: { ...snapshot().binding, tenant_id: "evil", can_publish: true },
  };
  const intent = lockProducerDecision(snap, "approve");
  const result = prepareProducerDecision(intent, snapshot(), "Reviewed");
  assert.deepEqual(Object.keys(intent.snapshot).sort(),
    ["binding", "generation", "output_id", "review_status", "session_id"]);
  assert.deepEqual(Object.keys(result.body.binding).sort(), [
    "content_digest", "evidence_digest", "item_id", "item_version",
    "language", "persona", "replay_id",
  ]);
  assert.equal("roles" in result, false);
  assert.equal("can_publish" in result.body.binding, false);
});
