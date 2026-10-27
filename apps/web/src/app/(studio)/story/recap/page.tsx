/** Automated match recaps for fans, analysts and captions, every figure verified against the log. */
import type { Metadata } from "next";
import { Suspense } from "react";
import { RecapBody } from "../../../../studio/recap";
import { matchExport } from "../../../../studio/data";
import { recapClaims, recapMatchId, recapReplayEndMs, recaps } from "../../../../studio/recaps";

const latest = recaps[recaps.length - 1];

export const metadata: Metadata = {
  title: "Match recap",
  description: `${latest.text.fan.en.body} Every figure verified against the event log. Synthetic demo match.`,
  alternates: { canonical: "/story/recap" },
  openGraph: { title: `${latest.text.fan.en.headline} · MatchDesk`, description: "An automated match recap, every figure verified.", type: "article" },
};

export default function RecapPage() {
  return (
    <Suspense>
      <RecapBody recaps={recaps} claims={recapClaims} names={matchExport.display_names} matchId={recapMatchId} replayEndMs={recapReplayEndMs} />
    </Suspense>
  );
}
