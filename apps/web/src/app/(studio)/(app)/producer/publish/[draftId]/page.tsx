/** Review & Publication journey (future state) for the synthetic D-031 draft. */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { PublicationBody } from "../../../../../../studio/publication";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Publication journey", robots: { index: false } };

export function generateStaticParams() {
  return [{ draftId: "D-031" }];
}
export const dynamicParams = false;

export default async function PublishPage({ params }: { params: Promise<{ draftId: string }> }) {
  const { draftId } = await params;
  if (draftId !== "D-031") notFound();
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Producer Tools", href: "/producer/queue" }, { label: "Composer", href: "/producer/compose/D-031" }, { label: "Publication" }]} />
      <PageHead title="Publication journey" sub="Future state: how approval and publishing will work. Nothing is published in this demo."><TopActions /></PageHead>
      <Suspense><PublicationBody /></Suspense>
    </div>
  );
}
