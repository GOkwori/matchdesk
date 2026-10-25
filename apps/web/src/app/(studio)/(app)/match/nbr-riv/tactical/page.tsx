/** Match analysis: filterable shot map, team comparison and evidence-cited interpretations. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { ControlTimeline } from "../../../../../../studio/control";
import { TacticalBody } from "../../../../../../studio/tactical";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Match analysis", robots: { index: false } };

export default function TacticalPage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Match overview", href: "/match/nbr-riv" }, { label: "Match analysis" }]} />
      <PageHead title="Match analysis" sub="See where shots happened, compare the teams and explore what the numbers suggest. Opinions are labelled."><TopActions /></PageHead>
      <Suspense><TacticalBody /></Suspense>
      <ControlTimeline />
    </div>
  );
}
