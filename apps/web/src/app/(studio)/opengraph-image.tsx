/** Default social card for every studio page that does not define its own. */
import { ogSize, renderCard } from "../../studio/og/card";

export const dynamic = "force-static";
export const alt = "MatchDesk: turn football moments into verifiable stories";
export const size = ogSize;
export const contentType = "image/png";

export default function Image() {
  return renderCard({ eyebrow: "AI-assisted · Verified · Human-led", title: "Turn football moments into verifiable stories", footer: "Synthetic demo: Northbridge FC 2–1 Riverside United" });
}
