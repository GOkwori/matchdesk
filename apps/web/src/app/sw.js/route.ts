/** /sw.js: the offline worker, generated at build time with the studio route list and a build stamp. */
import { siteRoutes } from "../../studio/site";

export const dynamic = "force-static";

const BUILD = Date.now().toString(36);

/**
 * Strategy: pages are network-first (fresh when online, cached copy offline); hashed
 * /_next/static assets are cache-first; everything is same-origin and /api is never cached.
 * On install the worker caches every studio page plus the scripts, styles and fonts those
 * pages reference, so the whole demo works with no connection after one online visit.
 */
const source = `/* MatchDesk offline worker · build ${BUILD} */
const BUILD = ${JSON.stringify(BUILD)};
const PAGES = "md-pages-" + BUILD;
const ASSETS = "md-assets";
const ROUTES = ${JSON.stringify(siteRoutes.map((r) => r.path).filter((p) => !["/workforce/", "/operator/", "/producer/secure/"].some((prefix) => p.startsWith(prefix))))};
const PRIVATE_PREFIXES = ["/api/", "/workforce/", "/operator/", "/producer/secure/"];
const EXTRA = ["/manifest.webmanifest", "/icon.png", "/apple-icon.png", "/favicon.ico"];

const assetUrls = (text) => {
  const found = new Set();
  for (const m of text.matchAll(/(?:src|href)="(\\/_next\\/static\\/[^"]+)"/g)) found.add(m[1]);
  for (const m of text.matchAll(/url\\((\\/_next\\/static\\/[^)"']+)\\)/g)) found.add(m[1]);
  for (const m of text.matchAll(/"(\\/_next\\/static\\/chunks\\/[^"\\\\]+\\.js)"/g)) found.add(m[1]);
  return [...found];
};

async function precache() {
  const pages = await caches.open(PAGES);
  const assets = await caches.open(ASSETS);
  const queue = [];
  await Promise.all(ROUTES.map(async (path) => {
    const res = await fetch(path, { cache: "reload" });
    if (!res.ok) return;
    queue.push(...assetUrls(await res.clone().text()));
    await pages.put(path, res);
  }));
  await Promise.all(EXTRA.map(async (path) => {
    try { const res = await fetch(path); if (res.ok) await assets.put(path, res); } catch {}
  }));
  const seen = new Set();
  while (queue.length) {
    const url = queue.shift();
    if (seen.has(url)) continue;
    seen.add(url);
    if (await assets.match(url)) continue;
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      if (url.endsWith(".css")) queue.push(...assetUrls(await res.clone().text()));
      await assets.put(url, res);
    } catch {}
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key.startsWith("md-pages-") && key !== PAGES) await caches.delete(key);
    await self.clients.claim();
  })());
});

async function page(request) {
  const url = new URL(request.url);
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    const res = await fetch(request, { signal: controller.signal });
    clearTimeout(timer);
    if (res.ok && ROUTES.includes(url.pathname)) (await caches.open(PAGES)).put(url.pathname, res.clone());
    return res;
  } catch {
    const cache = await caches.open(PAGES);
    return (await cache.match(url.pathname)) || (await cache.match("/")) || Response.error();
  }
}

async function asset(request) {
  const cache = await caches.open(ASSETS);
  const hit = await cache.match(request, { ignoreSearch: true });
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) cache.put(request, res.clone());
  return res;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  // Never precache, offline-fallback, or intercept any authenticated operator URL.
  if (url.origin !== self.location.origin || PRIVATE_PREFIXES.some((p) => url.pathname.startsWith(p))) return;
  if (request.mode === "navigate") { event.respondWith(page(request)); return; }
  if (url.pathname.startsWith("/_next/static/") || EXTRA.includes(url.pathname)) { event.respondWith(asset(request)); return; }
});
`;

export function GET() {
  return new Response(source, {
    headers: { "Content-Type": "text/javascript; charset=utf-8", "Cache-Control": "no-cache, no-store, must-revalidate" },
  });
}
