/** Read-only inspection of deterministic synthetic MatchDesk producer evidence. */
"use client";

import { useEffect, useState } from "react";

type Preview = {
  mode: "synthetic_read_only";
  scenario: string;
  output: {
    binding: { item_id: string; item_version: number; content_digest: string; evidence_digest: string };
    payload: { kind: string; lines: { claim_id: string; text: string }[] };
  };
  claim: { claim_id: string; text: string };
  verification: { status: string; query_id: string; reason: string; expected: number | null; observed: number | null };
  evidence: { evidence_id: string; event_ids: string[] };
  review_status: "pending_verification";
  authenticated: false;
  publication_enabled: false;
};

/** Make the server response untrusted: no missing or contradictory flags are accepted. */
function isPreview(value: unknown): value is Preview {
  if (typeof value !== "object" || value === null) return false;
  const data = value as Record<string, unknown>;
  if (data.mode !== "synthetic_read_only" || data.authenticated !== false ||
    data.publication_enabled !== false || data.review_status !== "pending_verification") return false;
  const output = data.output as Record<string, unknown> | undefined;
  const verification = data.verification as Record<string, unknown> | undefined;
  const evidence = data.evidence as Record<string, unknown> | undefined;
  const binding = output?.binding as Record<string, unknown> | undefined;
  const payload = output?.payload as Record<string, unknown> | undefined;
  return typeof binding?.item_id === "string" && typeof binding.item_version === "number" &&
    typeof binding.content_digest === "string" && typeof binding.evidence_digest === "string" &&
    /^[0-9a-f]{64}$/.test(binding.content_digest) &&
    /^[0-9a-f]{64}$/.test(binding.evidence_digest) &&
    payload?.kind === "commentary" && Array.isArray(payload.lines) &&
    payload.lines.length > 0 &&
    payload.lines.every((line: unknown) => typeof line === "object" && line !== null &&
      typeof (line as Record<string, unknown>).text === "string") &&
    typeof verification?.status === "string" && typeof verification.reason === "string" &&
    typeof evidence?.evidence_id === "string" && Array.isArray(evidence.event_ids);
}

/** Present real checked synthetic evidence without a misleading approval affordance. */
export default function ProducerPreviewPage() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 8000);
    void (async () => {
      try {
        const response = await fetch("/api/producer/preview", {
          signal: abort.signal, cache: "no-store",
        });
        if (!response.ok) throw new Error(`Evidence request failed (HTTP ${response.status})`);
        const value: unknown = await response.json();
        if (!isPreview(value)) throw new Error("Unexpected producer preview contract");
        setPreview(value);
      } catch (cause) {
        if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : "Request failed");
      } finally {
        clearTimeout(timer);
      }
    })();
    return () => { clearTimeout(timer); abort.abort(); };
  }, []);

  return <main>
    <header><a href="/" className="wordmark">MatchDesk<span> / PRODUCER DESK</span></a>
      <p className="stage">Synthetic evidence · Read-only preview</p></header>
    <section className="introduction"><p className="eyebrow">P3-05 · INSPECT FIRST</p>
      <h1>Producer evidence desk</h1>
      <p>This is a real deterministic example, not a live match or a stored producer decision.
        Approval, editing and publication are locked until authenticated, durable review is implemented.</p>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    {!preview && !error && <p role="status">Loading synthetic evidence…</p>}
    {preview && <div className="workspace">
      <section className="desk-panel" aria-label="Proposed commentary and source">
        <h2>Draft commentary</h2>
        <p className="notice">Scenario: {preview.scenario} · {preview.output.payload.kind}</p>
        {preview.output.payload.lines.map((line) =>
          <p key={line.claim_id}>{line.text}</p>)}
        <h2>Source evidence</h2>
        <p>Evidence record: <code>{preview.evidence.evidence_id}</code></p>
        <p>Referenced event IDs: {preview.evidence.event_ids.join(", ")}</p>
      </section>
      <aside aria-label="Verification and producer controls">
        <h2>Verification</h2>
        <p>{preview.verification.status} · {preview.verification.query_id}</p>
        <p>{preview.verification.reason}</p>
        <p>Measured: {preview.verification.observed ?? "N/A"} · Asserted: {preview.verification.expected ?? "N/A"}</p>
        <h2>Producer status</h2>
        <p>Awaiting authenticated review · version {preview.output.binding.item_version}</p>
        <p className="notice">Item: {preview.output.binding.item_id}</p>
        <label>Content SHA-256</label><code>{preview.output.binding.content_digest}</code>
        <label>Evidence SHA-256</label><code>{preview.output.binding.evidence_digest}</code>
        <p className="notice">Edit, reverify, approve, reject and publish are unavailable in this preview.</p>
      </aside>
    </div>}
    <footer>Original seeded synthetic data · No model call · No producer authentication · No publication</footer>
  </main>;
}
