/** Public fan story (locked screen 04): a verified moment explained for supporters. */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { StoryBody } from "../../../../studio/story";
import { STORY_SLUG } from "../../../../studio/data";

export const metadata: Metadata = {
  title: "58′ Goal for Northbridge FC",
  description: "Okafor heads in a corner to put Northbridge back in front, verified against the match event log. Synthetic demo match.",
  alternates: { canonical: `/story/${STORY_SLUG}` },
  openGraph: { title: "58′ Goal for Northbridge FC · MatchDesk", description: "A verified football moment, explained.", type: "article" },
};

export function generateStaticParams() {
  return [{ slug: STORY_SLUG }];
}
export const dynamicParams = false;

export default async function StoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (slug !== STORY_SLUG) notFound();
  return <Suspense><StoryBody /></Suspense>;
}
