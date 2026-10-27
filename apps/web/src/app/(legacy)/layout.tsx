/** Document shell for the local foundation; no third-party fonts or tracking. */
import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./styles.css";

export const metadata: Metadata = {
  title: "MatchDesk | Foundation workbench",
  description: "Local synthetic event contract validation. Production workflows are not connected.",
  robots: { index: false, follow: false },
};

/** Establish the language and accessible page root shared by all workbench views. */
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en-GB"><body>{children}</body></html>;
}
