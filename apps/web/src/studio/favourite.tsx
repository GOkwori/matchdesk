/** "Make this my player": stores the favourite on this device and opens the replay. */
"use client";

import Link from "next/link";
import { openAssistant } from "./assistant-host";
import { useViewer } from "./viewer";

export function FavouritePlayer({ id, name }: { id: string; name: string }) {
  const { viewer, ready, update } = useViewer();
  const mine = ready && viewer.player === id;
  return (
    <div className="md-btn-row">
      <button type="button" className={`md-btn ${mine ? "md-btn-secondary" : "md-btn-primary"}`} aria-pressed={mine} onClick={() => update({ player: mine ? null : id })}>
        {mine ? `★ ${name} is your player` : `☆ Make ${name} my player`}
      </button>
      <Link href="/match/nbr-riv/live" className="md-btn md-btn-secondary">Follow in the replay</Link>
      <button type="button" className="md-btn md-btn-secondary" onClick={() => openAssistant(`Summarise ${name}'s match`)}>Ask about {name}</button>
    </div>
  );
}
