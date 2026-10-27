/** Design system (locked screen 05): tokens and components rendered from the real CSS. */
import type { Metadata } from "next";
import { Icon } from "../../../../studio/icons";
import { TopActions } from "../../../../studio/shell";
import { PageHead, VerdictChip } from "../../../../studio/ui";

export const metadata: Metadata = { title: "Design system", description: "MatchDesk Sunset Studio tokens and components.", robots: { index: false } };

const swatches = [
  ["Canvas", "--md-canvas"], ["Panel", "--md-panel"], ["Raised", "--md-raised"], ["Line", "--md-line"],
  ["Control line", "--md-control-line"], ["Text", "--md-text"], ["Muted", "--md-muted"], ["Accent", "--md-accent"],
  ["Accent soft", "--md-accent-soft"], ["Success", "--md-success"], ["Info", "--md-info"], ["Warning", "--md-warn"],
  ["Error", "--md-error"], ["Home", "--md-home"], ["Away", "--md-away"], ["Pitch", "--md-pitch"],
] as const;

export default function DesignSystemPage() {
  return (
    <div className="md-page">
      <PageHead title="Design system" sub="Sunset Studio · locked 16 Oct 2026. Every sample below uses the production CSS."><TopActions /></PageHead>
      <div className="md-ds">
        <section className="md-panel md-ds-wide" aria-labelledby="ds-tokens">
          <h2 id="ds-tokens">Colour tokens</h2>
          <ul className="md-swatches">
            {swatches.map(([name, token]) => (
              <li key={token}><span className="md-swatch" style={{ background: `var(${token})` }} /><strong>{name}</strong><code>{token}</code></li>
            ))}
          </ul>
        </section>
        <section className="md-panel" aria-labelledby="ds-type">
          <h2 id="ds-type">Type</h2>
          <p className="md-ds-display">Display 40</p>
          <p className="md-ds-h1">Heading 28</p>
          <p className="md-ds-h2">Section 16</p>
          <p>Body 14 · Plus Jakarta Sans</p>
          <p className="md-mono md-accent-soft-text">67:12 · E-1366 · CL-0213</p>
        </section>
        <section className="md-panel" aria-labelledby="ds-buttons">
          <h2 id="ds-buttons">Buttons</h2>
          <div className="md-btn-row">
            <button type="button" className="md-btn md-btn-primary">Submit for review</button>
            <button type="button" className="md-btn md-btn-secondary">Cancel</button>
            <button type="button" className="md-btn md-btn-danger">Discard changes</button>
            <button type="button" className="md-btn md-btn-primary" disabled>Disabled</button>
          </div>
          <p className="md-locked"><Icon name="lock" size={14} /> Approve · Planned</p>
        </section>
        <section className="md-panel" aria-labelledby="ds-chips">
          <h2 id="ds-chips">Status · icon + label, never colour alone</h2>
          <div className="md-btn-row">
            <VerdictChip verdict="verified" /><VerdictChip verdict="pending" /><VerdictChip verdict="failed" /><VerdictChip verdict="not-yet" />
            <VerdictChip pill verdict="verified" label="Eligible" /><VerdictChip pill verdict="failed" label="Not eligible" />
          </div>
        </section>
        <section className="md-panel md-ds-wide" aria-labelledby="ds-banners">
          <h2 id="ds-banners">Banners</h2>
          <div className="md-stack">
            <div className="md-banner md-banner-info"><span className="md-banner-icon" aria-hidden="true">i</span><strong>Information</strong><span>D-029 is ready for review.</span></div>
            <div className="md-banner md-banner-warn"><span className="md-banner-icon" aria-hidden="true">!</span><strong>Warning</strong><span>You have unsaved changes.</span></div>
            <div className="md-banner md-banner-error"><span className="md-banner-icon" aria-hidden="true">!</span><strong>Error</strong><span>We couldn’t save your changes. Your work hasn’t been lost. <code>ref: req-7f3a</code></span></div>
            <div className="md-banner md-banner-success"><span className="md-banner-icon" aria-hidden="true">✓</span><strong>Success</strong><span>D-031 v4 re-verified and eligible.</span></div>
          </div>
        </section>
        <section className="md-panel md-ds-wide" aria-labelledby="ds-stepper">
          <h2 id="ds-stepper">Workflow stepper</h2>
          <ol className="md-stepper">
            <li className="done"><span>✓</span>Ready</li>
            <li className="done"><span>✓</span>Eligible</li>
            <li className="current" aria-current="step"><span>3</span>Approve</li>
            <li><span>4</span>Destinations</li>
            <li><span>5</span>Published</li>
          </ol>
        </section>
      </div>
    </div>
  );
}
