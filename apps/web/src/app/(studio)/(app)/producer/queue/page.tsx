/** Producer review queue: which drafts can be approved, and what blocks the rest. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { QueueBody } from "../../../../../studio/queue";
import { TopActions } from "../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../studio/ui";

export const metadata: Metadata = { title: "Review queue", robots: { index: false } };

export default function QueuePage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Producer Tools" }, { label: "Review queue" }]} />
      <PageHead title="Review queue" sub="Only drafts whose every claim is verified, or marked as opinion, can be approved."><TopActions /></PageHead>
      <Suspense><QueueBody /></Suspense>
    </div>
  );
}
