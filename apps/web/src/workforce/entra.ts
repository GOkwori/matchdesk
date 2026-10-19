/** Offline Entra confidential-client exchange and cryptographic JWT qualification.
 *
 * A host may use this ONLY after a durably consumed OIDC state and must supply
 * a certificate-signed client assertion plus issuer-pinned signing keys. The
 * browser never chooses an endpoint, audience, signing key, client credential,
 * nonce or resource. This module does not fetch open discovery URLs, create an
 * application session, confer producer entitlements or assert recent MFA.
 *
 * The future production host must independently qualify certificate rotation,
 * Entra metadata/JWKS refresh, server-only session encryption and revocation.
 * No exported Next.js route invokes this module.
 */
import { createPublicKey, verify as verifySignature } from "node:crypto";
import type { PendingWorkforceExchange, WorkforceOidcPolicy } from "./oidc";

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const BASE64URL = /^[A-Za-z0-9_-]+$/;
const KEY_ID = /^[A-Za-z0-9_-]{1,128}$/;
const PKCE = /^[A-Za-z0-9_-]{43}$/;
const JWT = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
const MAX_TOKEN_BODY = 32768;
const MAX_AGE_SECONDS = 3600;
const CLOCK_SKEW_SECONDS = 30;
const ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer";

function denied(): never {
  // Never include provider response bodies, access tokens or host credentials.
  throw new Error("Workforce Entra exchange or token verification denied");
}

/** Only an independently reviewed and issuer-bound signing-key resolver. */
export type WorkforceSigningKey = Readonly<{
  issuer: string;
  kid: string;
  kty: "RSA";
  alg: "RS256";
  use: "sig";
  n: string;
  e: string;
}>;

export type WorkforceSigningKeys = Readonly<{
  resolve(issuer: string, kid: string): Promise<WorkforceSigningKey | null>;
}>;

/** Only the trusted host owns and signs its confidential-client credential. */
export type WorkforceClientAssertionSigner = Readonly<{
  sign(clientId: string, tokenEndpoint: string): Promise<string>;
}>;

export type WorkforceEntraExchangeHost = Readonly<{
  keys: WorkforceSigningKeys;
  assertion: WorkforceClientAssertionSigner;
  fetchToken?: (url: string, init: RequestInit) => Promise<Response>;
  nowSeconds?: () => number;
}>;

/** No ID token, refresh token or user-controlled claims cross this boundary. */
export type VerifiedWorkforceCodeExchange = Readonly<{
  tenantId: string;
  subject: string;
  objectId: string;
  issuer: string;
  clientId: string;
  delegatedAccessToken: string;
  expiresAtSeconds: number;
}>;

type Claims = Readonly<Record<string, unknown>>;

function parseSection(value: string, maxEncodedBytes: number): Claims {
  if (!BASE64URL.test(value) || value.length > maxEncodedBytes) return denied();
  const data = Buffer.from(value, "base64url");
  if (data.length === 0 || data.length > maxEncodedBytes * 3 / 4 + 1 ||
      data.toString("base64url") !== value) return denied();
  try {
    const parsed: unknown = JSON.parse(data.toString("utf8"));
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return denied();
    return parsed as Claims;
  } catch {
    return denied();
  }
}

