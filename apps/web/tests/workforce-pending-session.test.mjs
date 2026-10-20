/** Pending workforce vault tests: no production identity, sessions or secrets.
 *
 * Test JWT-shaped values are deliberately nonworking synthetic strings. The
 * fake driver models two fixed database functions. Separate real PostgreSQL
 * CI tests prove role privileges, database time and tombstone persistence.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { PostgresPendingWorkforceSessions } from "../src/workforce/pending-session.ts";

const TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const CLIENT = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff";
const API = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa";
const OID = "dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb";
const ISSUER = "https://login.microsoftonline.com/" + TENANT + "/v2.0";
const TOKEN = ["synthetic1", "synthetic2", "notasignature"].join(".");
const KEY = Buffer.alloc(32, 93);
const NOW = 1_760_000_000_000;
const POLICY = {
  tenantId: TENANT, clientId: CLIENT, apiResourceAppId: API,
  publicOrigin: "https://operator.example.test",
  delegatedApiScope: "api://" + API + "/MatchDesk.Producer.Access",
};

function exchange(change = {}) {
  return {
    tenantId: TENANT, issuer: ISSUER, subject: "test-person",
    objectId: OID, clientId: CLIENT,
    delegatedAccessToken: TOKEN,
    expiresAtSeconds: NOW / 1000 + 600,
    ...change,
  };
}

/** Only the two exact SECURITY DEFINER calls are available to this fake role. */
class FakeSql {
  constructor() {
    this.rows = new Map();
    this.calls = [];
    this.error = null;
    this.badRows = null;
  }
  async query(sql, parameters) {
    if (this.error) throw this.error;
    this.calls.push({ sql, parameters });
    if (this.badRows !== null) return { rows: this.badRows };
    if (sql === "SELECT public.matchdesk_prepare_workforce_session(" +
        "$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) AS prepared") {
      const digest = parameters[0];
      if (this.rows.has(digest)) return { rows: [{ prepared: false }] };
      this.rows.set(digest, {
        fields: parameters, revoked: false,
      });
      return { rows: [{ prepared: true }] };
    }
    if (sql === "SELECT public.matchdesk_revoke_workforce_session($1) AS revoked") {
      const row = this.rows.get(parameters[0]);
      if (!row || row.revoked) return { rows: [{ revoked: false }] };
      row.revoked = true;
      return { rows: [{ revoked: true }] };
    }
    throw new Error("Unexpected direct-table or unrestricted SQL");
  }
}

const vault = (db = new FakeSql(), key = KEY, policy = POLICY) =>
  new PostgresPendingWorkforceSessions(db, policy, key);

test("a signed-token candidate is AES-256-GCM sealed and never becomes a cookie", async () => {
  const db = new FakeSql();
  const receipt = await vault(db).prepare(exchange(), NOW);
  assert.match(receipt.recordDigest, /^[0-9a-f]{64}$/);
  assert.equal(receipt.expiresAtMs, NOW + 600_000);
  assert.equal(db.calls.length, 1);
  const row = db.rows.get(receipt.recordDigest);
  assert.equal(row.fields[0], receipt.recordDigest);
  assert.equal(row.fields[1], TENANT);
  assert.equal(row.fields[2], ISSUER);
  assert.equal(row.fields[3], "test-person");
  assert.equal(row.fields[4], OID);
  assert.equal(row.fields[5], CLIENT);
  assert.equal(row.fields[6], NOW);
  assert.equal(row.fields[7], NOW + 600_000);
  assert.equal(row.fields[8].length, 12);
  assert.ok(row.fields[9].length > 16);
  assert.equal(row.fields[10].length, 16);
  assert.equal(row.fields[9].includes(Buffer.from(TOKEN)), false);
  assert.ok(!JSON.stringify(row.fields.slice(0, 8)).includes(TOKEN));
  assert.equal("cookie" in receipt, false);
  assert.equal("delegatedAccessToken" in receipt, false);
  assert.equal("activate" in vault(db), false);
});

test("pending records always fail the BFF resolver before and after revocation", async () => {
  const db = new FakeSql();
  const s = vault(db);
  const receipt = await s.prepare(exchange(), NOW);
  const count = db.calls.length;
  assert.equal(await s.resolve("s".repeat(43)), null);
  assert.equal(await s.resolve(receipt.recordDigest), null);
  assert.equal(db.calls.length, count);
  assert.equal(await s.revoke(receipt.recordDigest), true);
  assert.equal(await s.resolve("s".repeat(43)), null);
  assert.equal(db.calls.length, count + 1);
  assert.equal(db.rows.get(receipt.recordDigest).revoked, true);
});

