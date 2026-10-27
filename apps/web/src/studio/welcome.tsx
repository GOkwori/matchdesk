/** Returning-user resume card, shown only when this device has visited the studio before. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "./icons";
import { readLastPath } from "./shell";

const NAMES: { prefix: string; label: string }[] = [
  { prefix: "/producer/compose", label: "Write a match story · D-031" },
  { prefix: "/producer/queue", label: "Review drafts" },
  { prefix: "/match/nbr-riv/evidence", label: "Check the facts" },
  { prefix: "/match/nbr-riv/moments", label: "Key moments" },
  { prefix: "/story", label: "Match stories" },
  { prefix: "/design-system", label: "Design guide" },
  { prefix: "/match/nbr-riv", label: "Match overview" },
];

export function ContinueCard() {
  const [last, setLast] = useState<string | null>(null);
  useEffect(() => { setLast(readLastPath()); }, []);
  if (!last || last === "/") return null;
  const name = NAMES.find((n) => last.startsWith(n.prefix))?.label ?? "your last screen";
  return (
    <Link href={last} className="md-continue">
      <span className="md-eyebrow">Continue where you left off</span>
      <strong>{name}</strong>
      <span className="md-link">Resume <Icon name="arrow" size={14} /></span>
    </Link>
  );
}
