/** App shell for the studio: sidebar, icon rail, mobile tab bar, top actions, search and tour. */
"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import { Logo } from "./ui";
import { claims, drafts, eventCountText, moments, STORY_SLUG, tourSteps } from "./data";

type NavItem = { href: string; label: string; icon: IconName; match: (path: string) => boolean; badge?: string };

const NAV: NavItem[] = [
  { href: "/match/nbr-riv", label: "Overview", icon: "home", match: (p) => p === "/match/nbr-riv" },
  { href: "/match/nbr-riv/live", label: "Live Intelligence", icon: "globe", match: (p) => p.startsWith("/match/nbr-riv/live") },
  { href: "/match/nbr-riv/moments", label: "Moments & Timeline", icon: "list", match: (p) => p.startsWith("/match/nbr-riv/moments") },
  { href: "/match/nbr-riv/tactical", label: "Tactical Analysis", icon: "pitch", match: (p) => p.startsWith("/match/nbr-riv/tactical") },
  { href: "/match/nbr-riv/insights", label: "AI Insights", icon: "sparkle", match: (p) => p.startsWith("/match/nbr-riv/insights") },
  { href: "/match/nbr-riv/evidence/CL-0213", label: "Evidence & Verification", icon: "shield", match: (p) => p.startsWith("/match/nbr-riv/evidence") },
  { href: "/producer/queue", label: "Producer Tools", icon: "monitor", match: (p) => p.startsWith("/producer"), badge: "2" },
  { href: `/story/${STORY_SLUG}`, label: "Audience Story", icon: "phone", match: (p) => p.startsWith("/story") },
  { href: "/workspace/activity", label: "Activity & Audit", icon: "pulse", match: (p) => p.startsWith("/workspace/activity") },
  { href: "/workspace/settings", label: "Settings & Help", icon: "grid", match: (p) => p.startsWith("/workspace/settings") },
];

const TABS: { href: string; label: string; icon: IconName; match: (p: string) => boolean }[] = [
  { href: "/match/nbr-riv", label: "Match", icon: "pulse", match: (p) => p.startsWith("/match/nbr-riv") && !p.startsWith("/match/nbr-riv/evidence") },
  { href: "/match/nbr-riv/evidence/CL-0213", label: "Verify", icon: "shield", match: (p) => p.startsWith("/match/nbr-riv/evidence") },
  { href: "/producer/queue", label: "Produce", icon: "pen", match: (p) => p.startsWith("/producer") },
  { href: `/story/${STORY_SLUG}`, label: "Story", icon: "phone", match: (p) => p.startsWith("/story") },
  { href: "/workspace/settings", label: "Settings", icon: "sliders", match: (p) => p.startsWith("/workspace") || p.startsWith("/design-system") },
];

const LAST_PATH_KEY = "md.lastPath";

/** Remember the last studio route so returning users can resume in one click. */
function useRememberPath() {
  const pathname = usePathname();
  useEffect(() => {
    try { window.localStorage.setItem(LAST_PATH_KEY, pathname); } catch { /* storage unavailable: resume is optional */ }
  }, [pathname]);
}

