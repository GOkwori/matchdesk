/** Demo activity: sample editing history and the D-031 versions made on this device. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { TopActions } from "../../../../../studio/shell";
import { PageHead } from "../../../../../studio/ui";
import { ActivityBody } from "../../../../../studio/workspace";

export const metadata: Metadata = { title: "Demo activity", robots: { index: false } };

export default function ActivityPage() {
  return (
    <div className="md-page">
      <PageHead title="Demo activity" sub="See sample editing history and changes saved on this device. This is not a real user audit log."><TopActions /></PageHead>
      <Suspense><ActivityBody /></Suspense>
    </div>
  );
}
