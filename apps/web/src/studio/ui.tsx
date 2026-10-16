/** Presentational building blocks for the locked Sunset Studio design (server-safe). */
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import mark from "./assets/matchdesk-mark-256.png";
import { Icon, type IconName } from "./icons";
import { fixture, statistics, verdictLabel, type Verdict } from "./data";

/** Panther mark plus wordmark; the image is decorative because the text names the product. */
export function Logo({ size = 36, href = "/" }: { size?: number; href?: string }) {
  return (
    <Link href={href} className="md-logo">
      <Image src={mark} alt="" width={size} height={size} unoptimized priority />
      <span>Match<span className="md-accent-text">Desk</span></span>
    </Link>
  );
}

/** Team shields: Northbridge solid orange, Riverside red stripes. */
export function Crest({ team, size = 46 }: { team: "NBR" | "RIV"; size?: number }) {
  const label = team === "NBR" ? `${fixture.home.name} crest` : `${fixture.away.name} crest`;
  const h = Math.round(size * 1.15);
  if (team === "NBR") {
    return (
      <svg width={size} height={h} viewBox="0 0 40 46" role="img" aria-label={label}>
        <path d="M3 3h34v20c0 11-8 17-17 21C11 40 3 34 3 23z" fill="var(--md-home)" stroke="var(--md-text)" strokeWidth="1.6" />
        <path d="M11 30 20 14l9 16z" fill="#1d252c" />
      </svg>
    );
  }
  const id = `riv-clip-${size}`;
  return (
    <svg width={size} height={h} viewBox="0 0 40 46" role="img" aria-label={label}>
      <defs><clipPath id={id}><path d="M3 3h34v20c0 11-8 17-17 21C11 40 3 34 3 23z" /></clipPath></defs>
      <g clipPath={`url(#${id})`}>
        <rect width="40" height="46" fill="#1d252c" />
        <rect x="7" width="6" height="46" fill="var(--md-away)" />
        <rect x="17" width="6" height="46" fill="var(--md-away)" />
        <rect x="27" width="6" height="46" fill="var(--md-away)" />
      </g>
      <path d="M3 3h34v20c0 11-8 17-17 21C11 40 3 34 3 23z" fill="none" stroke="var(--md-text)" strokeWidth="1.6" />
    </svg>
  );
}

