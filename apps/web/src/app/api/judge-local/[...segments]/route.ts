/** A fixed-target, localhost-only bridge to the opt-in Python judge host.
 *
 * This is not a general API proxy. No browser-controlled destination, cookies,
 * producer credentials, query strings or privileged commands can pass through.
 */
import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const WEB_ORIGIN = "http://127.0.0.1:3000";
const BACKEND_ORIGIN = "http://127.0.0.1:8000";
const MAX_RESPONSE_BYTES = 48_000;
const SID = /^[A-Za-z0-9_-]{32}$/;
const TOKEN = /^Bearer [A-Za-z0-9_-]{43}$/;

type RouteContext = { params: Promise<{ segments: string[] }> };

/** Return a controlled error without cache, framing, token or server details. */
function denied(status: number, reason: string): Response {
  return Response.json({ detail: reason }, { status, headers: securityHeaders() });
}

/** Suppress local bearer replay and unauthorized framing on every response. */
function securityHeaders(): HeadersInit {
  return {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "Vary": "Origin, Authorization, Sec-Fetch-Site",
  };
}

/** Permit only the four documented routes and methods, never a dynamic target. */
function backendPath(method: string, parts: string[]): string | null {
  if (parts.length === 1 && parts[0] === "sessions" && method === "POST") {
    return "/api/judge/sessions";
  }
  if (parts.length === 2 && parts[0] === "sessions" && SID.test(parts[1])) {
    return method === "DELETE" ? "/api/judge/sessions/" + parts[1] : null;
  }
  if (parts.length === 3 && parts[0] === "sessions" && SID.test(parts[1])) {
    if (parts[2] === "replay" && method === "GET") {
      return "/api/judge/sessions/" + parts[1] + "/replay";
    }
    if (parts[2] === "reset" && method === "POST") {
      return "/api/judge/sessions/" + parts[1] + "/reset";
    }
  }
  return null;
}

// Next.js generates these headers even for direct localhost requests. Accept
// only its exact loopback values; reject client-supplied conflicting forwarding
// data, extra forwarding fields, and any reverse-proxy configuration.
const NEXT_LOCAL_FORWARDING = new Map<string, string>([
  ["x-forwarded-for", "127.0.0.1"],
  ["x-forwarded-host", "127.0.0.1:3000"],
  ["x-forwarded-port", "3000"],
  ["x-forwarded-proto", "http"],
]);

/** Require the exact localhost forwarding tuple synthesized by Next.js. */
function exactLocalForwarding(headers: Headers): boolean {
  for (const [name, value] of headers) {
    if (name.startsWith("x-forwarded-") && NEXT_LOCAL_FORWARDING.get(name) !== value) {
      return false;
    }
  }
  return [...NEXT_LOCAL_FORWARDING].every(([name, value]) => headers.get(name) === value);
}

/** Guard the actual browser-facing trust boundary, not only the Python host. */
function trusted(request: NextRequest): boolean {
  const h = request.headers;
  const origin = h.get("origin");
  const fetchSite = h.get("sec-fetch-site");
  const isWrite = request.method !== "GET";
  return (
    h.get("host") === "127.0.0.1:3000" &&
    request.nextUrl.hostname === "127.0.0.1" &&
    request.nextUrl.port === "3000" &&
    request.nextUrl.search === "" &&
    !h.has("cookie") &&
    // An ordinary same-origin browser fetch may include its page referrer.
    (h.get("referer") === null || h.get("referer")!.startsWith(WEB_ORIGIN + "/")) &&
    !h.has("forwarded") &&
    exactLocalForwarding(h) &&
    !h.has("x-original-host") &&
    !h.has("x-original-url") &&
    (fetchSite === null || fetchSite === "same-origin") &&
    (isWrite ? origin === WEB_ORIGIN : origin === null || origin === WEB_ORIGIN)
  );
}

/** Forward only fixed, syntactically bounded capabilities to loopback. */
async function handle(request: NextRequest, context: RouteContext): Promise<Response> {
  // An explicit operator-only environment opt-in is required even on localhost.
  if (process.env.MATCHDESK_LOCAL_JUDGE_ENABLED !== "1") {
    return denied(404, "Local judge adapter is disabled");
  }
  if (!trusted(request)) return denied(403, "Local judge access denied");
  const { segments } = await context.params;
  const path = backendPath(request.method, segments);
  if (path === null) return denied(404, "Unknown local judge operation");

  const incoming = request.headers.get("authorization");
  const needsBearer = !(segments.length === 1 && request.method === "POST");
  if (needsBearer ? !incoming || !TOKEN.test(incoming) : incoming !== null) {
    return denied(403, "Local judge session unavailable");
  }

  let body: string | undefined;
  if (request.method === "POST") {
    if (request.headers.get("content-type") !== "application/json") {
      return denied(400, "Expected JSON");
    }
    body = await request.text();
    if (body !== "{}") return denied(400, "Expected an empty JSON object");
  }
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const reply = await fetch(BACKEND_ORIGIN + path, {
        method: request.method,
        headers: {
          "Origin": BACKEND_ORIGIN,
          "X-MatchDesk-Judge": "synthetic-local-v1",
          ...(needsBearer ? { Authorization: incoming! } : {}),
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        ...(body !== undefined ? { body } : {}),
        signal: controller.signal,
        cache: "no-store",
        redirect: "manual",
      });
      // Never follow a backend redirect or relay an oversized/private response.
      const sizeHeader = reply.headers.get("content-length");
      if (
        reply.status >= 300 && reply.status < 400 ||
        sizeHeader !== null && Number(sizeHeader) > MAX_RESPONSE_BYTES ||
        reply.headers.get("content-type")?.includes("application/json") === false
      ) return denied(503, "Synthetic judge response unavailable");
      if (reply.status === 204) {
        return new Response(null, { status: 204, headers: securityHeaders() });
      }
      // Read a bounded stream; Content-Length alone is never a resource limit.
      if (!reply.body) return denied(503, "Synthetic judge response unavailable");
      const reader = reply.body.getReader();
      const chunks: Uint8Array[] = [];
      let received = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        received += value.byteLength;
        if (received > MAX_RESPONSE_BYTES) {
          await reader.cancel();
          return denied(503, "Synthetic judge response unavailable");
        }
        chunks.push(value);
      }
      const content = new TextDecoder("utf-8", { fatal: true }).decode(
        Uint8Array.from(chunks.flatMap((chunk) => Array.from(chunk))),
      );
      return new Response(content, {
        status: reply.status,
        headers: { ...securityHeaders(), "Content-Type": "application/json" },
      });
    } finally {
      clearTimeout(timeout);
    }
  } catch {
    return denied(503, "Local judge service unavailable");
  }
}

export async function GET(request: NextRequest, context: RouteContext): Promise<Response> {
  return handle(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  return handle(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<Response> {
  return handle(request, context);
}
