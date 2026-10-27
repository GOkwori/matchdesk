/** Broadcast overlay for the demo match: verified lower-thirds and a score bug, on a transparent page. */
import { Suspense } from "react";
import { BroadcastOverlay } from "../../../../studio/broadcast";

export default function BroadcastPage() {
  return <Suspense><BroadcastOverlay /></Suspense>;
}
