/** Moments & Timeline: full event timeline with a deep-linkable selected moment (?moment=M-05). */
"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Icon } from "./icons";
import { GoalPitch, VerdictChip } from "./ui";
import { TourStep } from "./shell";
import { clock, eventCountText, findMoment, keySeconds, moments, scoreAt, storyCheck, type Moment } from "./data";

const kindIcon = { Goal: "ball", Corner: "flag", Substitution: "swap", "Yellow card": "card" } as const;

/** Rule-based detection signals; these are deterministic explanations, not model confidence. */
function signals(m: Moment): { label: string; value: string }[] {
  const before = scoreAt(m.seconds - 1);
  const after = scoreAt(m.seconds);
  const rows = [{ label: "Logged event", value: `${m.event} · ${m.kind} at ${clock(m.seconds)}` }];
  if (m.id === "M-05") {
    // Computed by the registered sequence_gap.v1 query, not written by hand.
    const gap = storyCheck("FS-CORNER-GAP");
    const fact = gap.claim.fact!;
    rows.push({
      label: "Preceding corner",
      value: gap.result.status === "verified"
        ? `${fact.from_event_id} at ${clock(keySeconds(fact.from_event_id!))}, ${fact.gap_seconds} seconds earlier · verified`
        : `Not verified: ${gap.result.reason}`,
    });
  }
  if (m.kind === "Goal") rows.push({ label: "Score change", value: `${before.home}–${before.away} → ${after.home}–${after.away}` });
  return rows;
}

export function MomentsBody() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selected = findMoment(params.get("moment")) ?? findMoment("M-05")!;

  const select = (id: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("moment", id);
    router.replace(`${pathname}?${next}`, { scroll: false });
  };
  const halves = [
    { label: "First half", items: moments.filter((m) => m.seconds < 45 * 60) },
    { label: "Second half", items: moments.filter((m) => m.seconds >= 45 * 60) },
  ];

  return (
    <div className="md-split">
      <section className="md-panel md-split-main" aria-labelledby="md-timeline-title">
        <div className="md-panel-head"><h2 id="md-timeline-title">Match timeline</h2><span className="md-muted">7 key moments · {eventCountText} events</span></div>
        {halves.map((h) => (
          <div key={h.label} className="md-half">
            <h3 className="md-half-label">{h.label}</h3>
            <ul className="md-timeline">
              {h.items.map((m) => {
                const active = m.id === selected.id;
                return (
                  <li key={m.id}>
                    <button type="button" className={`md-tl-item${active ? " md-tl-active" : ""}`} aria-pressed={active} onClick={() => select(m.id)}>
                      <span className={`md-tl-dot md-moment-${m.team === "NBR" ? "home" : "away"}`}><Icon name={kindIcon[m.kind]} size={16} /></span>
                      <span className="md-mono md-moment-clock">{clock(m.seconds)}</span>
                      <span className="md-moment-text"><strong>{m.title}</strong><span>{m.kind} · {m.team === "NBR" ? "Northbridge" : "Riverside"}</span></span>
                      {m.claimIds.length > 0 && <VerdictChip verdict="verified" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </section>
      <aside className="md-split-side" aria-label="Selected moment">
        <section className="md-panel md-selected" aria-labelledby="md-sel-title">
          <span className="md-mono md-accent-soft-text">{selected.id} · {selected.event} · {clock(selected.seconds)}</span>
          <h2 id="md-sel-title" className="md-sel-title">{selected.title}</h2>
          <p className="md-muted">{selected.detail}</p>
          {selected.kind === "Goal" && selected.team === "NBR" && (
            <GoalPitch variant={selected.id === "M-05" ? "header" : "right-foot"} label={selected.id === "M-05" ? "Corner from the right, then a header inside the six-yard box" : "Right-footed finish from the edge of the box"} />
          )}
          <h3 className="md-h3">Why this moment was detected</h3>
          <dl className="md-rows">
            {signals(selected).map((r) => <div key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>)}
          </dl>
          <div className="md-btn-row">
            {selected.claimIds[0]
              ? <Link href={`/match/nbr-riv/evidence/${selected.claimIds[0]}`} className="md-btn md-btn-primary">Check the evidence <Icon name="arrow" size={16} /></Link>
              : <span className="md-muted">No claims reference this moment yet.</span>}
            <Link href={`/match/nbr-riv?t=${selected.seconds}`} className="md-btn md-btn-secondary">Jump replay here</Link>
          </div>
        </section>
        <TourStep step={2} />
      </aside>
    </div>
  );
}