/** Verify RS256 itself, then apply independent exact issuer/audience policy. */
async function verifyJwt(
  token: string, issuer: string, audience: string, keys: WorkforceSigningKeys,
  now: number,
): Promise<Claims> {
  if (typeof token !== "string" || token.length > 16384 || !JWT.test(token)) return denied();
  const [partHeader, partBody, partSignature] = token.split(".");
  const header = parseSection(partHeader, 2048);
  if (header.alg !== "RS256" || typeof header.kid !== "string" ||
      !KEY_ID.test(header.kid) || header.crit !== undefined ||
      header.jku !== undefined || header.jwk !== undefined ||
      header.x5u !== undefined || header.b64 !== undefined ||
      (header.typ !== undefined && header.typ !== "JWT" && header.typ !== "at+jwt")) {
    return denied();
  }
  let key: WorkforceSigningKey | null;
  try {
    key = await keys.resolve(issuer, header.kid);
  } catch {
    return denied();
  }
  if (key === null || typeof key !== "object" ||
      key.issuer !== issuer || key.kid !== header.kid ||
      key.kty !== "RSA" || key.alg !== "RS256" || key.use !== "sig" ||
      !BASE64URL.test(key.n) || !BASE64URL.test(key.e) ||
      key.n.length < 340 || key.n.length > 1000 || key.e !== "AQAB") return denied();

  const signature = Buffer.from(partSignature, "base64url");
  if (signature.toString("base64url") !== partSignature) return denied();
  try {
    const publicKey = createPublicKey({
      key: { kty: "RSA", n: key.n, e: key.e },
      format: "jwk",
    });
    if (publicKey.asymmetricKeyType !== "rsa" ||
        (publicKey.asymmetricKeyDetails?.modulusLength ?? 0) < 2048 ||
        !verifySignature("RSA-SHA256",
          Buffer.from(partHeader + "." + partBody, "ascii"), publicKey, signature)) {
      return denied();
    }
  } catch {
    return denied();
  }
  const claims = parseSection(partBody, 8192);
  const validNumber = (value: unknown): value is number =>
    typeof value === "number" && Number.isSafeInteger(value) && value > 0;
  if (claims.iss !== issuer || claims.aud !== audience ||
      claims.ver !== "2.0" ||
      !validNumber(claims.iat) || !validNumber(claims.nbf) ||
      !validNumber(claims.exp) ||
      claims.iat > now + CLOCK_SKEW_SECONDS ||
      claims.nbf > now + CLOCK_SKEW_SECONDS ||
      claims.exp <= now - CLOCK_SKEW_SECONDS ||
      claims.exp <= claims.iat ||
      claims.exp - claims.iat > MAX_AGE_SECONDS ||
      now - claims.iat > MAX_AGE_SECONDS + CLOCK_SKEW_SECONDS) {
    return denied();
  }
  return claims;
}

/** Inspect both tokens; signed API claims alone cannot confer app entitlements. */
export async function verifyWorkforceTokenPair(
  idToken: string, accessToken: string, policy: WorkforceOidcPolicy,
  nonce: string, keys: WorkforceSigningKeys, nowSeconds: number,
): Promise<Readonly<{ subject: string; objectId: string; expiresAtSeconds: number }>> {
  if (!policy || !GUID.test(policy.tenantId) || !GUID.test(policy.clientId) ||
      !GUID.test(policy.apiResourceAppId) ||
      policy.delegatedApiScope !==
        "api://" + policy.apiResourceAppId + "/MatchDesk.Producer.Access" ||
      !PKCE.test(nonce) || !Number.isSafeInteger(nowSeconds) || nowSeconds <= 0 ||
      !keys || typeof keys.resolve !== "function") return denied();

  const issuer = "https://login.microsoftonline.com/" + policy.tenantId.toLowerCase() + "/v2.0";
  const id = await verifyJwt(idToken, issuer, policy.clientId, keys, nowSeconds);
  const api = await verifyJwt(accessToken, issuer, policy.apiResourceAppId, keys, nowSeconds);
  if (id.tid !== policy.tenantId || api.tid !== policy.tenantId ||
      id.nonce !== nonce ||
      typeof id.sub !== "string" || id.sub.length < 1 || id.sub.length > 256 ||
      typeof id.oid !== "string" || !GUID.test(id.oid) ||
      api.oid !== id.oid ||
      api.azp !== policy.clientId ||
      typeof api.scp !== "string" ||
      !api.scp.split(" ").includes("MatchDesk.Producer.Access") ||
      api.idtyp === "app" ||
      typeof api.sub !== "string" || api.sub.length === 0) return denied();
  // An access token is proof of API delegation, not recent step-up or
  // server-side producer role. Those checks belong to independent host gates.
  return {
    subject: id.sub,
    objectId: id.oid,
    expiresAtSeconds: Math.min(id.exp as number, api.exp as number),
  };
}

