/** A notice shown only on the studio-only copy (Vercel), which has no API behind it. */
"use client";

import { useEffect, useState } from "react";
import { Icon } from "./icons";

/** The full demo on Azure: the studio with the API, live stream, live agent runs and MCP behind it. */
const FULL_DEMO_URL = "https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io";

const HOSTED_KEY = "md.hostedNotice";

/**
 * On the studio-only copy (Vercel), say that the live features run on Azure and link there.
 * Dismissing it keeps it closed for the rest of the visit.
 */
function Notice() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let dismissed = false;
    try { dismissed = window.sessionStorage.getItem(HOSTED_KEY) === "1"; } catch { /* storage blocked: show it */ }
    setOpen(!dismissed);
  }, []);
  if (!open) return null;
  const close = () => {
    setOpen(false);
    try { window.sessionStorage.setItem(HOSTED_KEY, "1"); } catch { /* storage blocked */ }
  };
  return (
    <aside className="md-hosted" aria-label="About this copy">
      <p>This copy replays the match in your browser. The live stream, live agent runs on Microsoft Foundry and the MCP endpoint run on Azure.</p>
      <a className="md-btn md-btn-primary md-btn-sm" href={FULL_DEMO_URL}>Open the full demo</a>
      <button type="button" className="md-hosted-close" aria-label="Dismiss" onClick={close}><Icon name="close" size={18} /></button>
    </aside>
  );
}

/** Decided at build time, so the full demo ships none of this code. */
export const HostedCopyNotice = process.env.MATCHDESK_STUDIO_ONLY === "1" ? Notice : () => null;
