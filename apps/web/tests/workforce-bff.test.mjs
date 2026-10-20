/** Synthetic host tests for the default-disabled Next.js workforce BFF contract.
 *
 * These tests verify transport, CSRF and response boundaries, NOT live Entra
 * identity, provider MFA, session issuance or production operator authority.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createWorkforceBff } from '../src/workforce/bff.ts';

const PUBLIC = 'https://matchdesk.example.test';
const BACKEND = 'https://private-api.example.test';
const TENANT = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const ISSUER = 'https://login.microsoftonline.com/' + TENANT + '/v2.0';
const SID = 'synthetic-session-1';
const OUTPUT = 'synthetic-output-1';
const COOKIE = 's'.repeat(43);
const CSRF = 'c'.repeat(43);
const ACCESS = ['eyJhbGciOiJSUzI1NiJ9', 'eyJzdWIiOiIxIn0', 'signaturetest123456'].join('.');
const SEGMENTS = ['sessions', SID, 'cases', OUTPUT, 'create'];

function req(action = 'create', overrides = {}) {
  const path = overrides.path ??
    '/api/workforce/producer/sessions/' + SID + '/cases/' + OUTPUT + '/' + action;
  return new Request(overrides.url ?? PUBLIC + path, {
    method: overrides.method ?? 'POST',
    headers: {
      Host: 'matchdesk.example.test',
      Origin: PUBLIC,
      'Sec-Fetch-Site': 'same-origin',
      'Content-Type': 'application/json',
      Cookie: '__Host-md-workforce=' + COOKIE,
      'X-CSRF-Token': CSRF,
      ...overrides.headers,
    },
    body: overrides.body ?? '{"binding":{"item_id":"synthetic"}}',
  });
}

function fixture(overrides = {}) {
  const calls = [];
  const session = {
    issuer: ISSUER, tenantId: TENANT, subject: 'test-producer',
    roles: ['producer'], permittedSessions: [SID],
    delegatedToken: ACCESS, csrfSecret: CSRF, expiresAtMs: 1_060_000,
    ...overrides.session,
  };
  const host = {
    publicOrigin: PUBLIC, backendOrigin: BACKEND,
    trustedIssuer: ISSUER, trustedTenantId: TENANT,
    nowMs: () => 1_000_000,
    sessions: { resolve: async (cookie) => cookie === COOKIE ? session : null },
    async fetchBackend(url, init) {
      calls.push({ url, init });
      const action = url.split('/').at(-1);
      return Response.json({
        session_id: SID, output_id: OUTPUT,
        generation: action === 'create' ? 1 : 2,
        item_version: 1,
        ...(action === 'reverify'
          ? { mode: 'grant_backed_development_only', approval_enabled: false }
          : { mode: 'grant_backed_development_only', action }),
        review_status: action === 'reverify' ? 'ready_for_decision'
          : action === 'approve' ? 'approved'
          : action === 'reject' ? 'rejected' : 'pending_verification',
        publication_enabled: false, private_marker: 'never-return-me',
      }, {
        status: action === 'create' ? 201 : 200,
        headers: { 'Set-Cookie': 'forged=not-relayed' },
      });
    },
    ...overrides.host,
  };
  return { calls, session, host, handle: createWorkforceBff(host) };
}

test('the shipped BFF is unavailable without an injected trusted host', async () => {
  const result = await createWorkforceBff(null)(req(), SEGMENTS);
  assert.equal(result.status, 404);
  assert.match((await result.json()).detail, /disabled/);
  assert.equal(result.headers.get('cache-control'), 'no-store, max-age=0');
});

test('a fixed-target create sends only a server-owned bearer and sanitises the receipt', async () => {
  const { calls, handle } = fixture();
  const result = await handle(req(), SEGMENTS);
  assert.equal(result.status, 201);
  assert.equal(result.headers.get('set-cookie'), null);
  assert.equal(result.headers.get('cache-control'), 'no-store, max-age=0');
  assert.deepEqual(await result.json(), {
    session_id: SID, output_id: OUTPUT, generation: 1,
    item_version: 1, review_status: 'pending_verification',
    action: 'create', publication_enabled: false,
  });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url,
    BACKEND + '/api/workforce/producer/sessions/' + SID + '/cases/' + OUTPUT + '/create');
  assert.equal(calls[0].init.headers.Authorization, 'Bearer ' + ACCESS);
  assert.equal(calls[0].init.headers.Cookie, undefined);
  assert.equal(calls[0].init.headers['X-CSRF-Token'], undefined);
  assert.equal(calls[0].init.cache, 'no-store');
  assert.equal(calls[0].init.redirect, 'manual');
  assert.equal(calls[0].init.credentials, 'omit');
});

test('only the five exact actions can reach the backend', async () => {
  for (const action of ['edit', 'reverify', 'approve', 'reject']) {
    const { calls, handle } = fixture();
    const result = await handle(req(action), ['sessions', SID, 'cases', OUTPUT, action]);
    assert.equal(result.status, 200, action);
    assert.equal((await result.json()).action, action);
    assert.ok(calls[0].url.endsWith('/' + action));
  }
  const { calls, handle } = fixture();
  const result = await handle(req('publish'), ['sessions', SID, 'cases', OUTPUT, 'publish']);
  assert.equal(result.status, 404);
  assert.equal(calls.length, 0);
});

test('encoded paths, arbitrary segments, and query strings cannot retarget the proxy', async () => {
  const paths = [
    '/api/workforce/producer/sessions/' + SID + '/cases/' + OUTPUT + '/create?target=x',
    '/api/workforce/producer/sessions/%73ynthetic-session-1/cases/' + OUTPUT + '/create',
    '/api/workforce/producer/sessions/' + SID + '/cases/' + OUTPUT + '/create/extra',
  ];
  for (const path of paths) {
    const { calls, handle } = fixture();
    const segments = path.replace('/api/workforce/producer/', '').split('?')[0].split('/');
    assert.equal((await handle(req('create', { path }), segments)).status, 404);
    assert.equal(calls.length, 0);
  }
});

test('cross-origin, non-same-origin, forged host, and browser credentials are denied', async () => {
  const invalid = [
    { Origin: 'https://attacker.invalid' },
    { Host: 'attacker.invalid' },
    { 'Sec-Fetch-Site': 'same-site' },
    { 'Sec-Fetch-Site': 'cross-site' },
    { Authorization: 'Bearer client-token' },
    { Forwarded: 'host=attacker.invalid' },
    { 'X-Original-Host': 'attacker.invalid' },
    { 'X-Original-URI': '/api/workforce/admin' },
    { 'X-Forwarded-Host': 'attacker.invalid' },
    { 'X-Forwarded-Proto': 'http' },
    { 'X-Forwarded-Prefix': '/api/workforce/admin' },
    { 'X-Forwarded-For': '127.0.0.1' },
    { 'X-Forwarded-Uri': '/api/workforce/admin' },
    { 'X-Rewrite-URL': '/api/workforce/admin' },
    { 'X-HTTP-Method-Override': 'GET' },
    { 'X-MatchDesk-Workforce': 'force' },
    { 'Content-Type': 'text/plain' },
  ];
  for (const headers of invalid) {
    const { calls, handle } = fixture();
    assert.equal((await handle(req('create', { headers }), SEGMENTS)).status, 403);
    assert.equal(calls.length, 0);
  }
});

test('session cookies and CSRF must match a server-held secret', async () => {
  const badHeaders = [
    { Cookie: '' },
    { Cookie: '__Host-md-workforce=' + COOKIE + '; injected=1' },
    { Cookie: 'other=' + COOKIE },
    { 'X-CSRF-Token': '' },
    { 'X-CSRF-Token': 'b'.repeat(43) },
  ];
  for (const headers of badHeaders) {
    const { calls, handle } = fixture();
    const response = await handle(req('create', { headers }), SEGMENTS);
    assert.ok([401, 403].includes(response.status));
    assert.equal(calls.length, 0);
  }
});

test('tenant, issuer, producer role, session membership and expiry are rechecked', async () => {
  const invalid = [
    { issuer: 'https://foreign.invalid/v2.0' },
    { tenantId: 'ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee' },
    { subject: '' },
    { roles: ['auditor'] },
    { permittedSessions: ['other'] },
    { delegatedToken: 'browser-provided-not-an-api-token' },
    { expiresAtMs: 1_003_000 },
    { expiresAtMs: 9_000_000 },
  ];
  for (const session of invalid) {
    const { calls, handle } = fixture({ session });
    assert.equal((await handle(req(), SEGMENTS)).status, 403, JSON.stringify(session));
    assert.equal(calls.length, 0);
  }
});

test('a fixed host origin, private backend and workforce issuer are mandatory', async () => {
  const invalid = [
    { publicOrigin: 'http://public.invalid' },
    { backendOrigin: 'http://attacker.invalid' },
    { backendOrigin: BACKEND + '/open-proxy' },
    { trustedIssuer: 'https://ciamlogin.com/customer' },
  ];
  for (const host of invalid) {
    const { calls, handle } = fixture({ host });
    assert.equal((await handle(req(), SEGMENTS)).status, 503);
    assert.equal(calls.length, 0);
  }
});

test('operator BFF rejects non-tenant-specific or malformed host issuers before session lookup', async () => {
  const invalid = [
    { trustedIssuer: 'https://login.microsoftonline.com/common/v2.0' },
    { trustedIssuer: 'https://login.microsoftonline.com/organizations/v2.0' },
    { trustedIssuer: 'https://login.microsoftonline.com/ffffffff-ffff-ffff-ffff-ffffffffffff/v2.0' },
    { trustedIssuer: ISSUER + '/extra' },
    { trustedIssuer: ISSUER + '?client_id=attacker' },
    { trustedIssuer: ISSUER + '#fragment' },
    { trustedIssuer: 'https://login.microsoftonline.com/' + TENANT },
    { trustedTenantId: '------------------------------------',
      trustedIssuer: 'https://login.microsoftonline.com/------------------------------------/v2.0' },
  ];
  for (const settings of invalid) {
    let resolved = 0;
    const { calls, handle } = fixture({
      host: {
        ...settings,
        sessions: { async resolve() { resolved++; throw new Error('private DB must not be called'); } },
      },
    });
    const response = await handle(req(), SEGMENTS);
    assert.equal(response.status, 503, JSON.stringify(settings));
    assert.equal((await response.json()).detail, 'Workforce BFF unavailable');
    assert.equal(resolved, 0);
    assert.equal(calls.length, 0);
  }
});

test('streaming payloads are bounded without trusting Content-Length', async () => {
  const { calls, handle } = fixture();
  const result = await handle(req('create', {
    body: '{"huge":"' + 'x'.repeat(40_000) + '"}',
  }), SEGMENTS);
  assert.equal(result.status, 413);
  assert.equal(calls.length, 0);
});

test('backend denials, redirects, invalid receipts and failures redact all secrets', async () => {
  const scenarios = [
    () => Response.json({ detail: 'private grant internal' }, { status: 403 }),
    () => new Response(null, { status: 302, headers: { Location: 'https://attacker.invalid' } }),
    () => new Response('<script>bad</script>', { status: 201, headers: { 'Content-Type': 'text/html' } }),
    () => Response.json({
      session_id: SID, output_id: OUTPUT, action: 'create',
      generation: 1, item_version: 1, review_status: 'approved',
      publication_enabled: true,
    }, { status: 201 }),
    () => Response.json({
      session_id: SID, output_id: 'other-output', action: 'create',
      generation: 1, item_version: 1, review_status: 'pending_verification',
      publication_enabled: false,
    }, { status: 201 }),
    () => Response.json({ huge: 'x'.repeat(9000) }, { status: 201 }),
    () => { throw new Error('private backend credential'); },
  ];
  for (const backendResponse of scenarios) {
    const { handle, host } = fixture();
    host.fetchBackend = async () => backendResponse();
    const response = await handle(req(), SEGMENTS);
    assert.ok([403, 503].includes(response.status));
    const body = await response.text();
    assert.doesNotMatch(body, /private grant internal|private backend credential|attacker.invalid/);
    assert.equal(response.headers.get('location'), null);
  }
});


test('reverification receipts must prove transaction-backed mode and an unapproved state', async () => {
  const variants = [
    { mode: 'host_authorized_reverification', approval_enabled: false,
      review_status: 'ready_for_decision' },
    { mode: 'grant_backed_development_only', approval_enabled: true,
      review_status: 'ready_for_decision' },
    { mode: 'grant_backed_development_only', approval_enabled: false,
      review_status: 'approved' },
    { mode: 'grant_backed_development_only', approval_enabled: false,
      review_status: 'ready_for_decision', action: 'approve' },
  ];
  for (const variant of variants) {
    const { handle, host } = fixture();
    host.fetchBackend = async () => Response.json({
      session_id: SID,
      output_id: OUTPUT,
      generation: 2,
      item_version: 1,
      publication_enabled: false,
      ...variant,
    });
    const response = await handle(req('reverify'),
      ['sessions', SID, 'cases', OUTPUT, 'reverify']);
    assert.equal(response.status, 503, JSON.stringify(variant));
    assert.equal((await response.json()).detail, 'Workforce upstream unavailable');
  }
});

test('all producer commands reject legacy boolean grants and impossible review states', async () => {
  const actionStates = {
    create: 'pending_verification',
    edit: 'pending_verification',
    approve: 'approved',
    reject: 'rejected',
  };
  for (const [action, validState] of Object.entries(actionStates)) {
    for (const variant of [
      { mode: 'opt_in_development_only', review_status: validState },
      { mode: undefined, review_status: validState },
      { mode: 'grant_backed_development_only', review_status: 'ready_for_decision' },
    ]) {
      const { calls, handle, host } = fixture();
      host.fetchBackend = async (url, init) => {
        calls.push({ url, init });
        return Response.json({
          session_id: SID, output_id: OUTPUT,
          generation: action === 'create' ? 1 : 2, item_version: 1,
          action, publication_enabled: false, ...variant,
        }, { status: action === 'create' ? 201 : 200 });
      };
      const response = await handle(req(action),
        ['sessions', SID, 'cases', OUTPUT, action]);
      assert.equal(response.status, 503, action + ': ' + JSON.stringify(variant));
      assert.equal((await response.json()).detail, 'Workforce upstream unavailable');
      assert.equal(calls.length, 1);
    }
  }
});
