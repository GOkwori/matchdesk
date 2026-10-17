/** Shot map and head-to-head bars drawn from the exported event log (server-safe SVG). */
import { clock, playerName, type ExportEvent } from "./data";

const ON_TARGET = new Set(["goal", "saved"]);

/** Map an event to display coordinates: Northbridge attacks right, Riverside attacks left. */
function place(shot: ExportEvent): { x: number; y: number } {
  const x = shot.x ?? 50;
  const y = shot.y ?? 50;
  return shot.team === "nbr" ? { x: 1 + (x / 100) * 103, y: 1 + (y / 100) * 66 } : { x: 1 + ((100 - x) / 100) * 103, y: 1 + ((100 - y) / 100) * 66 };
}

/** Plot shots on a pitch; goals are large, on-target filled, off-target hollow. */
export function ShotMap({ shots, caption }: { shots: readonly ExportEvent[]; caption: string }) {
  const home = shots.filter((s) => s.team === "nbr");
  const away = shots.filter((s) => s.team === "riv");
  const summary = `${caption}. Northbridge ${home.length} shots, ${home.filter((s) => ON_TARGET.has(s.outcome ?? "")).length} on target, attacking right. Riverside ${away.length} shots, ${away.filter((s) => ON_TARGET.has(s.outcome ?? "")).length} on target, attacking left.`;
  return (
    <figure className="md-shotmap">
      <svg viewBox="0 0 105 68" role="img" aria-label={summary}>
        <rect width="105" height="68" fill="var(--md-pitch)" rx="1.5" />
        <g fill="none" stroke="var(--md-pitch-line)" strokeWidth="0.35">
          <rect x="1" y="1" width="103" height="66" /><path d="M52.5 1v66" /><circle cx="52.5" cy="34" r="9.15" />
          <rect x="1" y="13.85" width="16.5" height="40.3" /><rect x="87.5" y="13.85" width="16.5" height="40.3" />
          <rect x="1" y="24.85" width="5.5" height="18.3" /><rect x="98.5" y="24.85" width="5.5" height="18.3" />
        </g>
        {shots.map((s) => {
          const p = place(s);
          const color = s.team === "nbr" ? "var(--md-home)" : "var(--md-away)";
          const goal = s.outcome === "goal";
          const onTarget = ON_TARGET.has(s.outcome ?? "");
          return (
            <circle key={s.id} cx={p.x} cy={p.y} r={goal ? 2.1 : 1.4}
              fill={onTarget ? color : "none"} stroke={goal ? "var(--md-text)" : color} strokeWidth={goal ? 0.6 : 0.5}>
              <title>{`${s.id} · ${clock(s.clock_ms / 1000)} · ${playerName(s.player)} · ${s.outcome}`}</title>
            </circle>
          );
        })}
      </svg>
      <figcaption>
        <span>{caption}</span>
        <span className="md-legend">
          <span><i className="md-dot-key md-key-home" />NBR</span>
          <span><i className="md-dot-key md-key-away" />RIV</span>
          <span><i className="md-dot-key md-key-hollow" />Off target</span>
          <span><i className="md-dot-key md-key-goal" />Goal</span>
        </span>
      </figcaption>
      <details className="md-table-toggle">
        <summary>View as table</summary>
        <table>
          <caption className="md-visually-hidden">Shots</caption>
          <thead><tr><th scope="col">Event</th><th scope="col">Clock</th><th scope="col">Team</th><th scope="col">Player</th><th scope="col">Outcome</th><th scope="col">Synthetic xG</th></tr></thead>
          <tbody>
            {shots.map((s) => (
              <tr key={s.id}><th scope="row" className="md-mono">{s.id}</th><td className="md-mono">{clock(s.clock_ms / 1000)}</td><td>{s.team === "nbr" ? "NBR" : "RIV"}</td><td>{playerName(s.player)}</td><td>{s.outcome}</td><td>{s.xg}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

/** Diverging head-to-head bars for comparable counts. */
export function Comparison({ rows }: { rows: readonly { label: string; home: number; away: number }[] }) {
  return (
    <ul className="md-compare">
      {rows.map((r) => {
        const total = r.home + r.away || 1;
        return (
          <li key={r.label}>
            <span className="md-compare-num">{r.home}</span>
            <span className="md-compare-bars" aria-hidden="true">
              <span className="md-compare-home"><span style={{ width: `${(r.home / total) * 100}%` }} /></span>
              <span className="md-compare-away"><span style={{ width: `${(r.away / total) * 100}%` }} /></span>
            </span>
            <span className="md-compare-num">{r.away}</span>
            <span className="md-compare-label">{r.label}<span className="md-visually-hidden">: Northbridge {r.home}, Riverside {r.away}</span></span>
          </li>
        );
      })}
    </ul>
  );
}
