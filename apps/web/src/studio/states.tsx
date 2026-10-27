/** Route-level error, not-found and loading states, shared by the studio's error.tsx, not-found.tsx and loading.tsx. */
"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { Icon } from "./icons";

/** Friendly failure with a reference ID the presenter can quote, a Retry and a safe way out. */
export function ErrorState({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null);
  const ref = error.digest ?? "client";
  useEffect(() => { heading.current?.focus(); }, []);
  return (
    <div className="md-state">
      <section className="md-panel md-state-card" aria-labelledby="md-error-title">
        <span className="md-state-icon" aria-hidden="true"><Icon name="info" size={26} /></span>
        <h1 id="md-error-title" ref={heading} tabIndex={-1}>This screen didn’t load</h1>
        <p>Nothing you changed has been lost: drafts are saved on this device. Try again, or go back to the match.</p>
        <p className="md-state-ref">Reference: {ref}</p>
        <div className="md-btn-row">
          <button type="button" className="md-btn md-btn-primary" onClick={reset}>Try again</button>
          <Link href="/match/nbr-riv" className="md-btn md-btn-secondary">Back to the match</Link>
        </div>
      </section>
    </div>
  );
}

/** Skeleton that mirrors the shell's page head and panels, so navigation never flashes blank. */
export function LoadingState() {
  return (
    <div className="md-skel" role="status" aria-label="Loading">
      <div className="md-skel-block" style={{ height: 44, width: "40%" }} />
      <div className="md-skel-row">{[0, 1, 2, 3].map((i) => <div key={i} className="md-skel-block" style={{ height: 104 }} />)}</div>
      <div className="md-skel-block" style={{ height: 280 }} />
    </div>
  );
}
