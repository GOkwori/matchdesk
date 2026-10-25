/** Story & Commentary Composer (locked screen 03) for the synthetic D-031 draft. */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { ComposerBody } from "../../../../../../studio/composer";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Composer · D-031", robots: { index: false } };

export function generateStaticParams() {
  return [{ draftId: "D-031" }];
}
export const dynamicParams = false;

export default async function ComposerPage({ params }: { params: Promise<{ draftId: string }> }) {
  const { draftId } = await params;
  if (draftId !== "D-031") notFound();
  return (
    <div className="md-page">
      <PageHead title="Write a match story" sub="Edit a sample story and see whether the recorded match events support each sentence."><TopActions /></PageHead>
      <Suspense><ComposerBody /></Suspense>
    </div>
  );
}
