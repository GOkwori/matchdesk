/** sitemap.xml: only the public, indexable studio routes. */
import type { MetadataRoute } from "next";
import { SITE_URL, siteRoutes } from "../studio/site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return siteRoutes
    .filter((route) => route.indexable)
    .map((route) => ({ url: `${SITE_URL}${route.path}`, changeFrequency: "monthly", priority: route.path === "/" ? 1 : 0.6 }));
}
