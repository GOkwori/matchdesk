/** Applies saved display preferences, registers the offline worker and marks the document interactive. */
"use client";

import { useEffect, useState } from "react";
import { applyPrefs, readPrefs } from "./workspace";

export function ReadyMarker() {
  useEffect(() => {
    applyPrefs(readPrefs());
    document.documentElement.dataset.mdReady = "1";
    // Production only: a dev-server worker would cache stale hot-reload bundles.
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator && window.isSecureContext) {
      navigator.serviceWorker.register("/sw.js").then(
        () => {
          document.documentElement.dataset.mdOffline = "ready";
          // Warm the lazily loaded event log in idle time, so the worker caches it and the
          // in-browser re-verification also works with no connection.
          const idle = window.requestIdleCallback ?? ((fn: () => void) => window.setTimeout(fn, 2000));
          idle(() => { void import("./generated/nbr-riv-events.json"); });
        },
        () => { /* the demo still works online without the worker */ },
      );
    }
  }, []);
  return null;
}

/** A calm, polite notice when the connection drops: the demo keeps working from this device. */
export function OfflineNotice() {
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, []);
  return (
    <div role="status" aria-live="polite" className="md-offline-slot">
      {offline && <p className="md-offline"><span className="md-dot md-dot-warn" aria-hidden="true" />You’re offline. The demo keeps working from this device.</p>}
    </div>
  );
}
