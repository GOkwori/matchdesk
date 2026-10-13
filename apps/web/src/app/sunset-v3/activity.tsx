/** Sunset Studio v3 Screen 12: activity, audit and preference design preview.
 *
 * All displayed activity comes from the seven named synthetic fixture moments.
 * A fixture event is NOT an authenticated audit record, verification execution,
 * producer decision, or an append-only history. No backend API or persistence
 * is invoked; interactive preferences are local, disposable visual settings.
 */
"use client";

import { useRef, useState, type RefObject, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { editorial, fixture, moments, type Moment } from "./demo-data";

type AuditTab = "activity" | "reviews" | "versions" | "preferences";
type Theme = "dark" | "light";
type TextSize = "default" | "large";

const tabs: readonly { id: AuditTab; label: string }[] = [
  { id: "activity", label: "Activity" },
  { id: "reviews", label: "Review history" },
  { id: "versions", label: "Version history" },
  { id: "preferences", label: "Preferences" },
];

/** A deliberate subset of actual fixture records replaces fabricated audit rows
 * and unsupported verification claims in the approved static mock-up.
 */
const eventIds = ["M-07", "M-06", "M-05", "M-03", "M-02"] as const;
const visibleEvents: readonly Moment[] = eventIds.flatMap(id => {
  const event = moments.find(moment => moment.id === id);
  return event ? [event] : [];
});

/** The selected row only reveals details already present in the frozen fixture. */
function EventDetails({ event, close }: { event: Moment; close: () => void }) {
  return <section id="mdv3-audit-event-details" className="mdv3-audit-detail"
    role="region" aria-label="Selected synthetic event details">
    <div className="mdv3-head"><h3>{event.event} · {event.kind}</h3>
      <button type="button" className="mdv3-secondary" onClick={close}
        aria-label={"Close details for " + event.event}>Close</button>
    </div>
    <dl>
      <div><dt>Event</dt><dd>{event.event}</dd></div>
      <div><dt>Fixture clock</dt><dd>{event.clock}</dd></div>
      <div><dt>Source moment</dt><dd>{event.id}</dd></div>
      <div><dt>Event description</dt><dd>{event.details}</dd></div>
      <div><dt>Score after</dt><dd>{event.scoreAfter}</dd></div>
      <div><dt>Authenticated actor</dt><dd>Not available</dd></div>
      <div><dt>Audit receipt</dt><dd>Not generated</dd></div>
    </dl>
    <p>Inspecting a synthetic fixture event does not create or retrieve a durable audit record.</p>
  </section>;
}

/** Render reference identifiers without claiming stored transitions or approval. */
function PlaceholderHistory({ kind }: { kind: "reviews" | "versions" }) {
  if (kind === "reviews") {
    return <div className="mdv3-audit-empty" role="status">
      <strong>No authenticated review history available</strong>
      <p>The demo contains no verified producer identity, signed decisions or audit receipts. Review actions are unavailable.</p>
      <div className="mdv3-audit-reference">
        <span>{editorial.blockedDraft} · Reference ineligible</span>
        <span>{editorial.eligibleDraft} · Reference eligible, not approved</span>
      </div>
      <p className="mdv3-muted">These are design reference states, not actual review actions or historical transitions.</p>
    </div>;
  }
  return <div className="mdv3-audit-empty" role="status">
    <strong>No durable version history available</strong>
    <p>Draft version IDs in the approved mock-up are illustrative. No saved version changes, immutable comparison chain or publisher receipt is stored here.</p>
    <div className="mdv3-audit-reference">
      <span>{editorial.blockedDraft} · Reference only</span>
      <span>{editorial.eligibleDraft} · Reference only</span>
    </div>
    <p className="mdv3-muted">The separately implemented Story & Commentary Composer captures edits in memory only and resets when left.</p>
  </div>;
}

function onTabKey(
  event: ReactKeyboardEvent<HTMLButtonElement>,
  tab: AuditTab,
  setTab: (value: AuditTab) => void,
  tabRefs: RefObject<Partial<Record<AuditTab, HTMLButtonElement | null>>>
) {
  const keys = tabs.map(item => item.id);
  const current = keys.indexOf(tab);
  const next = event.key === "ArrowRight" ? (current + 1) % keys.length
    : event.key === "ArrowLeft" ? (current + keys.length - 1) % keys.length
    : event.key === "Home" ? 0
    : event.key === "End" ? keys.length - 1 : -1;
  if (next < 0) return;
  event.preventDefault();
  setTab(keys[next]);
  tabRefs.current[keys[next]]?.focus();
}

export function ActivityAuditSettings({
  theme, onThemeChange,
}: {
  theme: Theme;
  onThemeChange: (value: Theme) => void;
}) {
  const [tab, setTab] = useState<AuditTab>("activity");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [textSize, setTextSize] = useState<TextSize>("default");
  const tabRefs = useRef<Partial<Record<AuditTab, HTMLButtonElement | null>>>({});
  const selectedEvent = visibleEvents.find(event => event.event === selectedId);

  return <div className="mdv3-content mdv3-activity"
    data-text-size={textSize} data-reduce-motion={reduceMotion ? "on" : "system"}>
    <header className="mdv3-page-heading">
      <div>
        <span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 12 · SYNTHETIC PREVIEW</span>
        <h1>Activity, Audit &amp; Settings</h1>
        <p>Inspect illustrative fixture events and customise local viewing preferences.</p>
      </div>
      <span className="mdv3-activity-stamp">Concept · Not live</span>
    </header>

    <div className="mdv3-activity-tabs" role="tablist" aria-label="Activity and settings panels">
      {tabs.map(item => <button key={item.id} type="button" role="tab"
        id={"mdv3-activity-tab-" + item.id} aria-controls="mdv3-activity-tabpanel"
        aria-selected={tab === item.id} tabIndex={tab === item.id ? 0 : -1}
        ref={element => { tabRefs.current[item.id] = element; }}
        className={tab === item.id ? "active" : undefined}
        onClick={() => setTab(item.id)}
        onKeyDown={event => onTabKey(event, item.id, setTab, tabRefs)}>
        {item.label}
      </button>)}
    </div>

    <div className="mdv3-activity-layout">
      <section className="mdv3-panel mdv3-activity-primary" role="tabpanel" tabIndex={0}
        id="mdv3-activity-tabpanel" aria-labelledby={"mdv3-activity-tab-" + tab}>
        {tab === "activity" ? <>
          <div className="mdv3-head"><h2>Illustrative activity log</h2></div>
          <p className="mdv3-muted">Five named events in the synthetic fixture — not deployed user activity, verification actions or production audit history.</p>
          <div className="mdv3-activity-table-scroll">
            <table role="table" className="mdv3-activity-table"
              aria-label="Named synthetic fixture events">
              <thead role="rowgroup"><tr role="row">
                <th role="columnheader" scope="col">Replay clock</th>
                <th role="columnheader" scope="col">Recorded fixture event</th>
                <th role="columnheader" scope="col">Category</th>
                <th role="columnheader" scope="col">Inspect</th>
              </tr></thead>
              <tbody role="rowgroup">{visibleEvents.map(event =>
                <tr key={event.event} role="row" data-selected={selectedId === event.event}>
                  <th role="rowheader" scope="row" data-label="Replay clock">{event.clock}</th>
                  <td role="cell" data-label="Recorded fixture event">
                    <strong>{event.title}</strong><small>{event.event} · {event.id}</small>
                  </td>
                  <td role="cell" data-label="Category">
                    <span className="mdv3-activity-category">{event.kind}</span>
                  </td>
                  <td role="cell" data-label="Inspect">
                    <button type="button" className="mdv3-secondary"
                      aria-expanded={selectedId === event.event}
                      aria-controls={selectedId === event.event ? "mdv3-audit-event-details" : undefined}
                      aria-label={"Details for " + event.event}
                      onClick={() => setSelectedId(prev => prev === event.event ? null : event.event)}>
                      Details
                    </button>
                  </td>
                </tr>)}</tbody>
            </table>
          </div>
          {selectedEvent && <EventDetails event={selectedEvent} close={() => setSelectedId(null)}/>}
          <div className="mdv3-activity-info" role="note">
            <span aria-hidden="true">ⓘ</span>
            <div><strong>Read-only demonstration</strong>
              <p>A real audit trail requires authenticated actors, durable append-only records, independently enforced action boundaries and an auditable decision receipt.</p></div>
          </div>
        </> : tab === "reviews" || tab === "versions" ? <>
          <div className="mdv3-head"><h2>{tab === "reviews" ? "Review history" : "Version history"}</h2></div>
          <PlaceholderHistory kind={tab}/>
        </> : <>
          <div className="mdv3-head"><h2>Viewing preferences · local preview</h2></div>
          <p>Use the adjacent panel to change the theme, animation and text scale. These preferences affect only the synthetic preview and are not saved to your account.</p>
          <dl className="mdv3-activity-current">
            <div><dt>Appearance</dt><dd>{theme === "dark" ? "Sunset Studio dark" : "Light"}</dd></div>
            <div><dt>Reduce motion</dt><dd>{reduceMotion ? "On for this view" : "Follow system setting"}</dd></div>
            <div><dt>Text size</dt><dd>{textSize === "large" ? "Large for this view" : "Default"}</dd></div>
            <div><dt>Data freshness</dt><dd>Synthetic replay · {fixture.clock}</dd></div>
          </dl>
          <div className="mdv3-activity-info" role="note"><span aria-hidden="true">ⓘ</span>
            <div><strong>No account preferences are stored</strong>
              <p>Changing appearance cannot grant access, suppress required replay labels or alter source records.</p></div></div>
        </>}
      </section>

      <aside className="mdv3-panel mdv3-activity-preferences"
        aria-labelledby="mdv3-activity-preferences-title">
        <div className="mdv3-head"><h2 id="mdv3-activity-preferences-title">Preferences · design proposal</h2></div>
        <fieldset className="mdv3-activity-appearance">
          <legend>Appearance</legend>
          <div className="mdv3-activity-choice" role="group" aria-label="Audience display appearance">
            <button type="button" className={theme === "dark" ? "active" : undefined}
              aria-pressed={theme === "dark"} onClick={() => onThemeChange("dark")}>
              Sunset Studio dark</button>
            <button type="button" className={theme === "light" ? "active" : undefined}
              aria-pressed={theme === "light"} onClick={() => onThemeChange("light")}>
              Light</button>
          </div>
        </fieldset>
        <div className="mdv3-activity-setting">
          <div><label htmlFor="mdv3-activity-motion">Reduce motion</label>
            <p>Follow system preference by default</p></div>
          <input id="mdv3-activity-motion" type="checkbox" checked={reduceMotion}
            onChange={e => setReduceMotion(e.target.checked)}/>
        </div>
        <div className="mdv3-activity-setting">
          <div><label htmlFor="mdv3-activity-text-size">Text size</label><p>Scale for legibility</p></div>
          <select id="mdv3-activity-text-size" value={textSize}
            onChange={e => setTextSize(e.target.value === "large" ? "large" : "default")}>
            <option value="default">Default</option><option value="large">Large</option>
          </select>
        </div>
        <div className="mdv3-activity-setting">
          <div><strong>Data freshness</strong><p>Clearly display replay status</p></div>
          <span className="mdv3-activity-pill mdv3-activity-required">Required</span>
        </div>
        <div className="mdv3-activity-setting">
          <div><strong>Publish authority</strong><p>Authenticated role and server policy required</p></div>
          <span className="mdv3-activity-pill mdv3-activity-unavailable">Unavailable</span>
        </div>
        <p className="mdv3-muted mdv3-activity-preferences-note">Preferences are session-only. No account settings, authorisation or public content are modified.</p>
      </aside>
    </div>
    <section className="mdv3-control-note" aria-label="Activity audit security boundary">
      <strong>Fixture activity is not an audit trail.</strong>
      <p>The preview has no authenticated actor, durable user activity, signed review, immutable version chain, backend mutation, publication or live telemetry. Source records and backend authorisation remain separate.</p>
    </section>
  </div>;
}
