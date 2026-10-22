/** Signed, credential-free Entra exchange and token-verification regressions.
 *
 * RSA keys are generated in memory for the test process. No live tenant,
 * confidential-client credential, production JWKS, login or session exists.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync, sign } from 'node:crypto';
import {
  verifyWorkforceTokenPair,
  redeemAndVerifyWorkforceCode,
} from '../src/workforce/entra.ts';

const TENANT = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const CLIENT = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff';
const API = 'cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa';
const OID = 'dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb';
const ORIGIN = 'https://operator.example.test';
const ISSUER = 'https://login.microsoftonline.com/' + TENANT + '/v2.0';
const TOKEN_ENDPOINT = 'https://login.microsoftonline.com/' + TENANT + '/oauth2/v2.0/token';
const CALLBACK = ORIGIN + '/api/workforce/oidc/callback';
const NOW = 1_760_000_000;
const NONCE = 'n'.repeat(43);
const POLICY = {
  publicOrigin: ORIGIN, tenantId: TENANT, clientId: CLIENT, apiResourceAppId: API,
  delegatedApiScope: 'api://' + API + '/MatchDesk.Producer.Access',
};
const PAIR = generateKeyPairSync('rsa', { modulusLength: 2048 });
const FOREIGN = generateKeyPairSync('rsa', { modulusLength: 2048 });
const JWK = PAIR.publicKey.export({ format: 'jwk' });

function token(claims, key = PAIR.privateKey, header = {}) {
  const h = Buffer.from(JSON.stringify({
    typ: 'JWT', alg: 'RS256', kid: 'kid-1', ...header,
  })).toString('base64url');
  const p = Buffer.from(JSON.stringify(claims)).toString('base64url');
  const signature = sign('RSA-SHA256', Buffer.from(h + '.' + p), key).toString('base64url');
  return [h, p, signature].join('.');
}

function idClaims(changes = {}) {
  return {
    ver: '2.0', iss: ISSUER, aud: CLIENT, tid: TENANT, sub: 'signed-human-subject',
    oid: OID, nonce: NONCE, iat: NOW - 20, nbf: NOW - 20, exp: NOW + 600,
    ...changes,
  };
}

function apiClaims(changes = {}) {
  return {
    ver: '2.0', iss: ISSUER, aud: API, tid: TENANT, sub: 'api-pairwise-subject',
    oid: OID, azp: CLIENT, scp: 'MatchDesk.Producer.Access',
    iat: NOW - 20, nbf: NOW - 20, exp: NOW + 500,
    ...changes,
  };
}

function keys(change = {}) {
  const key = {
    issuer: ISSUER, kid: 'kid-1', kty: 'RSA', alg: 'RS256', use: 'sig',
    n: JWK.n, e: JWK.e, ...change,
  };
  return { async resolve(issuer, kid) {
    return issuer === ISSUER && kid === 'kid-1' ? key : null;
  } };
}

function pending(change = {}) {
  return {
    issuer: ISSUER, clientId: CLIENT, tokenEndpoint: TOKEN_ENDPOINT,
    redirectUri: CALLBACK, nonce: NONCE, codeVerifier: 'p'.repeat(43),
    authorizationCode: 'synthetic-one-time-code',
    ...change,
  };
}

function host(change = {}) {
  const calls = [];
  const h = {
    keys: keys(),
    assertion: {
      async sign(clientId, target) {
        assert.equal(clientId, CLIENT);
        assert.equal(target, TOKEN_ENDPOINT);
        return ['signed', 'client', 'assertion'].join('.');
      },
    },
    nowSeconds: () => NOW,
    async fetchToken(url, init) {
      calls.push({ url, init });
      return Response.json({
        token_type: 'Bearer',
        id_token: token(idClaims()),
        access_token: token(apiClaims()),
        expires_in: 600,
      });
    },
    ...change,
  };
  return { h, calls };
}

test('real RS256 signatures bind the ID and delegated API tokens to one Entra person', async () => {
  const result = await verifyWorkforceTokenPair(
    token(idClaims({ roles: ['admin'] })),
    token(apiClaims({ roles: ['producer'], permitted_sessions: ['any'] })),
    POLICY, NONCE, keys(), NOW,
  );
  assert.deepEqual(result, {
    subject: 'signed-human-subject',
    objectId: OID,
    expiresAtSeconds: NOW + 500,
  });
  assert.equal('roles' in result, false);
});

test('ID token rejects issuer, audience, tenant, expiry, nonce or substituted identity', async () => {
  const bad = [
    { iss: 'https://login.microsoftonline.com/common/v2.0' },
    { aud: API }, { aud: [CLIENT] }, { tid: 'foreign-tenant' },
    { ver: '1.0' }, { nonce: 'wrong' }, { sub: '' },
    { oid: 'not-a-guid' }, { iat: NOW + 100 },
    { nbf: NOW + 100 }, { exp: NOW - 100 },
    { exp: NOW + 8000 }, { exp: 'not-a-timestamp' },
  ];
  for (const change of bad) {
    await assert.rejects(
      verifyWorkforceTokenPair(token(idClaims(change)), token(apiClaims()),
        POLICY, NONCE, keys(), NOW), /verification denied/,
      JSON.stringify(change),
    );
  }
});

test('delegated API token rejects wrong resource, client, scope, identity or app-only flow', async () => {
  const bad = [
    { aud: CLIENT }, { azp: 'foreign-client' },
    { scp: '' }, { scp: 'MatchDesk.Producer.AccessExtra' },
    { scp: ['MatchDesk.Producer.Access'] }, { idtyp: 'app' },
    { oid: 'eeeeeeee-ffff-aaaa-bbbb-cccccccccccc' },
    { sub: '' }, { tid: 'foreign-tenant' }, { ver: '1.0' },
  ];
  for (const change of bad) {
    await assert.rejects(
      verifyWorkforceTokenPair(token(idClaims()), token(apiClaims(change)),
        POLICY, NONCE, keys(), NOW), /verification denied/,
      JSON.stringify(change),
    );
  }
});

test('JWT header key substitution, unsigned tokens and bad RSA signatures fail closed', async () => {
  const invalid = [
    token(idClaims(), FOREIGN.privateKey),
    token(idClaims(), PAIR.privateKey, { alg: 'none' }),
    token(idClaims(), PAIR.privateKey, { kid: 'other' }),
    token(idClaims(), PAIR.privateKey, { jku: 'https://attacker.invalid/keyset' }),
    token(idClaims(), PAIR.privateKey, { jwk: JWK }),
    token(idClaims(), PAIR.privateKey, { crit: ['b64'], b64: false }),
    token(idClaims(), PAIR.privateKey, { typ: 'unsigned' }),
    token(idClaims()).slice(0, -8),
    'not-a-jwt',
  ];
  for (const value of invalid) {
    await assert.rejects(
      verifyWorkforceTokenPair(value, token(apiClaims()), POLICY, NONCE, keys(), NOW),
      /verification denied/,
    );
  }
});

test('issuer-bound RSA keys, 2048-bit minimum and immutable policy are mandatory', async () => {
  const badKeys = [
    keys({ issuer: 'https://attacker.invalid' }),
    // Malformed public key cannot be accepted; do not generate weak RSA keys.
    keys({ n: 'AQAB' }),
    keys({ e: 'AQAC' }),
    keys({ use: 'enc' }),
    keys({ alg: 'HS256' }),
    { async resolve() { throw new Error('private pinned-JWKS connection issue'); } },
  ];
  for (const resolver of badKeys) {
    await assert.rejects(
      verifyWorkforceTokenPair(token(idClaims()), token(apiClaims()),
        POLICY, NONCE, resolver, NOW), /verification denied/,
    );
  }
  const badPolicies = [
    { clientId: 'common' },
    { apiResourceAppId: 'invalid' },
    { tenantId: 'organizations' },
    { delegatedApiScope: 'api://different/MatchDesk.Producer.Access' },
  ];
  for (const change of badPolicies) {
    await assert.rejects(
      verifyWorkforceTokenPair(token(idClaims()), token(apiClaims()),
        { ...POLICY, ...change }, NONCE, keys(), NOW), /verification denied/,
    );
  }
});

test('confidential code redemption targets only the pinned tenant token endpoint', async () => {
  const { h, calls } = host();
  const result = await redeemAndVerifyWorkforceCode(pending(), POLICY, h);
  assert.deepEqual(result, {
    tenantId: TENANT, subject: 'signed-human-subject', objectId: OID,
    issuer: ISSUER, clientId: CLIENT,
    delegatedAccessToken: token(apiClaims()), // token() uses deterministic PKCS#1 v1.5 RSA.
    expiresAtSeconds: NOW + 500,
  });
  assert.equal(calls.length, 1);
  const call = calls[0];
  assert.equal(call.url, TOKEN_ENDPOINT);
  assert.equal(call.init.method, 'POST');
  assert.equal(call.init.redirect, 'manual');
  assert.equal(call.init.credentials, 'omit');
  assert.equal(call.init.cache, 'no-store');
  assert.equal(call.init.headers['Content-Type'], 'application/x-www-form-urlencoded');
  assert.ok(call.init.signal instanceof AbortSignal);
  const params = new URLSearchParams(call.init.body);
  assert.equal(params.get('grant_type'), 'authorization_code');
  assert.equal(params.get('client_id'), CLIENT);
  assert.equal(params.get('scope'), 'openid ' + POLICY.delegatedApiScope);
  assert.equal(params.get('redirect_uri'), CALLBACK);
  assert.equal(params.get('code'), 'synthetic-one-time-code');
  assert.equal(params.get('code_verifier'), 'p'.repeat(43));
  assert.equal(params.get('client_assertion_type'),
    'urn:ietf:params:oauth:client-assertion-type:jwt-bearer');
  assert.equal(params.get('client_assertion'), ['signed', 'client', 'assertion'].join('.'));
  assert.equal(params.has('client_secret'), false);
  assert.equal(params.has('refresh_token'), false);
});

test('substituted pending issuer, code, token endpoint and callback block all outbound calls', async () => {
  const invalid = [
    { issuer: 'https://login.microsoftonline.com/common/v2.0' },
    { tokenEndpoint: 'https://attacker.invalid/oauth/token' },
    { clientId: 'another-client' },
    { redirectUri: 'https://attacker.invalid/callback' },
    { nonce: 'wrong' }, { codeVerifier: 'short' },
    { authorizationCode: '' }, { authorizationCode: 'bad\ncode' },
  ];
  for (const change of invalid) {
    const { h, calls } = host();
    await assert.rejects(redeemAndVerifyWorkforceCode(pending(change), POLICY, h),
      /verification denied/);
    assert.equal(calls.length, 0, JSON.stringify(change));
  }
});

test('missing or faulty confidential-client signer prevents any token exchange', async () => {
  const cases = [
    { assertion: { sign: async () => '' } },
    { assertion: { sign: async () => { throw new Error('private certificate'); } } },
    { assertion: { sign: async () => 'raw-secret' } },
    { assertion: null },
  ];
  for (const change of cases) {
    const { h, calls } = host(change);
    await assert.rejects(redeemAndVerifyWorkforceCode(pending(), POLICY, h),
      (error) => /verification denied/.test(error.message) &&
        !/private certificate/.test(error.message));
    assert.equal(calls.length, 0);
  }
});

test('wrong provider status, redirects, content-type or oversized body always fail closed', async () => {
  const cases = [
    () => Response.json({ error: 'private_provider_error' }, { status: 400 }),
    () => new Response(null, { status: 302, headers: { location: 'https://attacker.invalid' } }),
    () => new Response('<html>bad</html>', {
      status: 200, headers: { 'content-type': 'text/html' },
    }),
    () => Response.json({ huge: 'x'.repeat(40_000) }),
    () => Response.json({ error: 'private' }, {
      headers: { 'content-length': '999999' },
    }),
    () => { throw new Error('private network secret'); },
  ];
  for (const scenario of cases) {
    const { h } = host({ fetchToken: async () => scenario() });
    await assert.rejects(redeemAndVerifyWorkforceCode(pending(), POLICY, h),
      (error) => /verification denied/.test(error.message) &&
        !/private|attacker/.test(error.message));
  }
});

test('API and ID validation occurs after token response and never silently authorises MFA', async () => {
  const variations = [
    { token_type: 'Basic' }, { expires_in: 8000 },
    { expires_in: '3600' }, { refresh_token: 'unexpected-refresh' },
    { id_token: token(idClaims({ nonce: 'wrong-nonce' })) },
    { access_token: token(apiClaims({ aud: CLIENT })) },
    { access_token: token(apiClaims(), FOREIGN.privateKey) },
    { access_token: '' },
  ];
  for (const change of variations) {
    const { h } = host({
      fetchToken: async () => Response.json({
        token_type: 'Bearer', id_token: token(idClaims()),
        access_token: token(apiClaims()), expires_in: 600, ...change,
      }),
    });
    await assert.rejects(redeemAndVerifyWorkforceCode(pending(), POLICY, h),
      /verification denied/, JSON.stringify(Object.keys(change)));
  }
});
