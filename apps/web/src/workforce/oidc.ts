/** Offline workforce OIDC code+PKCE initiation and callback verification.
 *
 * This is a host-injected trust contract, NOT a live sign-in provider. It does
 * not fetch Entra metadata, redeem codes, validate bearer/ID tokens, issue
 * cookies for signed-in users or grant producer access. Those remain separate,
 * fail-closed prerequisites for mounting any workforce operator routes.
 *
 * The host must implement the attempt store with durable, atomic create/consume.
 * The callback consumes state BEFORE testing browser binding/issuer to prevent
 * reuse of partially successful or attacker-substituted authorization responses.
 */
import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const B64URL_256 = /^[A-Za-z0-9_-]{43}$/;
const DIGEST = /^[0-9a-f]{64}$/;
const COOKIE = "__Host-md-workforce-oidc";
const CALLBACK_PATH = "/api/workforce/oidc/callback";
const MAX_AGE_MS = 300_000;

/** Reviewed, tenant-specific workforce authority. Never use common/organizations. */
export type WorkforceOidcPolicy = Readonly<{
  publicOrigin: string;
  tenantId: string;
  clientId: string;
  delegatedApiScope: string;
}>;

/** A pending, uniquely stored transaction with secrets unavailable to the UI. */
export type WorkforceOidcAttempt = Readonly<{
  stateDigest: string;
  bindingDigest: string;
  issuer: string;
  clientId: string;
  redirectUri: string;
  issuedAtMs: number;
  expiresAtMs: number;
  nonce: string;
  codeVerifier: string;
}>;

/** The store MUST be durable and consume exactly one attempt atomically. */
export type WorkforceOidcAttemptStore = Readonly<{
  create(attempt: WorkforceOidcAttempt): Promise<boolean>;
  consume(stateDigest: string): Promise<WorkforceOidcAttempt | null>;
}>;

/** Browser-only start output. This is not a session cookie or authentication. */
export type WorkforceOidcStart = Readonly<{
  authorizationUrl: string;
  bindingCookie: string;
}>;

/** Host-only input to a future pinned token-exchange and verifier adapter. */
export type PendingWorkforceExchange = Readonly<{
  issuer: string;
  clientId: string;
  tokenEndpoint: string;
  redirectUri: string;
  nonce: string;
  codeVerifier: string;
  authorizationCode: string;
}>;

function deny(): never {
  throw new Error("Workforce OIDC sign-in denied");
}

function digest(value: string): string {
  return createHash("sha256").update(value, "ascii").digest("hex");
}

function randomSecret(): string {
  return randomBytes(32).toString("base64url");
}

function matchDigest(a: string, b: string): boolean {
  if (!DIGEST.test(a) || !DIGEST.test(b)) return false;
  return timingSafeEqual(Buffer.from(a, "hex"), Buffer.from(b, "hex"));
}

/** Validate every endpoint from reviewed policy, not discovery in browser input. */
export function workforceOidcEndpoints(policy: WorkforceOidcPolicy) {
  if (!policy || typeof policy !== "object" ||
      !GUID.test(policy.tenantId) || !GUID.test(policy.clientId) ||
      policy.delegatedApiScope !== "api://" + policy.tenantId + "/MatchDesk.Producer.Access") {
    throw new Error("Workforce OIDC policy is not approved");
  }
  let publicUrl: URL;
  try {
    publicUrl = new URL(policy.publicOrigin);
  } catch {
    throw new Error("Workforce OIDC origin is invalid");
  }
  if (publicUrl.protocol !== "https:" ||
      publicUrl.origin !== policy.publicOrigin ||
      publicUrl.username || publicUrl.password || publicUrl.hash ||
      publicUrl.search || publicUrl.pathname !== "/") {
    throw new Error("Workforce OIDC requires one exact HTTPS origin");
  }
  const issuer = "https://login.microsoftonline.com/" + policy.tenantId.toLowerCase() + "/v2.0";
  const root = "https://login.microsoftonline.com/" + policy.tenantId.toLowerCase() + "/oauth2/v2.0";
  return {
    issuer,
    authorizationEndpoint: root + "/authorize",
    tokenEndpoint: root + "/token",
    redirectUri: policy.publicOrigin + CALLBACK_PATH,
  };
}

/** Reject origin/header substitution before any state is written or consumed. */
function exactBrowserRequest(
  request: Request, publicOrigin: string, phase: "start" | "callback",
): void {
  const url = new URL(request.url);
  const headers = request.headers;
  if (
    url.origin !== publicOrigin ||
    headers.get("host") !== new URL(publicOrigin).host ||
    headers.has("forwarded") ||
    [...headers.keys()].some((name) => name.startsWith("x-forwarded-") ||
      name.startsWith("x-original-")) ||
    headers.has("authorization") ||
    (phase === "start" && (
      request.method !== "POST" ||
      url.pathname !== "/api/workforce/oidc/start" ||
      url.search !== "" ||
      headers.get("origin") !== publicOrigin ||
      headers.get("sec-fetch-site") !== "same-origin"
    )) ||
    (phase === "callback" && (
      request.method !== "GET" ||
      url.pathname !== CALLBACK_PATH ||
      headers.has("origin") ||
      headers.get("sec-fetch-mode") !== "navigate" ||
      headers.get("sec-fetch-dest") !== "document" ||
      !["cross-site", "same-origin", "same-site", "none"].includes(
        headers.get("sec-fetch-site") ?? ""
      )
    ))
  ) {
    deny();
  }
}

