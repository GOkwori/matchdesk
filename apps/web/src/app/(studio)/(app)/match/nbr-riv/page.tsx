/** Intelligence Overview (locked screen 01): score, replay, attention, moments and next step. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { OverviewBody } from "../../../../../studio/overview";
import { TopActions } from "../../../../../studio/shell";
import { PageHead } from "../../../../../studio/ui";

export const metadata: Metadata = {
  title: "Intelligence Overview",
  description: "Northbridge FC 2–1 Riverside United (synthetic replay): verified key moments, match statistics and what needs a producer.",
  alternates: { canonical: "/match/nbr-riv" },
};

export default function OverviewPage() {
  return (
    <div className="md-page">
      <PageHead title="Match overview" sub="See the score, the big moments, and what to explore next."><TopActions /></PageHead>
      <Suspense><OverviewBody /></Suspense>
    </div>
  );
}
