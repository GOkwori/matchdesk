/**
 * Root layout for broadcast output: a bare, transparent page a vision mixer or OBS loads as a
 * browser source. No studio shell, no service worker, nothing but the graphic.
 */
import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import "../../studio/tokens.css";
import "../../studio/broadcast.css";

const jakarta = localFont({
  src: [
    { path: "../../studio/fonts/plus-jakarta-sans-latin-600-normal.woff2", weight: "600", style: "normal" },
    { path: "../../studio/fonts/plus-jakarta-sans-latin-700-normal.woff2", weight: "700", style: "normal" },
    { path: "../../studio/fonts/plus-jakarta-sans-latin-800-normal.woff2", weight: "800", style: "normal" },
  ],
  variable: "--md-font-ui-loaded",
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
});

const plexMono = localFont({
  src: [{ path: "../../studio/fonts/ibm-plex-mono-latin-600-normal.woff2", weight: "600", style: "normal" }],
  variable: "--md-font-mono-loaded",
  display: "swap",
  fallback: ["ui-monospace", "monospace"],
});

export const metadata: Metadata = {
  title: "Broadcast overlay · MatchDesk",
  description: "Verified on-screen graphics for a vision mixer or OBS browser source. Synthetic demo.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { colorScheme: "dark" };

export default function BroadcastLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-GB" className={`${jakarta.variable} ${plexMono.variable}`}>
      <body className="md-bc-body">{children}</body>
    </html>
  );
}
