/** The overlay feed as a static, machine-readable file: the same cues the replay shows. */
import feed from "../../../studio/generated/nbr-riv-overlays.json";

export const dynamic = "force-static";

export function GET() {
  return Response.json(feed, { headers: { "Cache-Control": "public, max-age=300" } });
}
