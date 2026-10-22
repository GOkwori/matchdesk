/** Root layout for the locked Sunset Studio frontend: self-hosted fonts, tokens and metadata. */
import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import { AssistantHost } from "../../studio/assistant-host";
import { OfflineNotice, ReadyMarker } from "../../studio/ready";
import { SITE_URL } from "../../studio/site";
import "../../studio/tokens.css";
import "../../studio/studio.css";

const jakarta = localFont({
  src: [
    { path: "../../studio/fonts/plus-jakarta-sans-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../../studio/fonts/plus-jakarta-sans-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "../../studio/fonts/plus-jakarta-sans-latin-600-normal.woff2", weight: "600", style: "normal" },
    { path: "../../studio/fonts/plus-jakarta-sans-latin-700-normal.woff2", weight: "700", style: "normal" },
    { path: "../../studio/fonts/plus-jakarta-sans-latin-800-normal.woff2", weight: "800", style: "normal" },
  ],
  variable: "--md-font-ui-loaded",
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
});

const plexMono = localFont({
  src: [
    { path: "../../studio/fonts/ibm-plex-mono-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "../../studio/fonts/ibm-plex-mono-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
  variable: "--md-font-mono-loaded",
  display: "swap",
  // Mono is for small clocks and IDs; fetch it after the page's critical CSS and scripts.
  preload: false,
  fallback: ["ui-monospace", "monospace"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "MatchDesk · Football intelligence, explained and verified", template: "%s · MatchDesk" },
  description: "MatchDesk turns football match events into verifiable stories: AI-assisted analysis, deterministic verification and human approval. Synthetic demo.",
  applicationName: "MatchDesk",
  openGraph: {
    title: "MatchDesk",
    description: "Turn football moments into verifiable stories. AI-assisted. Verified. Human-led.",
    type: "website",
    locale: "en_GB",
    siteName: "MatchDesk",
  },
  twitter: { card: "summary_large_image" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: "#0e1319",
  colorScheme: "dark",
};

export default function StudioRootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-GB" className={`${jakarta.variable} ${plexMono.variable}`}>
      <body className="md-root">{children}<OfflineNotice /><ReadyMarker /><AssistantHost /></body>
    </html>
  );
}
