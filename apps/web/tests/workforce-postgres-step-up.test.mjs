/** Synthetic adapter checks only; PostgreSQL privileges and locks require a separate gate. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { PostgresWorkforceStepUpStore } from "../src/workforce/postgres-step-up.ts";

const TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const CLIENT = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff";
const API = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa";
const ACTOR = "dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb";
const PENDING = createHash("sha256").update("pending").digest("hex");
const STATE = createHash("sha256").update("state").digest("hex");
const policy = { oidc: {
  tenantId: TENANT, clientId: CLIENT, apiResourceAppId: API,
  delegatedApiScope: "api://" + API + "/MatchDesk.Producer.Access",
  publicOrigin: "https://operator.example.test",
}, contextId: "c1" };
const attempt = {
  stateDigest: STATE, nonce: "n".repeat(43),
  tenantId: TENANT, clientId: CLIENT, objectId: ACTOR,
  subject: "qualified-operator", contextId: "c1",
  issuedAtSeconds: 1000000, expiresAtSeconds: 1000300,
};
class FakeSql {
  rows = new Map();
  calls = [];
  fail = false;
  async query(statement, args) {
    if (this.fail) throw new Error("internal database credential");
    this.calls.push({ statement, args });
    if (statement.startsWith("SELECT public.matchdesk_create_workforce_step_up_challenge(")) {
      if (this.rows.has(args[0])) return { rows: [{ created: false }] };
      this.rows.set(args[0], {
        state_digest: args[0], pending_digest: args[1],
        tenant_id: args[2], client_id: args[3], object_id: args[4],
        subject: args[5], context_id: args[6],
        issued_at_ms: String(args[7]), expires_at_ms: String(args[8]),
        nonce_iv: args[9], nonce_ciphertext: args[10], nonce_tag: args[11],
      });
      return { rows: [{ created: true }] };
    }
    if (statement === "SELECT * FROM public.matchdesk_consume_workforce_step_up_challenge($1,$2)") {
      const candidate = this.rows.get(args[0]);
      if (!candidate || candidate.pending_digest !== args[1]) return { rows: [] };
      this.rows.delete(args[0]);
      return { rows: [candidate] };
    }
    throw new Error("Unsupported SQL operation");
  }
}
const store = (db = new FakeSql(), key = Buffer.alloc(32, 31), parent = PENDING) =>
  new PostgresWorkforceStepUpStore(db, policy, key, parent);

test("fixed SQL encrypts nonce and only exact pending parent can consume", async () => {
  const db = new FakeSql(), s = store(db);
  assert.equal(await s.create(attempt), true);
  const row = db.rows.get(STATE);
  assert.equal(row.nonce_ciphertext.length, 43);
  assert.equal(row.nonce_iv.length, 12);
  assert.equal(row.nonce_tag.length, 16);
  assert.equal(row.nonce_ciphertext.includes(Buffer.from(attempt.nonce)), false);
  assert.equal(db.calls[0].args.includes(attempt.nonce), false);
  assert.equal(await store(db, Buffer.alloc(32, 31),
    createHash("sha256").update("other-parent").digest("hex")).consume(STATE), null);
  assert.deepEqual(await s.consume(STATE), attempt);
  assert.equal(await s.consume(STATE), null);
  assert.equal(db.calls.length, 4);
});

test("wrong cryptographic key and mutated AAD fail after single consumption", async () => {
  for (const tamper of [
    (row) => { row.context_id = "c2"; },
    (row) => { row.nonce_ciphertext = Buffer.alloc(43); },
    (row) => { row.issued_at_ms = "1000001000"; },
    (row) => { row.nonce_tag = Buffer.alloc(16); },
    (row) => { row.expires_at_ms = "9007199254740993"; },
  ]) {
    const db = new FakeSql();
    await store(db).create(attempt);
    tamper(db.rows.get(STATE));
    await assert.rejects(store(db).consume(STATE), /persistence denied/);
    assert.equal(await store(db).consume(STATE), null);
  }
  const db = new FakeSql();
  await store(db).create(attempt);
  await assert.rejects(store(db, Buffer.alloc(32, 32)).consume(STATE),
    /persistence denied/);
  assert.equal(await store(db).consume(STATE), null);
});

test("concurrent claim has exactly one winner", async () => {
  const db = new FakeSql(), s = store(db);
  await s.create(attempt);
  const outcomes = await Promise.all([s.consume(STATE), s.consume(STATE)]);
  assert.equal(outcomes.filter(Boolean).length, 1);
  assert.equal(outcomes.filter(x => x === null).length, 1);
});

test("invalid actor, digest, context and host dependencies reject before SQL", async () => {
  const db = new FakeSql(), s = store(db);
  for (const invalid of [
    { tenantId: "foreign" }, { clientId: "other" },
    { objectId: "invalid" }, { contextId: "c2" },
    { expiresAtSeconds: 1000900 }, { nonce: "bad nonce" },
    { subject: "" }, { stateDigest: "attacker" },
  ]) await assert.rejects(s.create({ ...attempt, ...invalid }), /persistence denied/);
  await assert.rejects(s.consume("bad"), /persistence denied/);
  assert.equal(db.calls.length, 0);
  assert.throws(() => store(db, Buffer.alloc(31)), /Protected step-up/);
  assert.throws(() => store(db, Buffer.alloc(32), "bad"), /Protected step-up/);
});

test("database faults, foreign rows and shape corruption disclose no internals", async () => {
  const db = new FakeSql(), s = store(db);
  db.fail = true;
  await assert.rejects(s.create(attempt), e => /persistence denied/.test(e.message) &&
    !e.message.includes("credential"));
  await assert.rejects(s.consume(STATE), e => /persistence denied/.test(e.message) &&
    !e.message.includes("credential"));
  db.fail = false;
  await s.create(attempt);
  db.rows.get(STATE).unexpected = "privileged";
  await assert.rejects(s.consume(STATE), /persistence denied/);
  assert.equal(await s.consume(STATE), null);
});
