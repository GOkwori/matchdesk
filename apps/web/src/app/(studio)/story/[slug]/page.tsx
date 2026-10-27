/** Public fan story (locked screen 04): one verified goal explained for supporters. */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { StoryBody } from "../../../../studio/story";
import { matchExport } from "../../../../studio/data";
import { findStory, stories, storyClaims, storyMatchId, storyReplayEndMs, storySummaries } from "../../../../studio/stories";

export function generateStaticParams() {
  return stories.map((s) => ({ slug: s.slug }));
}
export const dynamicParams = false;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const story = findStory(slug);
  if (!story) return { title: "Story" };
  const fan = story.text.fan.en;
  return {
    title: fan.headline,
    description: `${fan.body} Verified against the match event log. Synthetic demo match.`,
    alternates: { canonical: `/story/${story.slug}` },
    openGraph: { title: `${fan.headline} · MatchDesk`, description: "A verified football moment, explained.", type: "article" },
  };
}

export default async function StoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const story = findStory(slug);
  if (!story) notFound();
  const others = storySummaries().filter((s) => s.slug !== story.slug);
  return (
    <Suspense>
      <StoryBody story={story} claims={storyClaims(story)} others={others} names={matchExport.display_names} matchId={storyMatchId} replayEndMs={storyReplayEndMs} />
    </Suspense>
  );
}
