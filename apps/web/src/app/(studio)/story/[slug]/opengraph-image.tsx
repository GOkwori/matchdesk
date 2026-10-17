/** Social card for the public fan story. */
import { ogSize, renderCard } from "../../../../studio/og/card";

export const dynamic = "force-static";
export const alt = "58′ goal for Northbridge FC, verified against the match event log";
export const size = ogSize;
export const contentType = "image/png";

export default function Image() {
  return renderCard({ eyebrow: "Verified moment · 58:17", title: "Okafor’s header restores the Northbridge lead", footer: "Checked against the match event log · Synthetic demo match" });
}
