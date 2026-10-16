/** Same-origin browser requests keep the internal API address on the server. */
const config = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    // This URL is operator configuration, never a browser-supplied proxy target.
    const origin = process.env.MATCHDESK_API_ORIGIN ?? "http://127.0.0.1:8000";
    // Preserve local Next.js API handlers such as the opt-in judge bridge.
    // The generic Python proxy is a fallback only after filesystem routes.
    return { fallback: [{ source: "/api/:path*", destination: `${origin}/api/:path*` }] };
  },
};
export default config;
