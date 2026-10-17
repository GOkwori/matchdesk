/** Applies saved display preferences and marks the document interactive once hydrated. */
"use client";

import { useEffect } from "react";
import { applyPrefs, readPrefs } from "./workspace";

export function ReadyMarker() {
  useEffect(() => {
    applyPrefs(readPrefs());
    document.documentElement.dataset.mdReady = "1";
  }, []);
  return null;
}
