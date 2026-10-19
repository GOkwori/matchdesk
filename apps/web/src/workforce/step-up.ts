/** Host-only, default-disabled Entra step-up qualification for workforce identity.
 *
 * A signed acrs claim ALONE is not proof of MFA or an enforced Conditional
 * Access policy: Entra may emit acrs when no policy protects the context.
 * Require independent, fresh tenant-policy assurance and a new signed token
 * pair with auth_time after the one-time challenge. This module issues NO
 * workforce session, CSRF cookie, producer grant, publication or HTTP route.
 *
 * The future host must implement a durably atomic create/consume challenge
 * store and an independently reviewed per-actor CA policy evaluator. Browser
 * fields and LLM/tool messages are never trusted sources of either.
 */
import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import {
  verifyWorkforceStepUpClaims, type VerifiedWorkforceCodeExchange,
  type WorkforceSigningKeys,
} from "./entra";
import type { WorkforceOidcPolicy } from "./oidc";

const DIGEST = /^[a-f0-9]{64}$/;
const NONCE = /^[A-Za-z0-9_-]{43}$/;
const GUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const CONTEXT = /^c[1-9][0-9]?$/;
const CHALLENGE_AGE_SEC = 300;
const ASSURANCE_AGE_SEC = 120;
const EVIDENCE_TTL_SEC = 120;

function denied(): never {
  // No provider data, bearer values, database errors or protected identity.
  throw new Error("Workforce step-up qualification denied");
}

/** Host-reviewed tenant context: no common/organizations or dynamic context. */
export type WorkforceStepUpPolicy = Readonly<{
  oidc: WorkforceOidcPolicy;
  contextId: string;
}>;

/** The database commits one immutable challenge before the redirect begins. */
export type WorkforceStepUpAttempt = Readonly<{
  stateDigest: string;
  nonce: string;
  tenantId: string;
  clientId: string;
  objectId: string;
  subject: string;
  contextId: string;
  issuedAtSeconds: number;
  expiresAtSeconds: number;
}>;

/** Must atomically issue-if-absent and consume with a durable replay tombstone. */
export type WorkforceStepUpStore = Readonly<{
  create(attempt: WorkforceStepUpAttempt): Promise<boolean>;
  consume(stateDigest: string): Promise<WorkforceStepUpAttempt | null>;
}>;

/** Trusted provider attests ACTIVE Conditional Access coverage for this actor.
 *
 * Must be produced by the host from independently checked tenant policy, not
 * from a browser, token's acrs claim, role claim or unverified API response.
 */
export type WorkforceEnforcedPolicyEvidence = Readonly<{
  tenantId: string;
  clientId: string;
  objectId: string;
  contextId: string;
  policyId: string;
  enforced: true;
  actorIncluded: true;
  control: "multifactor" | "phishing_resistant";
  verifiedAtSeconds: number;
}>;

export type WorkforcePolicyAssuranceProvider = Readonly<{
  assess(input: Readonly<{
    tenantId: string;
    clientId: string;
    objectId: string;
    contextId: string;
  }>): Promise<WorkforceEnforcedPolicyEvidence | null>;
}>;

/** Host-only redirect instructions: no bearer, session, producer authority. */
export type WorkforceStepUpStart = Readonly<{
  challengeHandle: string;
  nonce: string;
  claimsRequest: string;
  expiresAtSeconds: number;
}>;

/** Short-lived identity qualification, NEVER an access or execution grant. */
export type QualifiedWorkforceStepUp = Readonly<{
  issuer: string;
  tenantId: string;
  clientId: string;
  subject: string;
  objectId: string;
  contextId: string;
  qualifiedAtSeconds: number;
  expiresAtSeconds: number;
}>;

function validPolicy(policy: WorkforceStepUpPolicy): boolean {
  const oidc = policy?.oidc;
  if (!oidc || typeof oidc !== "object" ||
      !GUID.test(oidc.tenantId) || !GUID.test(oidc.clientId) ||
      !GUID.test(oidc.apiResourceAppId) ||
      oidc.delegatedApiScope !== "api://" +
        oidc.apiResourceAppId + "/MatchDesk.Producer.Access" ||
      !CONTEXT.test(policy.contextId)) return false;
  try {
    const url = new URL(oidc.publicOrigin);
    return url.protocol === "https:" && url.origin === oidc.publicOrigin &&
      url.pathname === "/" && url.search === "" && url.hash === "" &&
      !url.username && !url.password;
  } catch {
    return false;
  }
}

