/** Error boundary for the welcome, about and fan story pages. */
"use client";

import { ErrorState } from "../../studio/states";

export default function StudioError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <main id="main" className="md-welcome-main"><ErrorState error={error} reset={reset} /></main>;
}