/** Compact score strip used on detail screens, with an optional breadcrumb trail. */
export function ScoreStrip({ crumbs }: { crumbs?: { label: string; href?: string }[] }) {
  return (
    <div className="md-strip">
      <span className="md-strip-score">
        <Crest team="NBR" size={22} />{fixture.home.short}
        <span className="md-strip-num" aria-label="2 to 1">2 – 1</span>
        {fixture.away.short}<Crest team="RIV" size={22} />
      </span>
      <span className="md-mono md-accent-soft-text">67:12</span>
      {crumbs && (
        <nav aria-label="Breadcrumb" className="md-crumbs">
          <ol>
            {crumbs.map((c, i) => (
              <li key={c.label}>
                {c.href ? <Link href={c.href}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
                {i < crumbs.length - 1 && <span aria-hidden="true" className="md-crumb-sep">›</span>}
              </li>
            ))}
          </ol>
        </nav>
      )}
    </div>
  );
}

const chipIcon: Record<Verdict, string> = { verified: "✓", pending: "!", failed: "✕", "not-yet": "○" };

/** Status is always icon + label + colour, never colour alone. */
export function VerdictChip({ verdict, label, pill = false }: { verdict: Verdict; label?: string; pill?: boolean }) {
  return (
    <span className={`md-chip md-chip-${verdict}${pill ? " md-chip-pill" : ""}`}>
      <span aria-hidden="true">{chipIcon[verdict]}</span> {label ?? verdictLabel[verdict]}
    </span>
  );
}

export function KpiTile({ icon, tone, value, unit, label }: { icon: IconName; tone: "success" | "warn" | "error" | "info"; value: string; unit?: string; label: string }) {
  return (
    <article className={`md-kpi md-tone-${tone}`}>
      <span className="md-kpi-icon"><Icon name={icon} size={22} /></span>
      <span className="md-kpi-text">
        <span className="md-kpi-value">{value}{unit && <span className="md-kpi-unit">{unit}</span>}</span>
        <span className="md-kpi-label">{label}</span>
      </span>
    </article>
  );
}

/** The one primary action that moves the user forward in the journey. */
export function NextStep({ eyebrow = "Your next step", title, body, href, action }: { eyebrow?: string; title: string; body?: string; href: string; action: string }) {
  return (
    <section className="md-next" aria-label={eyebrow}>
      <span className="md-eyebrow">{eyebrow}</span>
      <h2 className="md-next-title">{title}</h2>
      {body && <p className="md-next-body">{body}</p>}
      <Link href={href} className="md-btn md-btn-primary">{action} <Icon name="arrow" size={16} /></Link>
    </section>
  );
}

/** Head-to-head stat bars with a text-table fallback for assistive technology. */
export function StatBars() {
  return (
    <section className="md-panel md-stats" aria-labelledby="md-stats-title">
      <div className="md-panel-head">
        <h2 id="md-stats-title">Match statistics</h2>
        <span className="md-legend"><span><i className="md-sw md-sw-home" />NBR</span><span><i className="md-sw md-sw-away" />RIV</span></span>
      </div>
      {statistics.map((s) => {
        const suffix = "suffix" in s ? s.suffix : "";
        return (
          <div className="md-stat" key={s.label}>
            <div className="md-stat-row"><strong>{s.home}{suffix}</strong><span>{s.label}</span><strong>{s.away}{suffix}</strong></div>
            <div className="md-stat-bar" aria-hidden="true">
              <span className="md-bar-home" style={{ flexGrow: s.home || 0.0001 }} />
              <span className="md-bar-away" style={{ flexGrow: s.away || 0.0001 }} />
            </div>
          </div>
        );
      })}
      <details className="md-table-toggle">
        <summary>View as table</summary>
        <table>
          <caption className="md-visually-hidden">Match statistics at 67:12</caption>
          <thead><tr><th scope="col">Statistic</th><th scope="col">Northbridge</th><th scope="col">Riverside</th></tr></thead>
          <tbody>{statistics.map((s) => <tr key={s.label}><th scope="row">{s.label}</th><td>{s.home}</td><td>{s.away}</td></tr>)}</tbody>
        </table>
      </details>
    </section>
  );
}

/** Pitch diagram for event locations; markers are scripted illustrations of logged events. */
export function GoalPitch({ variant, label }: { variant: "header" | "right-foot" | "both"; label: string }) {
  return (
    <svg viewBox="0 0 105 68" role="img" aria-label={label} className="md-pitch">
      <g fill="none" stroke="var(--md-pitch-line)" strokeWidth="0.6">
        <rect x="1" y="1" width="103" height="66" /><path d="M52.5 1v66" /><circle cx="52.5" cy="34" r="9.15" />
        <rect x="87.5" y="13.85" width="16.5" height="40.3" /><rect x="98.5" y="24.85" width="5.5" height="18.3" />
        <rect x="1" y="13.85" width="16.5" height="40.3" />
      </g>
      {(variant === "header" || variant === "both") && (
        <g>
          <path d="M103 2C95 8 94 20 98 32" stroke="var(--md-accent-soft)" strokeWidth="0.9" strokeDasharray="2 1.6" fill="none" />
          <circle cx="98" cy="33" r="2.4" fill="var(--md-home)" stroke="var(--md-text)" strokeWidth="0.6" />
        </g>
      )}
      {(variant === "right-foot" || variant === "both") && (
        <g>
          <circle cx="90" cy="41" r="2.4" fill="var(--md-home)" stroke="var(--md-text)" strokeWidth="0.6" />
          <path d="M90 41 103.5 36" stroke="var(--md-accent-soft)" strokeWidth="0.9" fill="none" />
        </g>
      )}
    </svg>
  );
}

export function PageHead({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) {
  return (
    <div className="md-pagehead">
      <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
      {children}
    </div>
  );
}
