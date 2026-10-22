/** Mounts Ask MatchDesk on first use, so its code and the event log load only when opened. */
"use client";

import { useEffect, useState, type ComponentType } from "react";

export const ASSISTANT_EVENT = "md:assistant";

/** Open the assistant, optionally with a question to ask straight away. */
export function openAssistant(question?: string) {
  window.dispatchEvent(new CustomEvent(ASSISTANT_EVENT, { detail: question ?? null }));
}

type PanelProps = { request: { id: number; question: string | null } };

export function AssistantHost() {
  const [Panel, setPanel] = useState<ComponentType<PanelProps> | null>(null);
  const [request, setRequest] = useState<{ id: number; question: string | null } | null>(null);

  useEffect(() => {
    const onOpen = (event: Event) => {
      const question = (event as CustomEvent<string | null>).detail ?? null;
      setRequest((current) => ({ id: (current?.id ?? 0) + 1, question }));
      void import("./assistant").then((module) => setPanel(() => module.Assistant));
    };
    window.addEventListener(ASSISTANT_EVENT, onOpen);
    return () => window.removeEventListener(ASSISTANT_EVENT, onOpen);
  }, []);

  return Panel && request ? <Panel request={request} /> : null;
}
