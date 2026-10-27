/** Signed, offline Conditional Access authentication-context qualification.
 *
 * All RSA keys and identities are synthetic. The pretend policy service is
 * intentionally independent of signed JWT claims. There is no live tenant,
 * active user session, cookie, grant, credential or production network call.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign, createHash } from "node:crypto";
import {
  workforceStepUpClaimsRequest,
  beginWorkforceStepUp,
  qualifyWorkforceStepUp,
} from "../src/workforce/step-up.ts";

const TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const CLIENT = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff";
const API = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa";
const OID = "dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb";
const POLICY_ID = "eeeeeeee-ffff-aaaa-bbbb-cccccccccccc";
const ORIGIN = "https://operator.example.test";
const ISSUER = "https://login.microsoftonline.com/" + TENANT + "/v2.0";
const NOW = 1_760_000_000;
const PAIR = generateKeyPairSync("rsa", { modulusLength: 2048 });
const FOREIGN = generateKeyPairSync("rsa", { modulusLength: 2048 });
const JWK = PAIR.publicKey.export({ format: "jwk" });
const POLICY = {
  contextId: "c1",
  oidc: {
    tenantId: TENANT, clientId: CLIENT, apiResourceAppId: API,
    publicOrigin: ORIGIN,
    delegatedApiScope: "api://" + API + "/MatchDesk.Producer.Access",
  },
};
const EXCHANGE = {
  tenantId: TENANT, clientId: CLIENT, issuer: ISSUER,
  objectId: OID, subject: "verified-initial-subject",
  delegatedAccessToken: "header.payload.signature",
  expiresAtSeconds: NOW + 600,
};

function token(claims, signer = PAIR.privateKey, extraHeader = {}) {
  const header = Buffer.from(JSON.stringify({
    alg: "RS256", typ: "JWT", kid: "kid-1", ...extraHeader,
  })).toString("base64url");
  const body = Buffer.from(JSON.stringify(claims)).toString("base64url");
  const sig = sign("RSA-SHA256", Buffer.from(header + "." + body), signer)
    .toString("base64url");
  return header + "." + body + "." + sig;
}
function idClaims(nonce, change = {}) {
  return {
    ver: "2.0", iss: ISSUER, aud: CLIENT, tid: TENANT, sub: EXCHANGE.subject,
    oid: OID, nonce, auth_time: NOW + 1, iat: NOW + 1,
    nbf: NOW, exp: NOW + 600, ...change,
  };
}
function apiClaims(change = {}) {
  return {
    ver: "2.0", iss: ISSUER, aud: API, tid: TENANT, sub: "api-pairwise-sub",
    oid: OID, azp: CLIENT, scp: "MatchDesk.Producer.Access",
    acrs: ["c1"], iat: NOW + 2, nbf: NOW, exp: NOW + 500, ...change,
  };
}
function keys(change = {}) {
  return {
    async resolve(issuer, kid) {
      if (issuer !== ISSUER || kid !== "kid-1") return null;
      return {
        issuer: ISSUER, kid: "kid-1", kty: "RSA", alg: "RS256", use: "sig",
        n: JWK.n, e: JWK.e, ...change,
      };
    },
  };
}
function assurance(change = {}) {
  const calls = [];
  return {
    calls,
    provider: {
      async assess(input) {
        calls.push(input);
        return {
          tenantId: TENANT, clientId: CLIENT, objectId: OID, contextId: "c1",
          policyId: POLICY_ID, enforced: true, actorIncluded: true,
          control: "multifactor", verifiedAtSeconds: NOW + 18,
          ...change,
        };
      },
    },
  };
}
class FakeStore {
  constructor() { this.attempts = new Map(); this.consumptions = 0; this.fail = false; }
  async create(attempt) {
    if (this.fail) throw new Error("private database certificate");
    if (this.attempts.has(attempt.stateDigest)) return false;
    this.attempts.set(attempt.stateDigest, attempt);
    return true;
  }
  async consume(digest) {
    if (this.fail) throw new Error("private database password");
    this.consumptions++;
    const attempt = this.attempts.get(digest) ?? null;
    this.attempts.delete(digest);
    return attempt;
  }
}
async function issued(store = new FakeStore()) {
  const start = await beginWorkforceStepUp(EXCHANGE, POLICY, store, NOW);
  return { store, start };
}
async function complete(
  { store, start }, changes = {},
) {
  const tokens = {
    id: token(idClaims(start.nonce, changes.idClaims)),
    api: token(apiClaims(changes.apiClaims)),
  };
  const evidence = assurance(changes.assurance);
  return qualifyWorkforceStepUp(
    changes.handle ?? start.challengeHandle,
    changes.idToken ?? tokens.id,
    changes.apiToken ?? tokens.api,
    changes.initialExchange ?? EXCHANGE,
    changes.policy ?? POLICY,
    store,
    changes.keys ?? keys(),
    changes.provider ?? evidence.provider,
    changes.now ?? NOW + 20,
  );
}

test("issued claims request is API-only and tightly pins the reviewed context", async () => {
  const { start, store } = await issued();
  assert.equal(start.challengeHandle.length, 43);
  assert.equal(start.nonce.length, 43);
  assert.notEqual(start.challengeHandle, start.nonce);
  assert.equal(start.expiresAtSeconds, NOW + 300);
  assert.deepEqual(JSON.parse(start.claimsRequest), {
    access_token: { acrs: { essential: true, value: "c1" } },
  });
  assert.equal(start.claimsRequest, workforceStepUpClaimsRequest(POLICY));
  const only = [...store.attempts.values()][0];
  assert.equal(only.stateDigest, createHash("sha256")
    .update(start.challengeHandle, "ascii").digest("hex"));
  assert.equal(only.objectId, OID);
  assert.equal(only.subject, EXCHANGE.subject);
  assert.equal(only.contextId, "c1");
  assert.equal("cookie" in start, false);
  assert.equal("session" in start, false);
  assert.equal("grant" in start, false);
});

test("two independently signed tokens plus enforced policy yield only ephemeral evidence", async () => {
  const x = await issued();
  const result = await complete(x);
  assert.deepEqual(result, {
    issuer: ISSUER, tenantId: TENANT, clientId: CLIENT,
    objectId: OID, subject: EXCHANGE.subject, contextId: "c1",
    qualifiedAtSeconds: NOW + 20, expiresAtSeconds: NOW + 138,
  });
  assert.equal(Object.isFrozen(result), true);
  for (const forbidden of [
    "accessToken", "csrfSecret", "delegatedAccessToken", "cookie",
    "roles", "permittedSessions", "authorization", "session",
    "publication_enabled", "grantId",
  ]) {
    assert.equal(forbidden in result, false);
  }
  assert.equal(x.store.attempts.size, 0);
});

test("the one-time signed proof is consumed; replay and a foreign handle fail", async () => {
  const x = await issued();
  await assert.rejects(
    complete(x, { handle: "a".repeat(43) }), /qualification denied/,
  );
  assert.equal(x.store.attempts.size, 1);
  assert.equal((await complete(x)).objectId, OID);
  await assert.rejects(complete(x), /qualification denied/);
  assert.equal(x.store.consumptions, 3);
});

test("missing or non-enforced Conditional Access for this exact actor fails even with acrs", async () => {
  const cases = [
    { enforced: false }, { actorIncluded: false },
    { tenantId: "other" }, { clientId: "wrong" }, { objectId: "wrong" },
    { contextId: "c2" }, { policyId: "not-a-guid" },
    { control: "password_only" }, { control: "" },
    { verifiedAtSeconds: NOW - 400 },
    { verifiedAtSeconds: NOW + 120 },
    { verifiedAtSeconds: "recent" },
  ];
  for (const candidate of cases) {
    const x = await issued();
    await assert.rejects(complete(x, { assurance: candidate }),
      /qualification denied/, JSON.stringify(candidate));
    assert.equal(x.store.attempts.size, 0);
  }
  for (const provider of [
    { async assess() { return null; } },
    { async assess() { throw new Error("secret Graph policy failure"); } },
  ]) {
    const x = await issued();
    await assert.rejects(complete(x, { provider }), (error) =>
      /qualification denied/.test(error.message) && !/secret Graph/.test(error.message));
    assert.equal(x.store.attempts.size, 0);
  }
});

test("signed acrs alone cannot prove freshness or MFA: required auth_time/iat fail closed", async () => {
  const changes = [
    { type: "idClaims", value: { auth_time: undefined } },
    { type: "idClaims", value: { auth_time: "1760000001" } },
    { type: "idClaims", value: { auth_time: NOW - 600 } },
    { type: "idClaims", value: { auth_time: NOW + 120 } },
    { type: "idClaims", value: { iat: NOW - 120 } },
    { type: "apiClaims", value: { iat: NOW - 120 } },
    { type: "apiClaims", value: { acrs: [] } },
    { type: "apiClaims", value: { acrs: ["c2"] } },
    { type: "apiClaims", value: { acrs: "c1" } },
    { type: "apiClaims", value: { acrs: ["c1", {}] } },
  ];
  for (const change of changes) {
    const x = await issued();
    await assert.rejects(complete(x, { [change.type]: change.value }),
      /qualification denied/, JSON.stringify(change));
    assert.equal(x.store.attempts.size, 0);
  }
});

test("signed IDs are pinned to issuer, tenant, nonce, human, resource and client", async () => {
  const bad = [
    { type: "idClaims", value: { oid: "ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb" } },
    { type: "idClaims", value: { sub: "another-user" } },
    { type: "idClaims", value: { nonce: "n".repeat(43) } },
    { type: "idClaims", value: { aud: API } },
    { type: "idClaims", value: { iss: "https://foreign.invalid/v2.0" } },
    { type: "apiClaims", value: { oid: "ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb" } },
    { type: "apiClaims", value: { azp: "another-client" } },
    { type: "apiClaims", value: { scp: "admin_only" } },
    { type: "apiClaims", value: { idtyp: "app" } },
  ];
  for (const c of bad) {
    const x = await issued();
    await assert.rejects(complete(x, { [c.type]: c.value }), /qualification denied/);
  }
});

test("foreign RSA signatures, attacker headers and untrusted key resolvers fail closed", async () => {
  for (const bad of [
    (x) => token(idClaims(x.start.nonce), FOREIGN.privateKey),
    (x) => token(idClaims(x.start.nonce), PAIR.privateKey, { jku: "https://bad.invalid" }),
    (x) => token(idClaims(x.start.nonce), PAIR.privateKey, { alg: "none" }),
  ]) {
    const x = await issued();
    await assert.rejects(complete(x, { idToken: bad(x) }), /qualification denied/);
  }
  const x = await issued();
  await assert.rejects(complete(x, {
    keys: { async resolve() { throw new Error("private JWKS secret"); } },
  }), (err) => /qualification denied/.test(err.message) && !/private/.test(err.message));
});

test("swapped actor or context cannot reuse a consumed challenge", async () => {
  for (const change of [
    { initialExchange: { ...EXCHANGE, objectId: "ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb" } },
    { initialExchange: { ...EXCHANGE, subject: "other" } },
    { policy: { ...POLICY, contextId: "c2" } },
  ]) {
    const x = await issued();
    await assert.rejects(complete(x, change), /qualification denied/);
    assert.equal(x.store.attempts.size, 0);
  }
});

test("invalid policy, expired initial token or database faults deny issuance safely", async () => {
  for (const oidc of [
    { tenantId: "common" }, { clientId: "invalid" },
    { apiResourceAppId: "invalid" },
    { publicOrigin: "http://operator.example.test" },
    { delegatedApiScope: "api://wrong/scope" },
  ]) {
    await assert.rejects(beginWorkforceStepUp(
      EXCHANGE, { ...POLICY, oidc: { ...POLICY.oidc, ...oidc } },
      new FakeStore(), NOW,
    ), /qualification denied/);
  }
  for (const contextId of ["", "c0", "cp1", "C1", "c100", "../../admin"]) {
    assert.throws(() => workforceStepUpClaimsRequest({
      ...POLICY, contextId,
    }), /qualification denied/);
  }
  await assert.rejects(beginWorkforceStepUp(
    { ...EXCHANGE, expiresAtSeconds: NOW + 5 },
    POLICY, new FakeStore(), NOW,
  ), /qualification denied/);
  const broken = new FakeStore();
  broken.fail = true;
  await assert.rejects(beginWorkforceStepUp(
    EXCHANGE, POLICY, broken, NOW,
  ), (err) => /qualification denied/.test(err.message) && !/private/.test(err.message));
});

test("expired and malformed state is consumed once but never permits qualification", async () => {
  const original = await issued();
  await assert.rejects(complete(original, { now: NOW + 301 }), /qualification denied/);
  assert.equal(original.store.attempts.size, 0);

  const mutated = await issued();
  const digest = [...mutated.store.attempts.keys()][0];
  const state = mutated.store.attempts.get(digest);
  mutated.store.attempts.set(digest, { ...state, nonce: "bad nonce" });
  await assert.rejects(complete(mutated), /qualification denied/);
  assert.equal(mutated.store.attempts.size, 0);
});

test("policy-only or browser-asserted step-up cannot bypass token requirements", async () => {
  const x = await issued();
  const evidence = assurance();
  await assert.rejects(qualifyWorkforceStepUp(
    x.start.challengeHandle, "browser-mfa=true", "browser-scope=producer",
    EXCHANGE, POLICY, x.store, keys(), evidence.provider, NOW + 20,
  ), /qualification denied/);
  assert.equal(x.store.attempts.size, 0);
});
