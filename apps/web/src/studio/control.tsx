/** Control vs chaos: five-minute windows labelled by a published rule, with the verified sentences behind each phase. */
import { clock } from "./data";
import { CHAOS_RECOVERIES_PER_MINUTE, CONTROL_ACCURACY, CONTROL_POSSESSION, controlPhases, type Phase, type WindowReading } from "./insight-engine";
import { matchContext } from "./match-context";
import { roundHalfUp } from "./precision";

const KIND_LABEL = { control: "Control", chaos: "Chaos", contested: "Contested" } as const;

function phaseTitle(phase: Pick<Phase, "kind" | "team">, teams: Record<string, string>): string {
  return phase.kind === "control" && phase.team ? `${teams[phase.team]} in control` : phase.kind === "chaos" ? "Chaos: the ball kept changing hands" : "Contested";
}

function fill(w: Pick<WindowReading, "kind" | "team">): string {
  if (w.kind === "control") return w.team === "nbr" ? "var(--md-home)" : "var(--md-away)";
  return w.kind === "chaos" ? "var(--md-warn)" : "var(--md-raised)";
}

const pct = (v: number | null) => (v == null ? "–" : `${roundHalfUp(v * 100, 0)}%`);
const kmh = (v: number | null) => (v == null ? "–" : `${roundHalfUp(v, 1)} km/h`);

