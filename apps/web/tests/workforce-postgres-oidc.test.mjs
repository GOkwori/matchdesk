/** Encrypted workforce OIDC store unit tests; all credentials are synthetic.
 *
 * The fake below models one committed PostgreSQL statement per query; the
 * independent real PostgreSQL qualification validates function privileges,
 * durable replay tombstones and concurrent consumption ordering.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { beginWorkforceOidc, consumeWorkforceOidcCallback } from '../src/workforce/oidc.ts';
import { PostgresWorkforceOidcAttemptStore } from '../src/workforce/postgres-oidc.ts';

const TENANT = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const CLIENT = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff';
const RESOURCE = 'cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa';
const PUBLIC = 'https://operator.example.test';
const POLICY = {
  publicOrigin: PUBLIC, tenantId: TENANT, clientId: CLIENT,
  apiResourceAppId: RESOURCE,
  delegatedApiScope: 'api://' + RESOURCE + '/MatchDesk.Producer.Access',
};
const KEY = Buffer.alloc(32, 113);
const NOW = 1_000_000;
const hash = (value) => createHash('sha256').update(value).digest('hex');

function attempt() {
  return {
    stateDigest: hash('synthetic-state'),
    bindingDigest: hash('synthetic-binding'),
    issuer: 'https://login.microsoftonline.com/' + TENANT + '/v2.0',
    clientId: CLIENT,
    redirectUri: PUBLIC + '/api/workforce/oidc/callback',
    issuedAtMs: NOW,
    expiresAtMs: NOW + 300_000,
    nonce: 'n'.repeat(43),
    codeVerifier: 'v'.repeat(43),
  };
}

/** Return real-like bytea Buffers and string-form PostgreSQL BIGINTs. */
class FakeSql {
  constructor() {
    this.rows = new Map();
    this.calls = [];
    this.fail = false;
  }

  async query(sql, values) {
    if (this.fail) throw new Error('private PostgreSQL connection string');
    this.calls.push({ sql, values });
    if (sql.startsWith('SELECT public.matchdesk_create_workforce_oidc_attempt(')) {
      const [state_digest, binding_digest, issuer, client_id, redirect_uri,
        issued_at_ms, expires_at_ms, secret_iv, secret_ciphertext, secret_tag] = values;
      if (this.rows.has(state_digest)) return { rows: [{ created: false }] };
      this.rows.set(state_digest, {
        state_digest, binding_digest, issuer, client_id, redirect_uri,
        issued_at_ms: String(issued_at_ms),
        expires_at_ms: String(expires_at_ms),
        secret_iv, secret_ciphertext, secret_tag,
      });
      return { rows: [{ created: true }] };
    }
    if (sql === 'SELECT * FROM public.matchdesk_consume_workforce_oidc_attempt($1)') {
      const row = this.rows.get(values[0]);
      if (!row) return { rows: [] };
      this.rows.delete(values[0]);
      return { rows: [row] };
    }
    throw new Error('Unexpected or unrestricted SQL statement');
  }
}

function store(db = new FakeSql(), key = KEY) {
  return new PostgresWorkforceOidcAttemptStore(db, POLICY, key);
}

test('AES-256-GCM stores no raw nonce, PKCE or browser binding', async () => {
  const db = new FakeSql();
  const a = attempt();
  assert.equal(await store(db).create(a), true);
  const row = db.rows.get(a.stateDigest);
  assert.equal(row.state_digest, a.stateDigest);
  assert.equal(row.binding_digest, a.bindingDigest);
  assert.equal(row.secret_iv.length, 12);
  assert.equal(row.secret_ciphertext.length, 87);
  assert.equal(row.secret_tag.length, 16);
  assert.equal(row.secret_ciphertext.includes(Buffer.from(a.nonce)), false);
  assert.equal(row.secret_ciphertext.includes(Buffer.from(a.codeVerifier)), false);
  assert.equal(db.calls[0].values.some((p) => p === a.nonce || p === a.codeVerifier), false);
  assert.deepEqual(await store(db).consume(a.stateDigest), a);
  assert.equal(db.rows.size, 0);
});

test('duplicate state and replay fail without ever overwriting a tombstone', async () => {
  const db = new FakeSql();
  const s = store(db);
  const a = attempt();
  assert.equal(await s.create(a), true);
  assert.equal(await s.create(a), false);
  assert.deepEqual(await s.consume(a.stateDigest), a);
  assert.equal(await s.consume(a.stateDigest), null);
  assert.equal(db.calls.length, 4);
});

