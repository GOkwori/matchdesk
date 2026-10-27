/** Settings and help: display preferences, demo controls and links to every screen. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { TopActions } from "../../../../../studio/shell";
import { PageHead } from "../../../../../studio/ui";
import { SettingsBody } from "../../../../../studio/workspace";

export const metadata: Metadata = { title: "Settings and help", robots: { index: false } };

export default function SettingsPage() {
  return (
    <div className="md-page">
      <PageHead title="Settings and help" sub="Choose your team or player, adjust the display and restart this demo. Your choices stay on this device."><TopActions /></PageHead>
      <Suspense><SettingsBody /></Suspense>
    </div>
  );
}