function validExchange(
  exchange: VerifiedWorkforceCodeExchange, policy: WorkforceStepUpPolicy,
  nowSeconds: number,
): boolean {
  const oidc = policy.oidc;
  return Boolean(exchange && typeof exchange === "object" &&
    exchange.tenantId === oidc.tenantId &&
    exchange.clientId === oidc.clientId &&
    exchange.issuer === "https://login.microsoftonline.com/" +
      oidc.tenantId.toLowerCase() + "/v2.0" &&
    GUID.test(exchange.objectId) &&
    typeof exchange.subject === "string" &&
    exchange.subject.length > 0 && exchange.subject.length <= 256 &&
    Number.isSafeInteger(exchange.expiresAtSeconds) &&
    exchange.expiresAtSeconds >= nowSeconds + 10);
}

function validAttempt(attempt: WorkforceStepUpAttempt): boolean {
  return Boolean(attempt && typeof attempt === "object" &&
    DIGEST.test(attempt.stateDigest) &&
    NONCE.test(attempt.nonce) &&
    GUID.test(attempt.tenantId) && GUID.test(attempt.clientId) &&
    GUID.test(attempt.objectId) &&
    typeof attempt.subject === "string" &&
    attempt.subject.length > 0 && attempt.subject.length <= 256 &&
    CONTEXT.test(attempt.contextId) &&
    Number.isSafeInteger(attempt.issuedAtSeconds) &&
    attempt.issuedAtSeconds > 0 &&
    Number.isSafeInteger(attempt.expiresAtSeconds) &&
    attempt.expiresAtSeconds === attempt.issuedAtSeconds + CHALLENGE_AGE_SEC);
}

function validTime(nowSeconds: number): boolean {
  return Number.isSafeInteger(nowSeconds) && nowSeconds > 0 &&
    nowSeconds <= Number.MAX_SAFE_INTEGER - CHALLENGE_AGE_SEC;
}

function digest(value: string): string {
  return createHash("sha256").update(value, "ascii").digest("hex");
}

/** Minimum context claims request, to be included in a FRESH PKCE authorise.
 *
 * The future host must send a separate one-time OIDC challenge with a new
 * state, PKCE and nonce, not add credentials to an existing browser session.
 */
export function workforceStepUpClaimsRequest(policy: WorkforceStepUpPolicy): string {
  if (!validPolicy(policy)) return denied();
  return JSON.stringify({
    access_token: { acrs: { essential: true, value: policy.contextId } },
  });
}

/** Reserve a one-use challenge in the trusted server store; never issue login. */
export async function beginWorkforceStepUp(
  exchange: VerifiedWorkforceCodeExchange,
  policy: WorkforceStepUpPolicy,
  store: WorkforceStepUpStore,
  nowSeconds: number,
): Promise<WorkforceStepUpStart> {
  if (!validPolicy(policy) || !validTime(nowSeconds) ||
      !validExchange(exchange, policy, nowSeconds) ||
      !store || typeof store.create !== "function") return denied();
  const handle = randomBytes(32).toString("base64url");
  const nonce = randomBytes(32).toString("base64url");
  const attempt: WorkforceStepUpAttempt = {
    stateDigest: digest(handle), nonce,
    tenantId: policy.oidc.tenantId,
    clientId: policy.oidc.clientId,
    objectId: exchange.objectId,
    subject: exchange.subject,
    contextId: policy.contextId,
    issuedAtSeconds: nowSeconds,
    expiresAtSeconds: nowSeconds + CHALLENGE_AGE_SEC,
  };
  try {
    if (await store.create(attempt) !== true) return denied();
    return {
      challengeHandle: handle, nonce,
      claimsRequest: workforceStepUpClaimsRequest(policy),
      expiresAtSeconds: attempt.expiresAtSeconds,
    };
  } catch {
    return denied();
  }
}

