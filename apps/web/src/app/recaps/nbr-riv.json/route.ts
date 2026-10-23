/** The match recaps as a static, machine-readable file: every figure with the claim behind it. */
import feed from "../../../studio/generated/nbr-riv-recaps.json";

export const dynamic = "force-static";

export function GET() {
  return Response.json(feed, { headers: { "Cache-Control": "public, max-age=300" } });
}
