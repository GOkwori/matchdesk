/** Reserved producer BFF route: disabled until independently approved Entra host.
 *
 * The generic Next rewrite excludes /api/workforce. This opt-in transport contract
 * must not accept browser bearer tokens, simulated identities or environment-only
 * activation. Only a separately reviewed real host may replace the null adapter.
 */
import type { NextRequest } from "next/server";
import { createWorkforceBff } from "../../../../../workforce/bff";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Context = { params: Promise<{ segments: string[] }> };
const disabled = createWorkforceBff(null);

/** The shipped frontend has no valid workforce session issuer or mutation rights. */
export async function POST(request: NextRequest, context: Context): Promise<Response> {
  const { segments } = await context.params;
  return disabled(request, segments);
}
