/** Tactical Analysis: filterable shot map, team comparison and evidence-cited interpretations. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { TacticalBody } from "../../../../../../studio/tactical";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Tactical Analysis", robots: { index: false } };

export default function TacticalPage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Overview", href: "/match/nbr-riv" }, { label: "Tactical Analysis" }]} />
      <PageHead title="Tactical Analysis" sub="Where each team shot from, and what the numbers suggest. Interpretations need a producer’s review."><TopActions /></PageHead>
      <Suspense><TacticalBody /></Suspense>
    </div>
  );
}