test("one-time revocation retains a tombstone and cannot be undone", async () => {
  const db = new FakeSql();
  const s = vault(db);
  const receipt = await s.prepare(exchange(), NOW);
  assert.equal(await s.revoke(receipt.recordDigest), true);
  assert.equal(await s.revoke(receipt.recordDigest), false);
  assert.equal(await s.revoke("a".repeat(64)), false);
  assert.equal(db.rows.size, 1);
  assert.equal(db.rows.get(receipt.recordDigest).revoked, true);
  assert.ok(db.calls.every(({ sql }) => sql.startsWith("SELECT public.matchdesk_")));
});

test("independent pending records have unrelated digests, IVs and ciphertext", async () => {
  const db = new FakeSql();
  const s = vault(db);
  const a = await s.prepare(exchange(), NOW);
  const b = await s.prepare(exchange(), NOW);
  assert.notEqual(a.recordDigest, b.recordDigest);
  const first = db.rows.get(a.recordDigest).fields;
  const second = db.rows.get(b.recordDigest).fields;
  assert.notDeepEqual(first[8], second[8]);
  assert.notDeepEqual(first[9], second[9]);
});

test("host never stores token when identity, scope or expiry is inconsistent", async () => {
  const invalid = [
    { tenantId: "other" }, { issuer: "https://foreign.invalid/v2.0" },
    { objectId: "invalid" }, { clientId: "invalid" }, { subject: "" },
    { subject: "x".repeat(257) }, { delegatedAccessToken: "" },
    { delegatedAccessToken: "not-a-bearer" },
    { delegatedAccessToken: "q".repeat(8193) },
    { expiresAtSeconds: NOW / 1000 - 10 },
    { expiresAtSeconds: "untrusted" },
    { expiresAtSeconds: Number.MAX_SAFE_INTEGER },
  ];
  for (const item of invalid) {
    const db = new FakeSql();
    await assert.rejects(vault(db).prepare(exchange(item), NOW), /session denied/);
    assert.equal(db.calls.length, 0);
  }
});

test("a long delegated token is capped to fifteen minutes at the host boundary", async () => {
  const db = new FakeSql();
  const receipt = await vault(db).prepare(exchange({
    expiresAtSeconds: NOW / 1000 + 3600,
  }), NOW);
  assert.equal(receipt.expiresAtMs, NOW + 900_000);
});

test("wrong key size and unapproved tenant or scope cannot instantiate the vault", () => {
  for (const key of [Buffer.alloc(31), Buffer.alloc(33)]) {
    assert.throws(() => vault(new FakeSql(), key), /approved host dependencies/);
  }
  for (const change of [
    { tenantId: "common" },
    { apiResourceAppId: "not-a-guid" },
    { clientId: "not-a-guid" },
    { delegatedApiScope: "api://another/MatchDesk.Producer.Access" },
    { publicOrigin: "http://operator.example.test" },
    { publicOrigin: "https://operator.example.test.evil.invalid" },
    { publicOrigin: "https://operator.example.test/path" },
    { publicOrigin: "https://operator.example.test?redirect=evil" },
    { publicOrigin: "https://user:pass@operator.example.test" },
  ]) {
    assert.throws(() => vault(new FakeSql(), KEY, { ...POLICY, ...change }),
      /approved host dependencies/);
  }
});

test("database faults and unexpected shapes fail closed without leaking credentials", async () => {
  for (const error of [new Error("private DB credential"), new Error("private key")]) {
    const db = new FakeSql();
    db.error = error;
    await assert.rejects(vault(db).prepare(exchange(), NOW), (e) =>
      /session denied/.test(e.message) && !/private/.test(e.message));
    await assert.rejects(vault(db).revoke("b".repeat(64)), (e) =>
      /session denied/.test(e.message) && !/private/.test(e.message));
  }
  const db = new FakeSql();
  db.badRows = [{ prepared: "true" }];
  await assert.rejects(vault(db).prepare(exchange(), NOW), /session denied/);
  db.badRows = [{ revoked: "true" }];
  await assert.rejects(vault(db).revoke("b".repeat(64)), /session denied/);
  await assert.rejects(vault(db).revoke("injected"), /session denied/);
});