test('a synthetic start/callback completes using the encrypted store contract', async () => {
  const db = new FakeSql();
  const s = store(db);
  const startRequest = new Request(PUBLIC + '/api/workforce/oidc/start', {
    method: 'POST',
    headers: {
      Host: 'operator.example.test', Origin: PUBLIC,
      'Sec-Fetch-Site': 'same-origin',
    },
  });
  const begun = await beginWorkforceOidc(POLICY, s, startRequest, NOW);
  const callback = new URL(PUBLIC + '/api/workforce/oidc/callback');
  callback.searchParams.set('state', new URL(begun.authorizationUrl).searchParams.get('state'));
  callback.searchParams.set('iss', 'https://login.microsoftonline.com/' + TENANT + '/v2.0');
  callback.searchParams.set('code', 'synthetic-auth-code');
  const finishRequest = new Request(callback, {
    method: 'GET',
    headers: {
      Host: 'operator.example.test',
      'Sec-Fetch-Site': 'cross-site',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Dest': 'document',
      Cookie: begun.bindingCookie.split(';')[0],
    },
  });
  const result = await consumeWorkforceOidcCallback(POLICY, s, finishRequest, NOW + 1_000);
  assert.equal(result.authorizationCode, 'synthetic-auth-code');
  assert.match(result.codeVerifier, /^[A-Za-z0-9_-]{43}$/);
  assert.equal(db.rows.size, 0);
  await assert.rejects(
    consumeWorkforceOidcCallback(POLICY, s, finishRequest, NOW + 1_001),
    /sign-in denied/,
  );
});

test('concurrent claims produce exactly one winning server-side exchange', async () => {
  const db = new FakeSql();
  const s = store(db);
  const a = attempt();
  await s.create(a);
  const outcomes = await Promise.all([s.consume(a.stateDigest), s.consume(a.stateDigest)]);
  assert.equal(outcomes.filter((value) => value !== null).length, 1);
  assert.equal(outcomes.filter((value) => value === null).length, 1);
});

test('substituted immutable metadata, ciphertext and auth tag fail closed', async () => {
  const changes = [
    (r) => { r.binding_digest = 'f'.repeat(64); },
    (r) => { r.issuer = 'https://foreign.invalid/v2.0'; },
    (r) => { r.client_id = 'other-client'; },
    (r) => { r.redirect_uri = 'https://attacker.invalid/callback'; },
    (r) => { r.issued_at_ms = '1000001'; },
    (r) => { r.expires_at_ms = '1300001'; },
    (r) => { r.secret_iv = Buffer.alloc(12, 7); },
    (r) => { r.secret_ciphertext = Buffer.alloc(87, 0); },
    (r) => { r.secret_tag = Buffer.alloc(16, 0); },
    (r) => { r.expires_at_ms = '9007199254740993'; },
    (r) => { r.secret_ciphertext = 'hex string'; },
  ];
  for (const change of changes) {
    const db = new FakeSql();
    const s = store(db);
    const a = attempt();
    await s.create(a);
    change(db.rows.get(a.stateDigest));
    await assert.rejects(s.consume(a.stateDigest), /Workforce OIDC state denied/);
    assert.equal(await s.consume(a.stateDigest), null);
  }
});

test('wrong encryption key cannot reveal nonce or verifier', async () => {
  const db = new FakeSql();
  const a = attempt();
  await store(db).create(a);
  await assert.rejects(
    store(db, Buffer.alloc(32, 114)).consume(a.stateDigest),
    /Workforce OIDC state denied/,
  );
  assert.equal(db.rows.size, 0);
});

test('direct table queries, SQL identifiers and raw state never reach the executor', async () => {
  const db = new FakeSql();
  const s = store(db);
  const a = attempt();
  await s.create(a);
  await s.consume(a.stateDigest);
  assert.equal(db.calls.length, 2);
  assert.equal(db.calls[0].sql.startsWith('SELECT public.matchdesk_create_workforce_oidc_attempt('), true);
  assert.equal(db.calls[1].sql, 'SELECT * FROM public.matchdesk_consume_workforce_oidc_attempt($1)');
  assert.ok(db.calls.every(({ sql }) => !sql.includes('DROP') && !sql.includes('FROM public.matchdesk_workforce_oidc_attempts')));
  assert.equal(db.calls[1].values[0], a.stateDigest);
});

test('invalid policy, wrong host key or foreign issuer is rejected before SQL', async () => {
  const db = new FakeSql();
  for (const change of [
    { tenantId: 'common' },
    { clientId: 'invalid' },
    { apiResourceAppId: 'invalid' },
    { delegatedApiScope: 'api://wrong/Access' },
    { publicOrigin: 'http://operator.example.test' },
  ]) {
    assert.throws(() => new PostgresWorkforceOidcAttemptStore(db, {
      ...POLICY, ...change,
    }, KEY));
  }
  for (const key of [Buffer.alloc(31), Buffer.alloc(33)]) {
    assert.throws(() => store(db, key), /256-bit/);
  }
  const bad = { ...attempt(), issuer: 'https://external.ciamlogin.com/issuer' };
  await assert.rejects(store(db).create(bad), /Workforce OIDC state denied/);
  await assert.rejects(store(db).consume('injected-string'), /Workforce OIDC state denied/);
  assert.equal(db.calls.length, 0);
});

test('database faults and unexpected result shapes never disclose credentials', async () => {
  const db = new FakeSql();
  const s = store(db);
  db.fail = true;
  await assert.rejects(s.create(attempt()), (e) =>
    !e.message.includes('private PostgreSQL') && /state denied/.test(e.message));
  await assert.rejects(s.consume(attempt().stateDigest), (e) =>
    !e.message.includes('private PostgreSQL') && /state denied/.test(e.message));
  const malformed = { query: async () => ({ rows: [{ created: 'true' }] }) };
  await assert.rejects(store(malformed).create(attempt()), /state denied/);
});
