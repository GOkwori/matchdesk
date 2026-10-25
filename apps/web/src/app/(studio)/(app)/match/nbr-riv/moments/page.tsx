/** Key moments: every key moment with deterministic detection reasons and evidence links. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { MomentsBody } from "../../../../../../studio/moments";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Key moments", robots: { index: false } };

export default function MomentsPage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Match overview", href: "/match/nbr-riv" }, { label: "Key moments" }]} />
      <PageHead title="Key moments" sub="Choose a goal or other big moment to see what happened and which events back it up."><TopActions /></PageHead>
      <Suspense><MomentsBody /></Suspense>
    </div>
  );
}
