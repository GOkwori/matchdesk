/** Custom accessible human-confirmation UI; no authentication or network.
 *
 * Native <dialog> supplies true modal top layer, keyboard focus containment
 * and an inert background. The host must recheck the bound generation and all
 * authorisation controls in the backend transaction before executing a command.
 */
"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  decisionStillCurrent, prepareProducerDecision,
  type DecisionCommandCandidate, type LockedProducerDecision,
  type ProducerDecisionSnapshot,
} from "./decision-confirmation";

export type ProducerDecisionDialogProps = {
  intent: LockedProducerDecision | null;
  current: ProducerDecisionSnapshot | null;
  onDismiss: () => void;
  /** This callback is intent only: it does not confer execution authority. */
  onConfirmed: (candidate: DecisionCommandCandidate) => void | Promise<void>;
};

export function ProducerDecisionDialog({
  intent, current, onDismiss, onConfirmed,
}: ProducerDecisionDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const currentRef = useRef(current);
  const intentRef = useRef(intent);
  const busyRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();
  const reasonId = useId();
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  currentRef.current = current;
  intentRef.current = intent;
  const currentVersion = intent !== null && decisionStillCurrent(intent, current);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (intent !== null && !element.open) {
      previousFocus.current = document.activeElement instanceof HTMLElement
        ? document.activeElement : null;
      setReason("");
      setError("");
      element.showModal();
    } else if (intent === null && element.open) {
      element.close();
      const last = previousFocus.current;
      if (last?.isConnected) last.focus();
      previousFocus.current = null;
    }
  }, [intent]);

  // Route changes must also return focus, not leave the browser on a dead node.
  useEffect(() => () => {
    if (dialog.current?.open) dialog.current.close();
    if (previousFocus.current?.isConnected) previousFocus.current.focus();
  }, []);

  const dismiss = () => { if (!busyRef.current) onDismiss(); };
  const confirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!intent || busyRef.current) return;
    let candidate: DecisionCommandCandidate;
    try {
      candidate = prepareProducerDecision(intent, currentRef.current, reason);
    } catch {
      setError("Review details have changed or are incomplete. Close and refresh.");
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      await onConfirmed(candidate);
      if (intentRef.current === intent) onDismiss();
    } catch {
      // Backend error bodies, access tokens and credential material are private.
      setError("The review was not completed. Nothing has been confirmed.");
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialog} className="md-decision-dialog" aria-modal="true"
      aria-labelledby={titleId} aria-describedby={descriptionId}
      onCancel={(event) => { event.preventDefault(); dismiss(); }}>
      {intent && (
        <div className="md-decision-content">
          <span className="md-eyebrow">Human confirmation · exact version</span>
          <h2 id={titleId}>Review sample producer decision</h2>
          <p id={descriptionId} className="md-muted">
            {intent.action === "approve" ? "Approve" : "Reject"} is the selected decision.
            Confirm only after reviewing the exact content and evidence. This
            dialog does not grant access or enable publishing.
          </p>
          {!currentVersion && (
            <div className="md-banner md-banner-error" role="alert">
              <span className="md-banner-icon" aria-hidden="true">!</span>
              <strong>Review changed</strong>
              <span>Captured evidence or version is stale. Close and reload.</span>
            </div>
          )}
          <dl className="md-decision-binding">
            <div><dt>Session</dt><dd>{intent.snapshot.session_id}</dd></div>
            <div><dt>Output</dt><dd>{intent.snapshot.output_id}</dd></div>
            <div><dt>Decision</dt><dd>{intent.action}</dd></div>
            <div><dt>Review generation</dt><dd>{intent.snapshot.generation}</dd></div>
            <div><dt>Item version</dt><dd>{intent.snapshot.binding.item_version}</dd></div>
            <div><dt>Replay</dt><dd>{intent.snapshot.binding.replay_id}</dd></div>
            <div><dt>Language / persona</dt>
              <dd>{intent.snapshot.binding.language} / {intent.snapshot.binding.persona}</dd></div>
            <div className="md-decision-digest"><dt>Content SHA-256</dt>
              <dd><code>{intent.snapshot.binding.content_digest}</code></dd></div>
            <div className="md-decision-digest"><dt>Evidence SHA-256</dt>
              <dd><code>{intent.snapshot.binding.evidence_digest}</code></dd></div>
          </dl>
          <form onSubmit={(event) => { void confirm(event); }}>
            <label className="md-decision-label" htmlFor={reasonId}>
              Reason for decision <span className="md-muted">(required, max 256 characters)</span>
            </label>
            <input id={reasonId} type="text" className="md-decision-reason"
              value={reason} maxLength={256} autoComplete="off"
              onChange={(event) => setReason(event.target.value)}
              disabled={busy || !currentVersion} aria-invalid={error ? "true" : undefined} />
            {error && <p className="md-decision-error" role="alert">{error}</p>}
            <div className="md-decision-actions">
              <button type="button" autoFocus className="md-btn md-btn-secondary"
                onClick={dismiss} disabled={busy}>Cancel</button>
              <button type="submit" className="md-btn md-btn-primary"
                disabled={busy || !currentVersion || reason.trim().length === 0}>
                {busy ? "Checking..." : "Confirm reviewed version"}
              </button>
            </div>
          </form>
        </div>
      )}
    </dialog>
  );
}
