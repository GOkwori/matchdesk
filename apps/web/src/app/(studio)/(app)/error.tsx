/** Error boundary for app screens; renders inside the shell so navigation stays available. */
"use client";

import { ErrorState } from "../../../studio/states";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorState error={error} reset={reset} />;
}