export function readLastPath(): string | null {
  try { return window.localStorage.getItem(LAST_PATH_KEY); } catch { return null; }
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  useRememberPath();
  return (
    <div className="md-app">
      <a className="md-skip" href="#main">Skip to main content</a>
      <aside className="md-side" aria-label="Main navigation">
        <Logo href="/" />
        <nav aria-label="Workspace">
          <ul className="md-nav">
            {NAV.map((item) => {
              const active = item.match(pathname);
              return (
                <li key={item.href}>
                  <Link href={item.href} className="md-nav-link" aria-current={active ? "page" : undefined}>
                    <Icon name={item.icon} />
                    <span className="md-nav-label">{item.label}</span>
                    {item.badge && <span className="md-badge" aria-label={`${item.badge} drafts`}>{item.badge}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="md-side-foot">
          <div className="md-tagline"><Icon name="wave" size={30} /><span>AI-assisted.<br />Verified.<br />Human-led.</span></div>
        </div>
      </aside>
      <div className="md-body">
        <header className="md-mobile-top">
          <Logo size={30} />
          <TopActions compact />
        </header>
        <main id="main" tabIndex={-1} className="md-main">{children}</main>
      </div>
      <nav className="md-tabs" aria-label="Primary">
        {TABS.map((t) => {
          const active = t.match(pathname);
          return (
            <Link key={t.href} href={t.href} aria-current={active ? "page" : undefined} className="md-tab">
              <Icon name={t.icon} size={22} /><span>{t.label}</span>
            </Link>
          );
        })}
      </nav>
      <CommandPalette />
    </div>
  );
}

/** Replay pill (explains the synthetic data), search, and the signed-in persona. */
export function TopActions({ compact = false }: { compact?: boolean }) {
  const id = compact ? "md-replay-info-m" : "md-replay-info";
  return (
    <div className="md-top-actions">
      <button type="button" className="md-replay-pill" popoverTarget={id}>
        <span className="md-dot" aria-hidden="true" />{compact ? "Replay" : "Synthetic replay"}
      </button>
      <div id={id} popover="auto" className="md-popover" role="note">
        <strong>Synthetic replay</strong>
        <p>Northbridge FC v Riverside United is invented test data replayed from a recorded event log of {eventCountText} events. It is not a live match, and nothing in this demo is published.</p>
      </div>
      <button type="button" className="md-search-btn" onClick={() => window.dispatchEvent(new Event("md:palette"))} aria-label="Search moments, claims and drafts" aria-keyshortcuts="Control+K Meta+K">
        <Icon name="search" size={16} />{!compact && <><span>Search</span><kbd>Ctrl K</kbd></>}
      </button>
      {!compact && <span className="md-avatar" role="img" aria-label="Signed in as Dana Price, producer">DP</span>}
    </div>
  );
}

type PaletteItem = { label: string; hint: string; href: string };

/** Ctrl/Cmd + K jump-to palette, built on the native modal dialog for focus containment. */
function CommandPalette() {
  const ref = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const items = useMemo<PaletteItem[]>(() => [
    { label: "Overview", hint: "Screen", href: "/match/nbr-riv" },
    { label: "Live Intelligence", hint: "Screen", href: "/match/nbr-riv/live" },
    { label: "Tactical Analysis", hint: "Screen", href: "/match/nbr-riv/tactical" },
    { label: "AI insights", hint: "Screen", href: "/match/nbr-riv/insights" },
    { label: "Publication journey", hint: "Screen", href: "/producer/publish/D-031" },
    { label: "Activity & Audit", hint: "Screen", href: "/workspace/activity" },
    { label: "Settings & Help", hint: "Screen", href: "/workspace/settings" },
    { label: "How verification works", hint: "Page", href: "/about" },
    { label: "Moments & Timeline", hint: "Screen", href: "/match/nbr-riv/moments" },
    { label: "Review queue", hint: "Screen", href: "/producer/queue" },
    { label: "Fan story", hint: "Screen", href: `/story/${STORY_SLUG}` },
    { label: "Design system", hint: "Screen", href: "/design-system" },
    ...moments.map((m) => ({ label: `${m.title}`, hint: `${m.id} · moment`, href: `/match/nbr-riv/moments?moment=${m.id}` })),
    ...claims.map((c) => ({ label: c.text, hint: `${c.id} · claim`, href: `/match/nbr-riv/evidence/${c.id}` })),
    ...drafts.map((d) => ({ label: d.title, hint: `${d.id} · draft`, href: d.id === "D-031" ? "/producer/compose/D-031" : "/producer/queue" })),
  ], []);
  const shown = items.filter((i) => `${i.label} ${i.hint}`.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 9);

  useEffect(() => {
    const open = () => { setQuery(""); if (ref.current && !ref.current.open) ref.current.showModal(); };
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
    };
    window.addEventListener("md:palette", open);
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("md:palette", open); window.removeEventListener("keydown", onKey); };
  }, []);

  const go = (href: string) => { ref.current?.close(); router.push(href); };

  return (
    <dialog ref={ref} className="md-palette" aria-labelledby="md-palette-title">
      <form method="dialog" onSubmit={(e) => { e.preventDefault(); if (shown[0]) go(shown[0].href); }}>
        <h2 id="md-palette-title" className="md-visually-hidden">Search MatchDesk</h2>
        <label className="md-palette-field">
          <Icon name="search" size={18} />
          <span className="md-visually-hidden">Search moments, claims, drafts and screens</span>
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search moments, claims, drafts…" />
          <kbd>Esc</kbd>
        </label>
        <ul className="md-palette-list" aria-label="Results">
          {shown.map((i) => (
            <li key={i.href + i.label}>
              <a href={i.href} onClick={(e) => { e.preventDefault(); go(i.href); }}>
                <span>{i.label}</span><span className="md-palette-hint">{i.hint}</span>
              </a>
            </li>
          ))}
          {shown.length === 0 && <li className="md-palette-empty">No matches. Try “Okafor”, “CL-0214” or “D-031”.</li>}
        </ul>
      </form>
    </dialog>
  );
}

const TOUR_DONE_KEY = "md.tourDone";

/** Guided-tour popover; renders only when the URL carries ?tour=<step>. */
export function TourStep({ step }: { step: number }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const current = Number(params.get("tour"));
  const card = useRef<HTMLDivElement>(null);
  const active = current === step;
  // A tour card that loads below the fold (or under the phone tab bar) is invisible guidance:
  // bring it into view once, without moving the page when it is already on screen.
  useEffect(() => {
    const el = card.current;
    if (!active || !el) return;
    const margin = parseFloat(getComputedStyle(el).scrollMarginBottom) || 0;
    const rect = el.getBoundingClientRect();
    if (rect.top >= 0 && rect.bottom <= window.innerHeight - margin) return;
    const reduce = document.documentElement.dataset.mdMotion === "reduce" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [active]);
  if (!active) return null;
  const data = tourSteps[step - 1];
  if (!data) return null;
  const finish = () => {
    try { window.localStorage.setItem(TOUR_DONE_KEY, "1"); } catch { /* optional */ }
    const next = new URLSearchParams(params.toString());
    next.delete("tour");
    router.replace(next.size ? `${pathname}?${next}` : pathname);
  };
  return (
    <div ref={card} className="md-tour" role="dialog" aria-modal="false" aria-labelledby={`md-tour-${step}`}>
      <span className="md-tour-arrow" aria-hidden="true" />
      <div className="md-tour-head">
        <span className="md-tour-eyebrow">Guided tour · {step} of {tourSteps.length}</span>
        <span className="md-tour-dots" aria-hidden="true">{tourSteps.map((_, i) => <i key={i} className={i < step ? "on" : ""} />)}</span>
      </div>
      <h2 id={`md-tour-${step}`} className="md-tour-title">{data.title}</h2>
      <p className="md-tour-body">{data.body}</p>
      <div className="md-tour-actions">
        <button type="button" className="md-tour-skip" onClick={finish}>{data.next ? "Skip tour" : "Close"}</button>
        {data.next
          ? <Link className="md-tour-next" href={data.next}>{data.nextLabel} <Icon name="arrow" size={16} /></Link>
          : <Link className="md-tour-next" href="/" onClick={() => { try { window.localStorage.setItem(TOUR_DONE_KEY, "1"); } catch { /* optional */ } }}>Finish tour <Icon name="arrow" size={16} /></Link>}
      </div>
    </div>
  );
}