/** First consume durable state, then verify context, actor and policy coverage.
 *
 * Caller-owned input cannot construct the attempt. On every failure, the
 * challenge remains consumed. The returned object is NOT a session/cookie,
 * cannot be passed to the BFF, and grants NO producer execution authority.
 */
export async function qualifyWorkforceStepUp(
  challengeHandle: string,
  idToken: string,
  accessToken: string,
  initialExchange: VerifiedWorkforceCodeExchange,
  policy: WorkforceStepUpPolicy,
  store: WorkforceStepUpStore,
  keys: WorkforceSigningKeys,
  assuranceProvider: WorkforcePolicyAssuranceProvider,
  nowSeconds: number,
): Promise<QualifiedWorkforceStepUp> {
  if (!validPolicy(policy) || !validTime(nowSeconds) ||
      typeof challengeHandle !== "string" || !NONCE.test(challengeHandle) ||
      !validExchange(initialExchange, policy, nowSeconds) ||
      !store || typeof store.consume !== "function" ||
      !keys || typeof keys.resolve !== "function" ||
      !assuranceProvider || typeof assuranceProvider.assess !== "function") return denied();

  try {
    const candidateDigest = digest(challengeHandle);
    // A real state store MUST use atomic one-use conditional consumption.
    const attempt = await store.consume(candidateDigest);
    if (!attempt || !validAttempt(attempt) ||
        !timingSafeEqual(
          Buffer.from(candidateDigest, "hex"),
          Buffer.from(attempt.stateDigest, "hex"),
        ) ||
        attempt.tenantId !== policy.oidc.tenantId ||
        attempt.clientId !== policy.oidc.clientId ||
        attempt.objectId !== initialExchange.objectId ||
        attempt.subject !== initialExchange.subject ||
        attempt.contextId !== policy.contextId ||
        attempt.issuedAtSeconds > nowSeconds + 30 ||
        attempt.issuedAtSeconds > nowSeconds ||
        attempt.expiresAtSeconds <= nowSeconds) return denied();

    // Do not infer enforcement from a signed acrs claim. The policy provider
    // must independently prove an ENABLED control actually covers this actor.
    const proof = await assuranceProvider.assess({
      tenantId: attempt.tenantId, clientId: attempt.clientId,
      objectId: attempt.objectId, contextId: attempt.contextId,
    });
    if (!proof || proof.tenantId !== attempt.tenantId ||
        proof.clientId !== attempt.clientId ||
        proof.objectId !== attempt.objectId ||
        proof.contextId !== attempt.contextId ||
        !GUID.test(proof.policyId) ||
        proof.enforced !== true || proof.actorIncluded !== true ||
        !["multifactor", "phishing_resistant"].includes(proof.control) ||
        !Number.isSafeInteger(proof.verifiedAtSeconds) ||
        proof.verifiedAtSeconds > nowSeconds + 30 ||
        nowSeconds - proof.verifiedAtSeconds > ASSURANCE_AGE_SEC) return denied();

    // Verify TWO signed tokens and require a fresh ID auth_time and exact API
    // acrs. A self-asserted browser MFA flag or a copied token cannot pass.
    const verified = await verifyWorkforceStepUpClaims(
      idToken, accessToken, policy.oidc, attempt.nonce, keys, nowSeconds,
      attempt.issuedAtSeconds, attempt.contextId,
      attempt.objectId, attempt.subject,
    );
    const expiresAtSeconds = Math.min(
      verified.expiresAtSeconds,
      attempt.expiresAtSeconds,
      proof.verifiedAtSeconds + ASSURANCE_AGE_SEC,
      nowSeconds + EVIDENCE_TTL_SEC,
    );
    if (expiresAtSeconds <= nowSeconds + 5) return denied();
    return Object.freeze({
      issuer: initialExchange.issuer,
      tenantId: attempt.tenantId,
      clientId: attempt.clientId,
      subject: attempt.subject,
      objectId: attempt.objectId,
      contextId: attempt.contextId,
      qualifiedAtSeconds: nowSeconds,
      expiresAtSeconds,
    });
  } catch {
    return denied();
  }
}
