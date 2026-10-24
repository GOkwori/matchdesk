/**
 * Voice-over: verified stories, recaps and overlays read aloud. On the Azure deployment the
 * API voices the item with Azure AI Speech (the item is named, never the text); elsewhere, or
 * if that fails, the device's own speech voice reads the same verified text.
 */
"use client";

import { useEffect, useState } from "react";
import type { ViewerLanguage } from "./viewer";

/** "text" is computed in the browser (an Ask answer): only the device voice reads it. */
export type VoiceItem = { kind: "story" | "recap" | "cue" | "text"; id: string; lang: ViewerLanguage; text: string };
export type VoiceSource = "azure" | "device" | "none";

/** Set at build time where the API sits behind /api (the Azure demo). */
const SERVER = process.env.NEXT_PUBLIC_MATCHDESK_LIVE_STREAM === "true";
const LOCALE: Record<ViewerLanguage, string> = { en: "en-GB", es: "es-ES", fr: "fr-FR" };
const COPY: Record<ViewerLanguage, { listen: string; stop: string; azure: string; device: string; none: string }> = {
  en: { listen: "Listen", stop: "Stop", azure: "Voice: Azure AI Speech", device: "Voice: your device", none: "No voice on this device" },
  es: { listen: "Escuchar", stop: "Detener", azure: "Voz: Azure AI Speech", device: "Voz: tu dispositivo", none: "Sin voz en este dispositivo" },
  fr: { listen: "Écouter", stop: "Arrêter", azure: "Voix : Azure AI Speech", device: "Voix : votre appareil", none: "Pas de voix sur cet appareil" },
};

let playing: HTMLAudioElement | null = null;

/** Stop whatever is being read. */
export function stopVoice(): void {
  playing?.pause();
  playing = null;
  try { window.speechSynthesis?.cancel(); } catch { /* no speech engine */ }
}

/** Read one verified item; resolves with the voice used. ``onEnd`` runs when it finishes. */
export async function speak(item: VoiceItem, onEnd?: () => void): Promise<VoiceSource> {
  stopVoice();
  if (SERVER && item.kind !== "text") {
    const audio = new Audio(`/api/voice/${item.kind}/${encodeURIComponent(item.id)}?persona=fan&lang=${item.lang}`);
    audio.onended = () => onEnd?.();
    playing = audio;
    try {
      await audio.play();
      return "azure";
    } catch {
      if (playing === audio) playing = null;
    }
  }
  const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
  if (!synth) return "none";
  const utterance = new SpeechSynthesisUtterance(item.text);
  utterance.lang = LOCALE[item.lang];
  const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(item.lang));
  if (voice) utterance.voice = voice;
  utterance.onend = () => onEnd?.();
  synth.speak(utterance);
  return "device";
}

/** A Listen / Stop button for one item, with a note saying which voice is reading. */
export function ListenButton({ item }: { item: VoiceItem }) {
  const [state, setState] = useState<"idle" | "playing">("idle");
  const [source, setSource] = useState<VoiceSource | null>(null);
  const copy = COPY[item.lang];
  useEffect(() => () => stopVoice(), []);
  useEffect(() => { stopVoice(); setState("idle"); }, [item.id, item.lang, item.text]);
  const toggle = async () => {
    if (state === "playing") { stopVoice(); setState("idle"); return; }
    setState("playing");
    const used = await speak(item, () => setState("idle"));
    setSource(used);
    if (used === "none") setState("idle");
  };
  return (
    <span className="md-listen">
      <button type="button" className="md-btn md-btn-secondary md-btn-sm" aria-pressed={state === "playing"} onClick={toggle}>
        <span aria-hidden="true">{state === "playing" ? "■" : "▶"}</span> {state === "playing" ? copy.stop : copy.listen}
      </button>
      {source && <span className="md-muted md-small" role="status">{copy[source]}</span>}
    </span>
  );
}

/** Spoken text from a headline and body: screen marks such as "59′ ·" are dropped. */
export function spoken(headline: string, body: string): string {
  return `${headline.replace(/^[0-9]+′ · /, "")}. ${body}`;
}
