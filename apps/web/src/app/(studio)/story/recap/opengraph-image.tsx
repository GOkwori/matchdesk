/** Social card for the match recap, from its verified English headline. */
import { ogSize, renderCard } from "../../../../studio/og/card";
import { recaps } from "../../../../studio/recaps";

export const dynamic = "force-static";
export const alt = "An automated match recap in the synthetic demo match, every figure verified against the event log";
export const size = ogSize;
export const contentType = "image/png";

export default async function Image() {
  const latest = recaps[recaps.length - 1];
  return renderCard({ eyebrow: `Automated recap · ${latest.clock}`, title: latest.text.fan.en.headline.replace(/^At \d+:\d+ · /, ""), footer: "Every figure checked against the match event log · Synthetic demo match" });
}
