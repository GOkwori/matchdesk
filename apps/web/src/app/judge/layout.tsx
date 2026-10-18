/** Isolated document root for the opt-in localhost judge workbench. */
import type { ReactNode } from "react";

/**
 * The opt-in judge route lives outside the studio route group, so Next.js
 * requires its own root layout. Keep the document shell minimal and do not
 * change the studio's CSP, authentication, or route-group boundaries.
 */
export default function JudgeLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
