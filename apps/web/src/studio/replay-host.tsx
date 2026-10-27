/** Mounts the replay player on demand, so the Live page's first load carries none of it. */
"use client";

import dynamic from "next/dynamic";

const ReplayPlayer = dynamic(() => import("./replay"), {
  ssr: false,
  loading: () => (
    <section className="md-panel md-lr" aria-labelledby="md-lr-title" aria-busy="true">
      <div className="md-panel-head"><h2 id="md-lr-title">Replay the match</h2><span className="md-muted md-small">Loading the event log…</span></div>
      <div className="md-bcast md-bcast-loading" />
    </section>
  ),
});

export function ReplayHost() {
  return <ReplayPlayer />;
}
