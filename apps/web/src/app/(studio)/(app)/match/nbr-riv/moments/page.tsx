/** Moments & Timeline: every key moment with deterministic detection reasons and evidence links. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { MomentsBody } from "../../../../../../studio/moments";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Moments & Timeline", robots: { index: false } };

export default function MomentsPage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Overview", href: "/match/nbr-riv" }, { label: "Moments & Timeline" }]} />
      <PageHead title="Moments & Timeline" sub="Pick a moment to see why it was detected and which claims it supports."><TopActions /></PageHead>
      <Suspense><MomentsBody /></Suspense>
    </div>
  );
}
