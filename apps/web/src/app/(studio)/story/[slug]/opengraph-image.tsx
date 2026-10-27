/** Social card for each fan story, from its verified English headline. */
import { ogSize, renderCard } from "../../../../studio/og/card";
import { findStory, stories } from "../../../../studio/stories";

export const dynamic = "force-static";
export const alt = "A goal in the synthetic demo match, verified against the match event log";
export const size = ogSize;
export const contentType = "image/png";

export function generateStaticParams() {
  return stories.map((s) => ({ slug: s.slug }));
}

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const story = findStory(slug) ?? stories[stories.length - 1];
  const headline = story.text.fan.en.headline.replace(/^\d+′ · /, "");
  return renderCard({ eyebrow: `Verified moment · ${story.clock}`, title: headline, footer: "Checked against the match event log · Synthetic demo match" });
}
