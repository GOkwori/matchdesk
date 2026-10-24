/** Verifier benchmark: hundreds of false sentences built from the demo's claims, and how many were caught. */
import type { Metadata } from "next";
import { VerifierBenchmark } from "../../../../../../../studio/benchmark";
import { TopActions } from "../../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../../studio/ui";

export const metadata: Metadata = { title: "Try to fool the verifier", robots: { index: false } };

export default function BenchmarkPage() {
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Overview", href: "/match/nbr-riv" }, { label: "Evidence & Verification", href: "/match/nbr-riv/evidence/CL-0214" }, { label: "Try to fool the verifier" }]} />
      <PageHead title="Try to fool the verifier" sub="Every claim the demo shows, made wrong one way at a time, and what the verifier did with each."><TopActions /></PageHead>
      <VerifierBenchmark />
    </div>
  );
}
