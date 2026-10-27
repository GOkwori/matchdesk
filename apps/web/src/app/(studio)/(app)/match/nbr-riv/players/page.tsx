/** Players: both squads, each linking to a verified player-focus page. */
import type { Metadata } from "next";
import Link from "next/link";
import { POSITION_LABEL, squads } from "../../../../../../studio/data";
import { matchContext } from "../../../../../../studio/match-context";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../studio/ui";

export const metadata: Metadata = { title: "Players", robots: { index: false } };

export default function PlayersPage() {
  const ctx = matchContext();
  const actions = (id: string) => ctx.events.filter((e) => e.player_id === id && e.match_clock_ms < ctx.replayEndMs).length;
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Match overview", href: "/match/nbr-riv" }, { label: "Players" }]} />
      <PageHead title="Players" sub="Pick a player for a focus page: every figure stated as a sentence and verified against the log." ><TopActions /></PageHead>
      <div className="md-two">
        {(["nbr", "riv"] as const).map((club) => (
          <section key={club} className="md-panel" aria-labelledby={`md-squad-${club}`}>
            <h2 id={`md-squad-${club}`}>{ctx.teams[club]}</h2>
            <ul className="md-squad">
              {squads[club].map((p) => (
                <li key={p.player_id}>
                  <Link href={`/match/nbr-riv/player/${p.player_id}`}>
                    <span className="md-mono md-squad-shirt">{p.shirt}</span>
                    <span className="md-squad-name">{p.name}</span>
                    <span className="md-muted md-small">{POSITION_LABEL[p.position]}{p.starter ? "" : " · bench"}</span>
                    <span className="md-mono md-subtle md-small">{actions(p.player_id)} actions</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
