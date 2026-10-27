/** Recap types and the words around a recap that are not facts; safe to load in the browser. */
import type { StoryClaim } from "./story-chrome";
import type { Persona, ViewerLanguage } from "./viewer";

type Words = Record<ViewerLanguage, string>;
export type RecapMilestone = { t_ms: number; kind: "goal" | "brace" | "shots"; team: "nbr" | "riv"; event_id: string; label: Words; claim_ids: string[] };
export type Recap = {
  id: "half-time" | "latest"; t_ms: number; clock: string; half: boolean; title: Words;
  score: Record<string, number>;
  goals: { event_id: string; t_ms: number; clock: string; team: "nbr" | "riv"; scorer: string; story: string | null }[];
  figures: {
    possession: Record<string, number>; shots: Record<string, number>; pass_accuracy: Record<string, number>;
    synthetic_xg: Record<string, number>; tackles_leader: { player: string; team: string; tackles: number };
  };
  milestones: RecapMilestone[];
  checks: { label: Words; claim_ids: string[] }[];
  unchecked: Words[];
  text: Record<Persona, Record<ViewerLanguage, { headline: string; body: string }>>;
};
export type RecapClaim = StoryClaim;

/** Words around the recap that are not facts: labels, notices and the viewer's own lines. */
export const recapChrome: Record<ViewerLanguage, {
  label: string; recaps: string; verified: [string, string]; recheckFailed: string; rechecked: string;
  style: string; personas: Record<Persona, string>; figures: string; possession: string; shots: string; passing: string;
  xg: string; tackles: string; milestones: string; title: string; matches: string; failed: string; notChecked: string;
  note: string; translation: string; story: string; yourClub: (club: string, ahead: boolean | null) => string;
  score: (h: number, a: number, at: string) => string; feed: string;
}> = {
  en: {
    label: "English", recaps: "Recaps", verified: ["Verified recap", "every figure checked against the match event log"],
    recheckFailed: "Your browser's re-check disagreed; treat this recap as unverified", rechecked: "Checked again in your browser",
    style: "Style", personas: { fan: "Fan", analyst: "Analyst", caption: "Caption" }, figures: "The figures",
    possession: "Possession", shots: "Shots", passing: "Passes completed", xg: "Expected goals (synthetic)", tackles: "Most tackles",
    milestones: "Milestones", title: "How we checked this", matches: "Matches event log", failed: "Does not match the log",
    notChecked: "Not checked · no data", note: "Fans only see this after a producer approves it.", translation: "",
    story: "Read the story", feed: "Recaps as JSON",
    yourClub: (club, ahead) => (ahead == null ? `Your club, ${club}, is level.` : ahead ? `Your club, ${club}, is ahead.` : `Your club, ${club}, is behind.`),
    score: (h, a, at) => `Northbridge ${h}, Riverside ${a}, ${at}`,
  },
  es: {
    label: "Español", recaps: "Resúmenes", verified: ["Resumen verificado", "cada cifra comprobada con el registro de eventos del partido"],
    recheckFailed: "La nueva comprobación en tu navegador no coincide; considera este resumen no verificado", rechecked: "Comprobado de nuevo en tu navegador",
    style: "Estilo", personas: { fan: "Aficionado", analyst: "Analista", caption: "Texto para pantalla" }, figures: "Las cifras",
    possession: "Posesión", shots: "Tiros", passing: "Pases completados", xg: "Goles esperados (datos sintéticos)", tackles: "Mayor número de entradas",
    milestones: "Hitos", title: "Cómo lo comprobamos", matches: "Coincide con el registro de eventos", failed: "No coincide con el registro de eventos",
    notChecked: "Sin comprobar · sin datos", note: "Los aficionados solo lo ven cuando un productor lo aprueba.",
    translation: "Traducción asistida por IA; pendiente de revisión por un hablante nativo.", story: "Leer la historia", feed: "Resúmenes en JSON",
    yourClub: (club, ahead) => (ahead == null ? `Tu club, ${club}, va empatado.` : ahead ? `Tu club, ${club}, va ganando.` : `Tu club, ${club}, va perdiendo.`),
    score: (h, a, at) => `Northbridge ${h}, Riverside ${a}, ${at}`,
  },
  fr: {
    label: "Français", recaps: "Résumés", verified: ["Résumé vérifié", "chaque chiffre contrôlé avec le journal d’événements du match"],
    recheckFailed: "La nouvelle vérification dans votre navigateur ne concorde pas ; considérez ce résumé comme non vérifié", rechecked: "Vérifié à nouveau dans votre navigateur",
    style: "Style", personas: { fan: "Supporter", analyst: "Analyste", caption: "Texte à l’écran" }, figures: "Les chiffres",
    possession: "Possession", shots: "Tirs", passing: "Passes réussies", xg: "Buts attendus (données synthétiques)", tackles: "Le plus de tacles",
    milestones: "Temps forts", title: "Comment nous l’avons vérifié", matches: "Conforme au journal d’événements", failed: "Non conforme au journal d’événements",
    notChecked: "Non vérifié · pas de données", note: "Les supporters ne le voient qu’après validation par un producteur.",
    translation: "Traduction assistée par IA, en attente de relecture par une personne de langue maternelle française.", story: "Lire l’histoire", feed: "Résumés en JSON",
    yourClub: (club, ahead) => (ahead == null ? `Votre club, ${club}, est à égalité.` : ahead ? `Votre club, ${club}, mène.` : `Votre club, ${club}, est mené.`),
    score: (h, a, at) => `Northbridge ${h}, Riverside ${a}, ${at}`,
  },
};
