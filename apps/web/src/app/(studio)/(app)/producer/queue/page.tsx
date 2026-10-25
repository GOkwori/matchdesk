/** Producer review queue: which drafts can be approved, and what blocks the rest. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { QueueBody } from "../../../../../studio/queue";
import { TopActions } from "../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../studio/ui";

export const metadata: Metadata = { title: "Review drafts", robots: { index: false } };

export default function QueuePage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Studio demo" }, { label: "Review drafts" }]} />
      <PageHead title="Review drafts" sub="Try reviewing sample stories. A draft is ready only when its facts are checked or clearly marked as opinion."><TopActions /></PageHead>
      <Suspense><QueueBody /></Suspense>
    </div>
  );
}
