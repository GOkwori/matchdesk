/** Catch-all so unknown addresses get the studio's styled 404 rather than the framework default. */
import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const metadata: Metadata = { title: "Page not found", robots: { index: false } };

export default function Missing(): never {
  notFound();
}
