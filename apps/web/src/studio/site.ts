/** Single route registry for the studio: sitemap, robots, offline precache and route tests read it. */
import { claims } from "./data";
import { stories } from "./stories";

/**
 * Public origin used for canonical URLs, the sitemap and social cards. Operators set
 * MATCHDESK_SITE_URL at build time; the fallback keeps local builds self-consistent.
 */
export const SITE_URL = (process.env.MATCHDESK_SITE_URL ?? "http://localhost:3000").replace(/\/+$/, "");

export type SiteRoute = {
  readonly path: string;
  /** Indexable routes appear in the sitemap; everything else is noindex workspace UI. */
  readonly indexable: boolean;
};

/** Every studio page that exists, in navigation order. Deep-linked variants are listed explicitly. */
export const siteRoutes: readonly SiteRoute[] = [
  { path: "/", indexable: true },
  { path: "/about", indexable: true },
  { path: "/story", indexable: true },
  ...stories.map((s) => ({ path: `/story/${s.slug}`, indexable: true })),
  { path: "/match/nbr-riv", indexable: true },
  { path: "/match/nbr-riv/live", indexable: false },
  { path: "/match/nbr-riv/moments", indexable: false },
  { path: "/match/nbr-riv/tactical", indexable: false },
  { path: "/match/nbr-riv/players", indexable: false },
  { path: "/match/nbr-riv/insights", indexable: false },
  ...claims.map((c) => ({ path: `/match/nbr-riv/evidence/${c.id}`, indexable: false })),
  { path: "/producer/queue", indexable: false },
  { path: "/producer/compose/D-031", indexable: false },
  { path: "/producer/publish/D-031", indexable: false },
  { path: "/workspace/activity", indexable: false },
  { path: "/workspace/settings", indexable: false },
  { path: "/design-system", indexable: false },
];

/** Prefixes crawlers must not index (workspace, producer and developer tools). */
export const disallowedPrefixes: readonly string[] = ["/producer/", "/workspace/", "/design-system", "/dev/", "/api/"];