/** The band, the rhythm rows and the phase list. Rendered on the server; no browser JavaScript. */
export function ControlTimeline() {
  const ctx = matchContext();
  const phases = controlPhases(ctx);
  const windows = phases.flatMap((p) => p.windows);
  const end = ctx.replayEndMs;
  const x = (ms: number) => 64 + (ms / end) * 528;
  const maxRec = Math.max(...windows.map((w) => w.recoveries.nbr + w.recoveries.riv));
  const maxSpeed = Math.max(...windows.flatMap((w) => [w.ballSpeed.nbr ?? 0, w.ballSpeed.riv ?? 0]));
  const summary = phases.map((p) => `${p.scope}: ${phaseTitle(p, ctx.teams)}`).join("; ");
  return (
    <section className="md-panel md-control" aria-labelledby="md-control-title">
      <div className="md-panel-head">
        <h2 id="md-control-title">Control and chaos</h2>
        <span className="md-chip md-chip-not-yet">Rule, not AI</span>
      </div>
      <p className="md-muted md-small">
        Every five minutes is labelled by a fixed rule over recomputed figures. <strong>Control</strong>: one side has at least {CONTROL_POSSESSION * 100}% of the ball and completes at least {CONTROL_ACCURACY * 100}% of its passes. <strong>Chaos</strong>: the two sides win the ball back at least {CHAOS_RECOVERIES_PER_MINUTE} times a minute between them. Anything else is <strong>contested</strong>.
      </p>
      <figure className="md-chart">
        <svg viewBox="0 0 600 150" role="img" aria-label={`Match phases to ${clock(end / 1000)}. ${summary}.`}>
          <g fontFamily="var(--md-font-mono)" fontSize="10" fill="var(--md-subtle)">
            <text x="0" y="28">Phase</text>
            <text x="0" y="78">Won back</text>
            <text x="0" y="128">Ball speed</text>
            {[0, 15, 30, 45, 60].map((m) => <text key={m} x={x(m * 60_000) - 6} y="148">{m}′</text>)}
          </g>
          {windows.map((w) => (
            <g key={w.fromMs}>
              <rect x={x(w.fromMs) + 0.5} y="10" width={x(w.toMs) - x(w.fromMs) - 1} height="28" rx="3" fill={fill(w)} opacity={w.kind === "contested" ? 1 : 0.85}>
                <title>{`${clock(w.fromMs / 1000)}–${clock(w.toMs / 1000)} · ${KIND_LABEL[w.kind]}${w.team ? ` (${ctx.teams[w.team]})` : ""} · possession ${pct(w.possession)}–${pct(1 - w.possession)} · passing ${pct(w.accuracy.nbr)} / ${pct(w.accuracy.riv)} · won back ${w.recoveries.nbr + w.recoveries.riv}`}</title>
              </rect>
              <rect x={x(w.fromMs) + 3} y={90 - ((w.recoveries.nbr + w.recoveries.riv) / maxRec) * 34} width={x(w.toMs) - x(w.fromMs) - 6} height={((w.recoveries.nbr + w.recoveries.riv) / maxRec) * 34} fill={w.kind === "chaos" ? "var(--md-warn)" : "var(--md-subtle)"} opacity="0.8" />
            </g>
          ))}
          {(["nbr", "riv"] as const).map((team) => (
            <path key={team} fill="none" stroke={team === "nbr" ? "var(--md-home)" : "var(--md-away)"} strokeWidth="2" strokeLinejoin="round"
              d={windows.map((w, i) => `${i ? "L" : "M"}${((x(w.fromMs) + x(w.toMs)) / 2).toFixed(1)} ${(136 - ((w.ballSpeed[team] ?? 0) / maxSpeed) * 34).toFixed(1)}`).join(" ")} />
          ))}
        </svg>
        <figcaption className="md-legend">
          <span><i style={{ background: "var(--md-home)" }} />Northbridge control</span>
          <span><i style={{ background: "var(--md-away)" }} />Riverside control</span>
          <span><i style={{ background: "var(--md-warn)" }} />Chaos</span>
          <span><i style={{ background: "var(--md-raised)" }} />Contested</span>
          <span className="md-muted">Lines: estimated ball speed, the match rhythm</span>
        </figcaption>
        <details className="md-table-toggle">
          <summary>View as table</summary>
          <table className="md-table">
            <caption className="md-visually-hidden">Each five-minute window, its figures and its label</caption>
            <thead><tr><th scope="col">Window</th><th scope="col">Label</th><th scope="col">Possession</th><th scope="col">Passing</th><th scope="col">Won back</th><th scope="col">Under pressure</th><th scope="col">Ball speed</th></tr></thead>
            <tbody>
              {windows.map((w) => (
                <tr key={w.fromMs}>
                  <td className="md-mono">{clock(w.fromMs / 1000)}–{clock(w.toMs / 1000)}</td>
                  <td>{KIND_LABEL[w.kind]}{w.team ? ` · ${ctx.teams[w.team]}` : ""}</td>
                  <td className="md-mono">{pct(w.possession)} / {pct(1 - w.possession)}</td>
                  <td className="md-mono">{pct(w.accuracy.nbr)} / {pct(w.accuracy.riv)}</td>
                  <td className="md-mono">{w.recoveries.nbr} / {w.recoveries.riv}</td>
                  <td className="md-mono">{w.pressured.nbr} / {w.pressured.riv}</td>
                  <td className="md-mono">{kmh(w.ballSpeed.nbr)} / {kmh(w.ballSpeed.riv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="md-muted md-small">Pairs read Northbridge / Riverside.</p>
        </details>
      </figure>
      <ol className="md-phases">
        {phases.map((p) => (
          <li key={p.fromMs} className={`md-phase md-phase-${p.kind}${p.team ? ` md-phase-${p.team}` : ""}`}>
            <div className="md-phase-head"><span className="md-mono">{p.scope}</span><strong>{phaseTitle(p, ctx.teams)}</strong></div>
            <p className="md-muted md-small">{p.reason}</p>
            <ul className="md-phase-lines">
              {p.lines.map((l) => (
                <li key={l.claim.text}>
                  <span className={`md-chip md-chip-${l.result.status === "verified" ? "verified" : "failed"}`}><span aria-hidden="true">{l.result.status === "verified" ? "✓" : "✕"}</span> {l.result.status === "verified" ? "Verified" : "Not verified"}</span>
                  <span>{l.claim.text}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
      <p className="md-muted md-small">Ball speed is estimated from pass length and the time to the next logged event; there is no tracking data. The match is synthetic, so these phases describe invented play.</p>
    </section>
  );
}