/** Only the new host-prefixed one-use browser binding may be read from Cookie. */
function browserBinding(request: Request): string {
  const raw = request.headers.get("cookie");
  if (raw === null || raw.length > 4096) return deny();
  const values = raw.split(";").map((p) => p.trim()).filter((p) => p.startsWith(COOKIE + "="));
  if (values.length !== 1) return deny();
  const value = values[0].slice(COOKIE.length + 1);
  if (!B64URL_256.test(value)) return deny();
  return value;
}

/** Reserve a one-use state with PKCE S256 and an unrelated HttpOnly cookie. */
export async function beginWorkforceOidc(
  policy: WorkforceOidcPolicy,
  store: WorkforceOidcAttemptStore,
  request: Request,
  nowMs: number = Date.now(),
): Promise<WorkforceOidcStart> {
  const endpoints = workforceOidcEndpoints(policy);
  exactBrowserRequest(request, policy.publicOrigin, "start");
  if (!Number.isSafeInteger(nowMs) || nowMs <= 0 ||
      !store || typeof store.create !== "function") deny();

  const state = randomSecret();
  const binding = randomSecret();
  const nonce = randomSecret();
  const codeVerifier = randomSecret();
  const attempt: WorkforceOidcAttempt = {
    stateDigest: digest(state),
    bindingDigest: digest(binding),
    issuer: endpoints.issuer,
    clientId: policy.clientId,
    redirectUri: endpoints.redirectUri,
    issuedAtMs: nowMs,
    expiresAtMs: nowMs + MAX_AGE_MS,
    nonce,
    codeVerifier,
  };
  try {
    if (await store.create(attempt) !== true) deny();
  } catch {
    deny();
  }

  const redirect = new URL(endpoints.authorizationEndpoint);
  redirect.searchParams.set("client_id", policy.clientId);
  redirect.searchParams.set("response_type", "code");
  redirect.searchParams.set("response_mode", "query");
  redirect.searchParams.set("redirect_uri", endpoints.redirectUri);
  redirect.searchParams.set("scope", "openid " + policy.delegatedApiScope);
  redirect.searchParams.set("state", state);
  redirect.searchParams.set("nonce", nonce);
  redirect.searchParams.set("code_challenge", createHash("sha256").update(codeVerifier).digest("base64url"));
  redirect.searchParams.set("code_challenge_method", "S256");
  return {
    authorizationUrl: redirect.toString(),
    bindingCookie: COOKIE + "=" + binding +
      "; Max-Age=300; Path=/; Secure; HttpOnly; SameSite=Lax",
  };
}

/** Clear the one-use cookie for both successful and rejected callbacks. */
export function clearWorkforceOidcBindingCookie(): string {
  return COOKIE + "=; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; " +
    "Path=/; Secure; HttpOnly; SameSite=Lax";
}

/** Consume browser-bound state and require RFC 9207 issuer before code exchange.
 *
 * The returned exchange must NEVER be serialized to browser JSON or logged.
 * It gives no authority to write, sign in, mint an app session or assert MFA.
 */
export async function consumeWorkforceOidcCallback(
  policy: WorkforceOidcPolicy,
  store: WorkforceOidcAttemptStore,
  request: Request,
  nowMs: number = Date.now(),
): Promise<PendingWorkforceExchange> {
  const endpoints = workforceOidcEndpoints(policy);
  exactBrowserRequest(request, policy.publicOrigin, "callback");
  if (!Number.isSafeInteger(nowMs) || nowMs <= 0 ||
      !store || typeof store.consume !== "function") deny();
  const url = new URL(request.url);
  if (url.hash || url.search.length > 8192) deny();
  const pairs = [...url.searchParams.entries()];
  const keys = pairs.map(([name]) => name);
  if (keys.length !== new Set(keys).size ||
      ![["state", "iss", "code"], ["state", "iss", "error"]].some(
        (allowed) => allowed.length === keys.length && allowed.every((key) => keys.includes(key))
      )) deny();
  const state = url.searchParams.get("state");
  const code = url.searchParams.get("code");
  const issuer = url.searchParams.get("iss");
  const error = url.searchParams.get("error");
  if (!state || !B64URL_256.test(state)) deny();

  // Atomically burn state even if the callback later turns out to be invalid.
  let attempt: WorkforceOidcAttempt | null;
  try {
    attempt = await store.consume(digest(state));
  } catch {
    deny();
  }
  if (!attempt || !matchDigest(attempt.stateDigest, digest(state))) deny();
  const binding = browserBinding(request);
  if (!matchDigest(attempt.bindingDigest, digest(binding)) ||
      attempt.issuer !== endpoints.issuer ||
      attempt.clientId !== policy.clientId ||
      attempt.redirectUri !== endpoints.redirectUri ||
      !B64URL_256.test(attempt.nonce) ||
      !B64URL_256.test(attempt.codeVerifier) ||
      !Number.isSafeInteger(attempt.issuedAtMs) ||
      !Number.isSafeInteger(attempt.expiresAtMs) ||
      attempt.issuedAtMs > nowMs ||
      attempt.expiresAtMs <= nowMs ||
      attempt.expiresAtMs - attempt.issuedAtMs !== MAX_AGE_MS ||
      issuer !== endpoints.issuer || error !== null ||
      code === null || !/^[\x21-\x7E]{1,2048}$/.test(code)
  ) deny();

  return {
    issuer: endpoints.issuer,
    clientId: policy.clientId,
    tokenEndpoint: endpoints.tokenEndpoint,
    redirectUri: endpoints.redirectUri,
    nonce: attempt.nonce,
    codeVerifier: attempt.codeVerifier,
    authorizationCode: code,
  };
}
