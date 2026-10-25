/** Try demo publishing: a browser-only approval and send for the synthetic D-031 draft. */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { PublicationBody } from "../../../../../../studio/publication";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Try demo publishing", robots: { index: false } };

export function generateStaticParams() {
  return [{ draftId: "D-031" }];
}
export const dynamicParams = false;

export default async function PublishPage({ params }: { params: Promise<{ draftId: string }> }) {
  const { draftId } = await params;
  if (draftId !== "D-031") notFound();
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Review drafts", href: "/producer/queue" }, { label: "Write a match story", href: "/producer/compose/D-031" }, { label: "Try demo publishing" }]} />
      <PageHead title="Try demo publishing" sub="Practise approving a sample story and sending it to pretend channels. Nobody is signed in and nothing leaves this browser."><TopActions /></PageHead>
      <Suspense><PublicationBody /></Suspense>
    </div>
  );
}