async function boundedJson(response: Response): Promise<Claims> {
  const length = response.headers.get("content-length");
  if (length !== null && (!/^[0-9]+$/.test(length) ||
      Number(length) > MAX_TOKEN_BODY)) return denied();
  if (!response.body) return denied();
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_TOKEN_BODY) return denied();
      chunks.push(value);
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
  const all = Buffer.concat(chunks.map((v) => Buffer.from(v)), total);
  try {
    const data: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(all));
    if (data === null || typeof data !== "object" || Array.isArray(data)) return denied();
    return data as Claims;
  } catch {
    return denied();
  }
}

/** Perform only a confidential-client certificate-assertion code redemption.
 *
 * NEVER return this result to a browser. Its delegated token must be protected
 * by a separately reviewed durable session vault; no user is yet authorized.
 */
export async function redeemAndVerifyWorkforceCode(
  pending: PendingWorkforceExchange,
  policy: WorkforceOidcPolicy,
  host: WorkforceEntraExchangeHost,
): Promise<VerifiedWorkforceCodeExchange> {
  try {
    if (!policy || !pending || !host || !host.assertion || !host.keys ||
        typeof host.assertion.sign !== "function" ||
        typeof host.keys.resolve !== "function" ||
        !GUID.test(policy.tenantId) || !GUID.test(policy.clientId) ||
        !GUID.test(policy.apiResourceAppId) ||
        policy.delegatedApiScope !==
          "api://" + policy.apiResourceAppId + "/MatchDesk.Producer.Access") return denied();
    const issuer = "https://login.microsoftonline.com/" + policy.tenantId.toLowerCase() + "/v2.0";
    const endpoint = "https://login.microsoftonline.com/" +
      policy.tenantId.toLowerCase() + "/oauth2/v2.0/token";
    const redirect = policy.publicOrigin + "/api/workforce/oidc/callback";
    const publicUrl = new URL(policy.publicOrigin);
    if (publicUrl.protocol !== "https:" || publicUrl.origin !== policy.publicOrigin ||
        !["/"].includes(publicUrl.pathname) ||
        pending.issuer !== issuer || pending.tokenEndpoint !== endpoint ||
        pending.clientId !== policy.clientId || pending.redirectUri !== redirect ||
        !PKCE.test(pending.nonce) || !PKCE.test(pending.codeVerifier) ||
        typeof pending.authorizationCode !== "string" ||
        !/^[\x21-\x7E]{1,2048}$/.test(pending.authorizationCode)) return denied();

    const now = (host.nowSeconds ?? (() => Math.floor(Date.now() / 1000)))();
    if (!Number.isSafeInteger(now) || now <= 0) return denied();

    // Signing happens outside browser code and the returned client assertion
    // must be minted by the trusted host against this exact token endpoint.
    const assertion = await host.assertion.sign(policy.clientId, endpoint);
    if (typeof assertion !== "string" || assertion.length > 8192 ||
        !JWT.test(assertion)) return denied();

    const form = new URLSearchParams({
      grant_type: "authorization_code",
      client_id: policy.clientId,
      redirect_uri: redirect,
      code: pending.authorizationCode,
      code_verifier: pending.codeVerifier,
      scope: "openid " + policy.delegatedApiScope,
      client_assertion_type: ASSERTION_TYPE,
      client_assertion: assertion,
    });
    const response = await (host.fetchToken ?? fetch)(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json",
      },
      body: form.toString(),
      redirect: "manual",
      credentials: "omit",
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (response.status !== 200 ||
        !response.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
      return denied();
    }
    const body = await boundedJson(response);
    if (body.token_type !== "Bearer" ||
        typeof body.id_token !== "string" ||
        typeof body.access_token !== "string" ||
        !Number.isSafeInteger(body.expires_in) ||
        (body.expires_in as number) < 60 ||
        (body.expires_in as number) > MAX_AGE_SECONDS ||
        body.refresh_token !== undefined) return denied();

    const checked = await verifyWorkforceTokenPair(
      body.id_token, body.access_token, policy, pending.nonce, host.keys, now,
    );
    return {
      tenantId: policy.tenantId,
      subject: checked.subject,
      objectId: checked.objectId,
      issuer,
      clientId: policy.clientId,
      delegatedAccessToken: body.access_token,
      expiresAtSeconds: Math.min(now + (body.expires_in as number),
        checked.expiresAtSeconds),
    };
  } catch {
    return denied();
  }
}
