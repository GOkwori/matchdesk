/** Same-origin browser requests keep the internal API address on the server. */
const config = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    // This URL is operator configuration, never a browser-supplied proxy target.
    const origin = process.env.MATCHDESK_API_ORIGIN ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${origin}/api/:path*` }];
  },
};
export default config;
