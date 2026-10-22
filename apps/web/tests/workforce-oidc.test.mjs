/** Credential-free workforce OIDC protocol tests (NOT live Entra authentication).
 *
 * This store models a single atomic consume in memory. A real host still needs
 * durable persistence, validated code exchange, signed token verification,
 * workforce entitlement/step-up checks and secure session/cookie issuance.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  beginWorkforceOidc,
  clearWorkforceOidcBindingCookie,
  consumeWorkforceOidcCallback,
  workforceOidcEndpoints,
} from '../src/workforce/oidc.ts';

const PUBLIC = 'https://operator.example.test';
const TENANT = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const CLIENT = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff';
const RESOURCE = 'cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa';
const POLICY = {
  publicOrigin: PUBLIC, tenantId: TENANT, clientId: CLIENT,
  apiResourceAppId: RESOURCE,
  delegatedApiScope: 'api://' + RESOURCE + '/MatchDesk.Producer.Access',
};
const NOW = 1_000_000;

function store() {
  const attempts = new Map();
  const out = {
    attempts, creates: 0, consumes: 0,
    async create(attempt) {
      out.creates += 1;
      if (attempts.has(attempt.stateDigest)) return false;
      attempts.set(attempt.stateDigest, attempt);
      return true;
    },
    async consume(hash) {
      out.consumes += 1;
      const result = attempts.get(hash) ?? null;
      attempts.delete(hash);
      return result;
    },
  };
  return out;
}

function startRequest(headers = {}) {
  return new Request(PUBLIC + '/api/workforce/oidc/start', {
    method: 'POST',
    headers: {
      Host: 'operator.example.test', Origin: PUBLIC,
      'Sec-Fetch-Site': 'same-origin', ...headers,
    },
  });
}

function callbackRequest(begin, overrides = {}) {
  const url = new URL(PUBLIC + '/api/workforce/oidc/callback');
  url.searchParams.set('state', new URL(begin.authorizationUrl).searchParams.get('state'));
  url.searchParams.set('iss', workforceOidcEndpoints(POLICY).issuer);
  url.searchParams.set('code', 'safe-synthetic-authorization-code');
  if (overrides.query) overrides.query(url);
  return new Request(overrides.url ?? url.toString(), {
    method: overrides.method ?? 'GET',
    headers: {
      Host: 'operator.example.test',
      'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Dest': 'document',
      Cookie: begin.bindingCookie.split(';')[0],
      ...overrides.headers,
    },
  });
}

async function pending() {
  const attempts = store();
  const start = await beginWorkforceOidc(POLICY, attempts, startRequest(), NOW);
  return { attempts, start };
}

test('PKCE S256, random nonce/state and browser-binding cookie are independent', async () => {
  const attempts = store();
  const start = await beginWorkforceOidc(POLICY, attempts, startRequest(), NOW);
  const url = new URL(start.authorizationUrl);
  const record = [...attempts.attempts.values()][0];
  const cookie = start.bindingCookie.split(';')[0].split('=')[1];
  assert.equal(url.origin, 'https://login.microsoftonline.com');
  assert.equal(url.pathname, '/' + TENANT + '/oauth2/v2.0/authorize');
  assert.equal(url.searchParams.get('client_id'), CLIENT);
  assert.equal(url.searchParams.get('response_type'), 'code');
  assert.equal(url.searchParams.get('response_mode'), 'query');
  assert.equal(url.searchParams.get('redirect_uri'), PUBLIC + '/api/workforce/oidc/callback');
  assert.equal(url.searchParams.get('scope'), 'openid ' + POLICY.delegatedApiScope);
  assert.equal(url.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(url.searchParams.get('code_challenge'),
    createHash('sha256').update(record.codeVerifier).digest('base64url'));
  assert.equal(url.searchParams.get('nonce'), record.nonce);
  assert.equal(record.stateDigest, createHash('sha256').update(url.searchParams.get('state')).digest('hex'));
  assert.equal(record.bindingDigest, createHash('sha256').update(cookie).digest('hex'));
  assert.equal(record.expiresAtMs - record.issuedAtMs, 300_000);
  assert.notEqual(cookie, url.searchParams.get('state'));
  assert.notEqual(record.nonce, record.codeVerifier);
  assert.ok(start.bindingCookie.startsWith('__Host-md-workforce-oidc='));
  assert.match(start.bindingCookie, /Max-Age=300; Path=\/; Secure; HttpOnly; SameSite=Lax$/);
  assert.equal(start.authorizationUrl.includes(record.codeVerifier), false);
  assert.equal(attempts.creates, 1);
});

test('valid consumed callback returns only a host-internal, pinned exchange', async () => {
  const { attempts, start } = await pending();
  const result = await consumeWorkforceOidcCallback(
    POLICY, attempts, callbackRequest(start), NOW + 50_000,
  );
  assert.deepEqual(result, {
    issuer: 'https://login.microsoftonline.com/' + TENANT + '/v2.0',
    clientId: CLIENT,
    tokenEndpoint: 'https://login.microsoftonline.com/' + TENANT + '/oauth2/v2.0/token',
    redirectUri: PUBLIC + '/api/workforce/oidc/callback',
    nonce: new URL(start.authorizationUrl).searchParams.get('nonce'),
    codeVerifier: result.codeVerifier,
    authorizationCode: 'safe-synthetic-authorization-code',
  });
  assert.match(result.codeVerifier, /^[A-Za-z0-9_-]{43}$/);
  assert.equal(attempts.consumes, 1);
  assert.equal(attempts.attempts.size, 0);
  await assert.rejects(
    consumeWorkforceOidcCallback(POLICY, attempts, callbackRequest(start), NOW + 50_001),
    /sign-in denied/,
  );
});

test('missing, altered and duplicate one-use cookies burn the state, not a session', async () => {
  const malicious = [
    { Cookie: '' },
    { Cookie: '__Host-md-workforce-oidc=' + 'b'.repeat(43) },
    { Cookie: '__Host-md-workforce-oidc=' + 'b'.repeat(43) +
      '; __Host-md-workforce-oidc=' + 'c'.repeat(43) },
  ];
  for (const headers of malicious) {
    const { attempts, start } = await pending();
    await assert.rejects(
      consumeWorkforceOidcCallback(
        POLICY, attempts, callbackRequest(start, { headers }), NOW + 5_000,
      ), /sign-in denied/,
    );
    assert.equal(attempts.consumes, 1);
    await assert.rejects(
      consumeWorkforceOidcCallback(POLICY, attempts, callbackRequest(start), NOW + 5_001),
      /sign-in denied/,
    );
  }
});

test('provider error and issuer substitution consume state, never return an exchange', async () => {
  for (const query of [
    (u) => u.searchParams.set('iss', 'https://login.microsoftonline.com/common/v2.0'),
    (u) => {
      u.searchParams.delete('code');
      u.searchParams.set('error', 'access_denied');
    },
  ]) {
    const { attempts, start } = await pending();
    await assert.rejects(
      consumeWorkforceOidcCallback(
        POLICY, attempts, callbackRequest(start, { query }), NOW + 10_000,
      ), /sign-in denied/,
    );
    assert.equal(attempts.consumes, 1);
    assert.equal(attempts.attempts.size, 0);
  }
});

test('exact expiry boundary and future-dated state fail closed', async () => {
  for (const time of [NOW - 1, NOW + 300_000, NOW + 301_000]) {
    const { attempts, start } = await pending();
    await assert.rejects(
      consumeWorkforceOidcCallback(POLICY, attempts, callbackRequest(start), time),
      /sign-in denied/,
    );
    assert.equal(attempts.attempts.size, 0);
  }
});

test('duplicate, mixed, unknown and oversized callback fields are rejected', async () => {
  const queries = [
    (u) => u.searchParams.append('state', 'a'.repeat(43)),
    (u) => u.searchParams.set('target', 'https://other.invalid'),
    (u) => u.searchParams.set('error', 'access_denied'),
    (u) => u.searchParams.set('code', 'x'.repeat(2050)),
    (u) => u.searchParams.set('state', 'wrong'),
  ];
  for (const query of queries) {
    const { attempts, start } = await pending();
    await assert.rejects(
      consumeWorkforceOidcCallback(POLICY, attempts,
        callbackRequest(start, { query }), NOW + 5_000), /sign-in denied/,
    );
  }
});

test('callback requires exact top-level navigation and rejects host spoofing', async () => {
  const scenarios = [
    { headers: { Host: 'attacker.invalid' } },
    { headers: { 'Sec-Fetch-Mode': 'cors' } },
    { headers: { 'Sec-Fetch-Dest': 'empty' } },
    { headers: { 'Sec-Fetch-Site': 'bogus' } },
    { headers: { Origin: PUBLIC } },
    { headers: { Forwarded: 'host=attacker.invalid' } },
    { headers: { Authorization: 'Bearer rogue' } },
    { url: PUBLIC + '/api/workforce/oidc/callback?state=invalid#fragment' },
    { method: 'POST' },
  ];
  for (const scenario of scenarios) {
    const { attempts, start } = await pending();
    await assert.rejects(
      consumeWorkforceOidcCallback(
        POLICY, attempts, callbackRequest(start, scenario), NOW + 10_000,
      ), /sign-in denied/,
    );
  }
});

test('start requires exact same-origin POST and stores nothing on invalid input', async () => {
  const requests = [
    startRequest({ Origin: 'https://attacker.invalid' }),
    startRequest({ 'Sec-Fetch-Site': 'cross-site' }),
    startRequest({ Host: 'attacker.invalid' }),
    startRequest({ Forwarded: 'host=attacker.invalid' }),
    new Request(PUBLIC + '/api/workforce/oidc/start?returnUrl=https://evil.invalid', {
      method: 'POST', headers: { Host: 'operator.example.test',
        Origin: PUBLIC, 'Sec-Fetch-Site': 'same-origin' },
    }),
  ];
  for (const request of requests) {
    const attempts = store();
    await assert.rejects(beginWorkforceOidc(POLICY, attempts, request, NOW), /sign-in denied/);
    assert.equal(attempts.creates, 0);
  }
});

test('policy disallows shared issuers, mixed resources and non-HTTPS origins', () => {
  const invalid = [
    { tenantId: 'common' }, { clientId: 'not-a-guid' },
    { apiResourceAppId: 'not-a-guid' },
    { delegatedApiScope: 'openid offline_access' },
    { delegatedApiScope: 'api://' + TENANT + '/MatchDesk.Producer.Access' },
    { publicOrigin: 'http://operator.example.test' },
    { publicOrigin: PUBLIC + '/redirect' },
    { publicOrigin: 'https://user:pass@operator.example.test' },
  ];
  for (const change of invalid) {
    assert.throws(() => workforceOidcEndpoints({ ...POLICY, ...change }), /OIDC/);
  }
});

test('store outage or rejected state issuance cannot create a browser redirect', async () => {
  const attempts = store();
  attempts.create = async () => false;
  await assert.rejects(beginWorkforceOidc(POLICY, attempts, startRequest(), NOW),
    /sign-in denied/);
  attempts.create = async () => { throw new Error('private database credentials'); };
  await assert.rejects(beginWorkforceOidc(POLICY, attempts, startRequest(), NOW),
    (error) => !error.message.includes('private database credentials'));
  const { start } = await pending();
  const outage = store();
  outage.consume = async () => { throw new Error('private database credentials'); };
  await assert.rejects(
    consumeWorkforceOidcCallback(POLICY, outage, callbackRequest(start), NOW + 5_000),
    (error) => !error.message.includes('private database credentials'),
  );
});

test('clearing the temporary cookie never sets a producer session or authorizes anything', () => {
  const clear = clearWorkforceOidcBindingCookie();
  assert.ok(clear.startsWith('__Host-md-workforce-oidc=; Max-Age=0;'));
  assert.match(clear, /Secure; HttpOnly; SameSite=Lax$/);
  assert.equal(clear.includes('__Host-md-workforce='), false);
});
