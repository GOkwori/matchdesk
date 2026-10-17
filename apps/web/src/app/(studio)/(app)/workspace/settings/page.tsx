/** Settings & Help: display preferences, demo controls and links to every screen. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { TopActions } from "../../../../../studio/shell";
import { PageHead } from "../../../../../studio/ui";
import { SettingsBody } from "../../../../../studio/workspace";

export const metadata: Metadata = { title: "Settings & Help", robots: { index: false } };

export default function SettingsPage() {
  return (
    <div className="md-page">
      <PageHead title="Settings & Help" sub="Preferences are saved on this device only."><TopActions /></PageHead>
      <Suspense><SettingsBody /></Suspense>
    </div>
  );
}
