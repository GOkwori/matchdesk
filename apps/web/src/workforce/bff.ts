/** Default-deny, fixed-target BFF contract for future workforce producer commands.
 *
 * This module does NOT authenticate Entra users, issue cookies, refresh tokens,
 * issue execution grants or activate a producer route. A separately reviewed
 * host must inject a real server-side session resolver after live qualification.
 * Access tokens and CSRF secrets are never accepted from browser JSON/cookies.
 */
import { timingSafeEqual } from "node:crypto";

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const OPAQUE = /^[A-Za-z0-9_-]{43}$/;
const JWT = /^[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}$/;
const COOKIE_NAME = "__Host-md-workforce";
const MAX_REQUEST_BYTES = 32_768;
const MAX_RESPONSE_BYTES = 8_192;
const ACTIONS = new Set(["create", "edit", "reverify", "approve", "reject"]);
const REVIEW_STATES = new Set(["pending_verification", "ready_for_decision", "approved", "rejected"]);

/** The host must independently validate Entra, realm, role, session and expiry. */
export type VerifiedWorkforceSession = {
  readonly issuer: string;
  readonly tenantId: string;
  readonly subject: string;
  readonly roles: readonly string[];
  readonly permittedSessions: readonly string[];
  readonly delegatedToken: string;
  readonly csrfSecret: string;
  readonly expiresAtMs: number;
};

/** Only the host's trusted, server-side session store may implement this interface. */
export type WorkforceSessionResolver = {
  resolve(opaqueSessionId: string): Promise<VerifiedWorkforceSession | null>;
};

export type WorkforceBffHost = {
  readonly publicOrigin: string;
  readonly backendOrigin: string;
  readonly trustedIssuer: string;
  readonly trustedTenantId: string;
  readonly sessions: WorkforceSessionResolver;
  readonly fetchBackend?: (url: string, init: RequestInit) => Promise<Response>;
  readonly nowMs?: () => number;
};

/** All responses are private, framing-denied, and contain no upstream credentials. */
function headers(): HeadersInit {
  return {
    "Cache-Control": "no-store, max-age=0",
    Pragma: "no-cache",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    Vary: "Origin, Cookie, Sec-Fetch-Site",
  };
}

function deny(status: number, detail: string): Response {
  return Response.json({ detail }, { status, headers: headers() });
}

/** Require one canonical public origin and an operator-owned backend destination. */
function originsValid(host: WorkforceBffHost): boolean {
  try {
    const publicUrl = new URL(host.publicOrigin);
    const backendUrl = new URL(host.backendOrigin);
    const publicLoopback = publicUrl.origin === "http://127.0.0.1:3000";
    const backendLoopback = backendUrl.origin === "http://127.0.0.1:8000";
    return (
      (publicUrl.protocol === "https:" || publicLoopback) &&
      (backendUrl.protocol === "https:" || backendLoopback) &&
      host.publicOrigin === publicUrl.origin &&
      host.backendOrigin === backendUrl.origin &&
      !publicUrl.username && !publicUrl.password &&
      !backendUrl.username && !backendUrl.password &&
      host.trustedIssuer.startsWith("https://login.microsoftonline.com/") &&
      /^[0-9a-f-]{36}$/i.test(host.trustedTenantId) &&
      typeof host.sessions.resolve === "function"
    );
  } catch {
    return false;
  }
}

/** No arbitrary paths, encoded separators, browsing or publication operations. */
function operation(segments: readonly string[], pathname: string): {
  sessionId: string; outputId: string; action: string; backendPath: string;
} | null {
  if (segments.length !== 5 || segments[0] !== "sessions" || segments[2] !== "cases" ||
      !IDENTIFIER.test(segments[1]) || !IDENTIFIER.test(segments[3]) ||
      !ACTIONS.has(segments[4])) return null;
  const backendPath = "/api/workforce/producer/" + segments.join("/");
  // Next may decode route parameters. A raw percent-encoded or doubled path is
  // never allowed to select a different backend resource than the visible URL.
  if (pathname !== backendPath) return null;
  return { sessionId: segments[1], outputId: segments[3], action: segments[4], backendPath };
}

/** Distinguish a bounded-request rejection from malformed JSON and transport faults. */
class BodyLimitError extends Error {}

