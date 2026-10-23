/** Story types and the words around a story that are not facts; safe to load in the browser. */
import type { Claim } from "./verifier";
import type { Persona, ViewerLanguage } from "./viewer";

export type StoryText = { headline: string; body: string };
export type StoryEvent = {
  id: string; t_ms: number; type: string; player: string | null; outcome: string | null; tags: string[];
  x: number | null; y: number | null; end_x: number | null; end_y: number | null;
};
export type Story = {
  slug: string; event_id: string; t_ms: number; clock: string; minute: number; team: "nbr" | "riv"; scorer: string;
  header: boolean; context: string; score: { before: Record<string, number>; after: Record<string, number> };
  scorer_goals: number; lead_in: { kind: "corner" | "interception" | "move"; event_id: string; seconds: number };
  buildup: StoryEvent[]; checks: { claim_ids: string[]; label: Record<ViewerLanguage, string> }[];
  unchecked: Record<ViewerLanguage, string>[]; diagram: Record<ViewerLanguage, string>;
  text: Record<Persona, Record<ViewerLanguage, StoryText>>;
};
export type StoryClaim = { claim_id: string; text: string; status: string; reason: string; claim: Claim };
export type StorySummary = { slug: string; team: "nbr" | "riv"; scorer: string; clock: string; headline: Record<ViewerLanguage, string> };

/** Words around the story that are not facts: labels, notices and the viewer's own lines. */
export const storyChrome: Record<ViewerLanguage, {
  label: string; title: string; matches: string; failed: string; notChecked: string; note: string; translation: string;
  verified: [string, string]; rechecked: string; recheckFailed: string; personas: Record<Persona, string>; style: string;
  more: string; score: (home: number, away: number, clock: string) => string; diagram: string;
  yourClub: (club: string, team: string, mine: boolean) => string; yourPlayer: (name: string) => string;
}> = {
  en: {
    label: "English", title: "How we checked this", matches: "Matches event log", failed: "Does not match the log",
    notChecked: "Not checked · no data", note: "Fans only see this after a producer approves it.", translation: "",
    verified: ["Verified moment", "checked against the match event log"], rechecked: "Checked again in your browser",
    recheckFailed: "Your browser's re-check disagreed; treat this story as unverified",
    personas: { fan: "Fan", analyst: "Analyst", caption: "Caption" }, style: "Style", more: "Other goals in this match",
    score: (h, a, c) => `Northbridge ${h}, Riverside ${a} at ${c}`, diagram: "Diagram of the move",
    yourClub: (club, team, mine) => (mine ? `Your club, ${club}, scored this one.` : `${team} scored against your club, ${club}.`),
    yourPlayer: (name) => `Your player, ${name}, scored.`,
  },
  es: {
    label: "Español", title: "Cómo lo comprobamos", matches: "Coincide con el registro de eventos", failed: "No coincide con el registro de eventos",
    notChecked: "Sin comprobar · sin datos", note: "Los aficionados solo lo ven cuando un productor lo aprueba.",
    translation: "Traducción asistida por IA, pendiente de revisión por un hablante nativo.",
    verified: ["Momento verificado", "comprobado con el registro de eventos del partido"], rechecked: "Comprobado de nuevo en tu navegador",
    recheckFailed: "La comprobación en tu navegador no coincide; trata esta historia como no verificada",
    personas: { fan: "Aficionado", analyst: "Analista", caption: "Rótulo" }, style: "Estilo", more: "Otros goles del partido",
    score: (h, a, c) => `Northbridge ${h}, Riverside ${a} en el ${c}`, diagram: "Diagrama de la jugada",
    yourClub: (club, team, mine) => (mine ? `Tu club, ${club}, marcó este gol.` : `${team} marcó contra tu club, ${club}.`),
    yourPlayer: (name) => `Tu jugador, ${name}, marcó.`,
  },
  fr: {
    label: "Français", title: "Comment nous l’avons vérifié", matches: "Conforme au journal d’événements", failed: "Non conforme au journal d’événements",
    notChecked: "Non vérifié · pas de données", note: "Les supporters ne le voient qu’après validation par un producteur.",
    translation: "Traduction assistée par IA, relecture par un locuteur natif en attente.",
    verified: ["Moment vérifié", "contrôlé avec le journal d’événements du match"], rechecked: "Vérifié à nouveau dans votre navigateur",
    recheckFailed: "La vérification dans votre navigateur ne concorde pas ; considérez cette histoire comme non vérifiée",
    personas: { fan: "Supporter", analyst: "Analyste", caption: "Légende" }, style: "Style", more: "Les autres buts du match",
    score: (h, a, c) => `Northbridge ${h}, Riverside ${a} à ${c}`, diagram: "Schéma de l’action",
    yourClub: (club, team, mine) => (mine ? `Votre club, ${club}, a marqué ce but.` : `${team} a marqué contre votre club, ${club}.`),
    yourPlayer: (name) => `Votre joueur, ${name}, a marqué.`,
  },
};
