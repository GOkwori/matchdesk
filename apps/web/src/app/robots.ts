/** robots.txt: crawl the public story and explainer; keep workspace and developer tools out. */
import type { MetadataRoute } from "next";
import { disallowedPrefixes, SITE_URL } from "../studio/site";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: [...disallowedPrefixes] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
