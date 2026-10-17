/** AI insights: specialist proposals that only a human producer can act on. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { InsightsBody } from "../../../../../../studio/insights";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "AI insights", robots: { index: false } };

export default function InsightsPage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Overview", href: "/match/nbr-riv" }, { label: "AI insights" }]} />
      <PageHead title="AI insights" sub="Scripted specialist proposals for this demo (no live model). Each one cites its evidence and waits for you."><TopActions /></PageHead>
      <Suspense><InsightsBody /></Suspense>
    </div>
  );
}
