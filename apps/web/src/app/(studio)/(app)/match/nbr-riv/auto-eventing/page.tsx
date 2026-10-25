/** Auto-eventing lab: events read from synthetic video by a detector, scored against the log. */
import type { Metadata } from "next";
import { AutoEventingLab } from "../../../../../../studio/auto-eventing";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Video detection experiment", robots: { index: false } };

export default function AutoEventingPage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Match overview", href: "/match/nbr-riv" }, { label: "Watch the replay", href: "/match/nbr-riv/live" }, { label: "Video detection experiment" }]} />
      <PageHead title="Video detection experiment" sub="See how a tool spots football actions in a made-up video, then checks its answers against the event log."><TopActions /></PageHead>
      <AutoEventingLab />
    </div>
  );
}
