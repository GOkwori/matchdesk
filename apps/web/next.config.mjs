/** Same-origin browser requests keep the internal API address on the server. */

/**
 * Content-Security-Policy for production builds. There is no 'unsafe-eval'. script-src
 * keeps 'unsafe-inline' because Next.js streams its route payload in inline scripts on
 * statically prerendered pages; a nonce would force every page to render dynamically
 * and break the offline cache. Development keeps Next's defaults, because React's dev
 * tooling needs eval.
 */
const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "worker-src 'self'",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const config = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    const production = process.env.NODE_ENV === "production";
    return [
      ...(production ? [{ source: "/:path*", headers: securityHeaders }] : []),
      // The offline worker must be re-checked on every visit so a new build takes over promptly.
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }] },
    ];
  },
  async rewrites() {
    // This URL is operator configuration, never a browser-supplied proxy target.
    const origin = process.env.MATCHDESK_API_ORIGIN ?? "http://127.0.0.1:8000";
    // Filesystem-backed Next API handlers (including the judge bridge) take precedence.
    // Unknown API paths still fall back to the existing fixed-target Python service.
    return { fallback: [{ source: "/api/:path*", destination: `${origin}/api/:path*` }] };
  },
};
export default config;