/** Read streams with a hard byte limit; Content-Length is not a memory limit. */
async function boundedBody(body: ReadableStream<Uint8Array> | null, limit: number): Promise<string> {
  if (!body) throw new Error("Missing response/request body");
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let count = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      count += value.byteLength;
      if (count > limit) {
        await reader.cancel();
        throw new BodyLimitError("Body exceeds bound");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const all = new Uint8Array(count);
  let offset = 0;
  for (const chunk of chunks) {
    all.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(all);
}

/** Match a constant-length CSRF secret against server-side session state. */
function sameToken(actual: string | null, expected: string): boolean {
  if (typeof actual !== "string" || !OPAQUE.test(actual) || !OPAQUE.test(expected)) return false;
  return timingSafeEqual(Buffer.from(actual), Buffer.from(expected));
}

/** Reject attempts to smuggle browser identity or override the host API token. */
function trustedRequest(request: Request, expectedOrigin: string): boolean {
  const url = new URL(request.url);
  const h = request.headers;
  return (
    request.method === "POST" &&
    url.origin === expectedOrigin &&
    url.search === "" &&
    h.get("host") === new URL(expectedOrigin).host &&
    h.get("origin") === expectedOrigin &&
    h.get("sec-fetch-site") === "same-origin" &&
    h.get("content-type") === "application/json" &&
    !h.has("authorization") && !h.has("forwarded") &&
    !h.has("x-original-host") && !h.has("x-original-url") &&
    !h.has("x-matchdesk-workforce") &&
    (!h.has("referer") || h.get("referer")!.startsWith(expectedOrigin + "/"))
  );
}

/** Check the *host-owned* realm, tenant, issuer and session before any upstream I/O. */
function authorizedSession(
  session: VerifiedWorkforceSession | null,
  host: WorkforceBffHost,
  targetSession: string,
): session is VerifiedWorkforceSession {
  const now = (host.nowMs ?? Date.now)();
  return (
    session !== null &&
    typeof session === "object" &&
    session.tenantId === host.trustedTenantId &&
    session.issuer === host.trustedIssuer &&
    typeof session.subject === "string" && session.subject.length > 0 &&
    Array.isArray(session.roles) && session.roles.includes("producer") &&
    Array.isArray(session.permittedSessions) &&
    session.permittedSessions.includes(targetSession) &&
    typeof session.delegatedToken === "string" &&
    session.delegatedToken.length <= 8192 && JWT.test(session.delegatedToken) &&
    typeof session.csrfSecret === "string" && OPAQUE.test(session.csrfSecret) &&
    Number.isSafeInteger(session.expiresAtMs) &&
    session.expiresAtMs > now + 5_000 &&
    session.expiresAtMs <= now + 15 * 60_000
  );
}

/** Relay only the non-sensitive state receipt, never arbitrary backend JSON. */
function receipt(payload: unknown, sessionId: string, outputId: string, action: string): object | null {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) return null;
  const value = payload as Record<string, unknown>;
  if (
    value.session_id !== sessionId || value.output_id !== outputId ||
    value.publication_enabled !== false ||
    !Number.isSafeInteger(value.generation) || Number(value.generation) < 1 ||
    !Number.isSafeInteger(value.item_version) || Number(value.item_version) < 1 ||
    typeof value.review_status !== "string" || !REVIEW_STATES.has(value.review_status) ||
    (action !== "reverify" && value.action !== action)
  ) return null;
  return {
    session_id: sessionId,
    output_id: outputId,
    generation: value.generation,
    item_version: value.item_version,
    review_status: value.review_status,
    action,
    publication_enabled: false,
  };
}

/** Reusable server-only handler; no public route activates a host by default. */
export function createWorkforceBff(host: WorkforceBffHost | null) {
  return async (request: Request, segments: readonly string[]): Promise<Response> => {
    // A configured environment variable, mock token or request header must
    // never activate workforce access without a verified host adapter.
    if (host === null) return deny(404, "Workforce BFF is disabled");
    if (!originsValid(host)) return deny(503, "Workforce BFF unavailable");
    const url = new URL(request.url);
    // Query strings cannot select, retarget or decorate privileged operations.
    if (url.search !== "") return deny(404, "Unknown workforce operation");
    const target = operation(segments, url.pathname);
    if (!target) return deny(404, "Unknown workforce operation");
    if (!trustedRequest(request, host.publicOrigin)) {
      return deny(403, "Workforce request denied");
    }
    const cookie = request.headers.get("cookie") ?? "";
    const match = new RegExp("^" + COOKIE_NAME + "=([A-Za-z0-9_-]{43})$").exec(cookie);
    if (!match) return deny(401, "Workforce session required");

    let session: VerifiedWorkforceSession | null;
    try {
      session = await host.sessions.resolve(match[1]);
    } catch {
      return deny(503, "Workforce session unavailable");
    }
    if (!authorizedSession(session, host, target.sessionId)) {
      return deny(403, "Workforce operation denied");
    }
    if (!sameToken(request.headers.get("x-csrf-token"), session.csrfSecret)) {
      return deny(403, "Workforce operation denied");
    }

    const length = request.headers.get("content-length");
    if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_REQUEST_BYTES)) {
      return deny(413, "Workforce request too large");
    }
    let raw: string;
    try {
      raw = await boundedBody(request.body, MAX_REQUEST_BYTES);
      const body: unknown = JSON.parse(raw);
      if (body === null || typeof body !== "object" || Array.isArray(body)) {
        return deny(400, "Invalid workforce request");
      }
    } catch (error) {
      if (error instanceof BodyLimitError) return deny(413, "Workforce request too large");
      return deny(400, "Invalid workforce request");
    }

    try {
      const response = await (host.fetchBackend ?? fetch)(
        host.backendOrigin + target.backendPath,
        {
          method: "POST",
          headers: {
            Authorization: "Bearer " + session.delegatedToken,
            "Content-Type": "application/json",
          },
          body: raw,
          cache: "no-store",
          redirect: "manual",
          credentials: "omit",
          signal: AbortSignal.timeout(5000),
        },
      );
      if ([400, 401, 403, 409, 413].includes(response.status)) {
        return deny(response.status, "Workforce operation denied or changed");
      }
      if (response.status !== (target.action === "create" ? 201 : 200) ||
          !response.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
        return deny(503, "Workforce upstream unavailable");
      }
      const text = await boundedBody(response.body, MAX_RESPONSE_BYTES);
      const state = receipt(JSON.parse(text), target.sessionId, target.outputId, target.action);
      if (state === null) return deny(503, "Workforce upstream unavailable");
      return Response.json(state, {
        status: response.status,
        headers: { ...headers(), "Content-Type": "application/json" },
      });
    } catch {
      return deny(503, "Workforce upstream unavailable");
    }
  };
}
