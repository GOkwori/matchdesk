/** Marks the document as interactive once React has hydrated (used by browser tests). */
"use client";

import { useEffect } from "react";

export function ReadyMarker() {
  useEffect(() => { document.documentElement.dataset.mdReady = "1"; }, []);
  return null;
}
