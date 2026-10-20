/** Exact-version, view-only producer decision confirmation contract.
 *
 * Human intent is never a grant, authenticated identity, current-MFA proof,
 * or publication permission. Trusted host and PostgreSQL command boundaries
 * must recheck binding, authorization, grant and CAS independently.
 */
const ID = /^[A-Za-z0-9_-]{1,96}$/;
const DIGEST = /^[a-f0-9]{64}$/;
const LANGUAGES = new Set(["en", "es", "fr"]);
const PERSONAS = new Set(["analyst", "casual_fan", "broadcast_caption"]);
const ACTIONS = new Set(["approve", "reject"]);

export type DecisionAction = "approve" | "reject";
export type ProducerApprovalBinding = Readonly<{
  item_id: string;
  item_version: number;
  replay_id: string;
  content_digest: string;
  evidence_digest: string;
  language: "en" | "es" | "fr";
  persona: "analyst" | "casual_fan" | "broadcast_caption";
}>;
export type ProducerDecisionSnapshot = Readonly<{
  session_id: string;
  output_id: string;
  generation: number;
  review_status: "ready_for_decision";
  binding: ProducerApprovalBinding;
}>;
export type LockedProducerDecision = Readonly<{
  action: DecisionAction;
  snapshot: ProducerDecisionSnapshot;
}>;
export type DecisionCommandCandidate = Readonly<{
  action: DecisionAction;
  session_id: string;
  output_id: string;
  body: Readonly<{
    binding: ProducerApprovalBinding;
    expected_generation: number;
    reason: string;
  }>;
}>;

function denied(): never {
  throw new Error("Producer confirmation requires a fresh exact-version review");
}

/** Only canonical, complete server review shapes can be confirmed. */
function validSnapshot(input: ProducerDecisionSnapshot | null): input is ProducerDecisionSnapshot {
  if (input === null || typeof input !== "object") return false;
  const b = input.binding;
  return Boolean(
    b && typeof b === "object" &&
    typeof input.session_id === "string" && ID.test(input.session_id) &&
    typeof input.output_id === "string" && ID.test(input.output_id) &&
    Number.isSafeInteger(input.generation) && input.generation >= 1 &&
    input.review_status === "ready_for_decision" &&
    typeof b.item_id === "string" && b.item_id === input.output_id &&
    Number.isSafeInteger(b.item_version) && b.item_version >= 1 &&
    typeof b.replay_id === "string" && ID.test(b.replay_id) &&
    typeof b.content_digest === "string" && DIGEST.test(b.content_digest) &&
    typeof b.evidence_digest === "string" && DIGEST.test(b.evidence_digest) &&
    typeof b.language === "string" && LANGUAGES.has(b.language) &&
    typeof b.persona === "string" && PERSONAS.has(b.persona)
  );
}

/** Freeze a defensive copy of every binding field, excluding display text. */
export function lockProducerDecision(
  snapshot: ProducerDecisionSnapshot, action: DecisionAction,
): LockedProducerDecision {
  if (!ACTIONS.has(action) || !validSnapshot(snapshot)) return denied();
  const binding: ProducerApprovalBinding = Object.freeze({
    item_id: snapshot.binding.item_id,
    item_version: snapshot.binding.item_version,
    replay_id: snapshot.binding.replay_id,
    content_digest: snapshot.binding.content_digest,
    evidence_digest: snapshot.binding.evidence_digest,
    language: snapshot.binding.language,
    persona: snapshot.binding.persona,
  });
  return Object.freeze({
    action,
    snapshot: Object.freeze({
      session_id: snapshot.session_id,
      output_id: snapshot.output_id,
      generation: snapshot.generation,
      review_status: snapshot.review_status,
      binding,
    }),
  });
}

/** Treat any changed field as stale, not as a retryable client update. */
export function decisionStillCurrent(
  intent: LockedProducerDecision, current: ProducerDecisionSnapshot | null,
): boolean {
  if (!intent || !validSnapshot(current) || !validSnapshot(intent.snapshot) ||
      !ACTIONS.has(intent.action)) return false;
  const a = intent.snapshot, b = current;
  return a.session_id === b.session_id &&
    a.output_id === b.output_id &&
    a.generation === b.generation &&
    a.review_status === b.review_status &&
    a.binding.item_id === b.binding.item_id &&
    a.binding.item_version === b.binding.item_version &&
    a.binding.replay_id === b.binding.replay_id &&
    a.binding.content_digest === b.binding.content_digest &&
    a.binding.evidence_digest === b.binding.evidence_digest &&
    a.binding.language === b.binding.language &&
    a.binding.persona === b.binding.persona;
}

/** Form only the exact Python ProducerDecisionRequest, plus fixed route keys.
 *
 * The action selects the reviewed endpoint and is NEVER a JSON body field.
 * This UI preflight cannot replace atomic backend grants and compare-and-swap.
 */
export function prepareProducerDecision(
  intent: LockedProducerDecision, current: ProducerDecisionSnapshot | null,
  reason: string,
): DecisionCommandCandidate {
  if (!decisionStillCurrent(intent, current) || typeof reason !== "string") return denied();
  const explanation = reason.trim();
  if (explanation.length < 1 || explanation.length > 256 ||
      /[\u0000-\u001f\u007f]/.test(explanation)) return denied();
  return Object.freeze({
    action: intent.action,
    session_id: intent.snapshot.session_id,
    output_id: intent.snapshot.output_id,
    body: Object.freeze({
      binding: Object.freeze({ ...intent.snapshot.binding }),
      expected_generation: intent.snapshot.generation,
      reason: explanation,
    }),
  });
}
