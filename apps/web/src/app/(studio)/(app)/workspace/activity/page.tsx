/** Activity & Audit: who did what, when, and every D-031 version. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { TopActions } from "../../../../../studio/shell";
import { PageHead } from "../../../../../studio/ui";
import { ActivityBody } from "../../../../../studio/workspace";

export const metadata: Metadata = { title: "Activity & Audit", robots: { index: false } };

export default function ActivityPage() {
  return (
    <div className="md-page">
      <PageHead title="Activity & Audit" sub="Every verification, edit and decision, newest first."><TopActions /></PageHead>
      <Suspense><ActivityBody /></Suspense>
    </div>
  );
}
