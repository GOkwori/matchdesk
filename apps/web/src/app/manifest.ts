/** Web app manifest so the demo installs and launches like an app (pairs with the offline worker). */
import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MatchDesk",
    short_name: "MatchDesk",
    description: "Turn football moments into verifiable stories. AI-assisted. Verified. Human-led.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#0e1319",
    theme_color: "#0e1319",
    lang: "en-GB",
    icons: [
      { src: "/icon.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
