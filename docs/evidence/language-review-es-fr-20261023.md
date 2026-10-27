# Spanish and French language review, 23 October 2026

Associated issue: [#62](https://github.com/GOkwori/matchdesk/issues/62) (audience integrity and multilingual acceptance).

## What was reviewed

The 165 Spanish and 165 French strings a visitor can see in the fan stories, recaps, timed
overlays and replay, each with its English source, from the
[review sheet](../testing/language-review-es-fr.md). The review covered grammar, natural
phrasing, football terms, interface labels, match commentary, consistency and the
verification messages. Numbers, names and times come from verified claims and were left as
they are.

| Language | Rows | Accepted | Corrected | Wrong meaning |
| --- | --- | --- | --- | --- |
| Spanish | 165 | 133 | 32 | 0 |
| French | 165 | 120 | 45 | 0 |
| Total | 330 | 253 | 77 | 0 |

The completed workbook is kept unchanged as
[`language-review-es-fr-20261023.xlsx`](language-review-es-fr-20261023.xlsx)
(SHA-256 `57ce2243c7391ff14e35bd20e6c789bdec394dad4db32034e7fb85686561cdca`).

## Status

- **Certified by the project owner**, who confirmed on 23 October 2026 that the review was
  done and certified.
- The workbook's own sign-off lines read "Spanish (AI-assisted review)" and "French
  (AI-assisted review)", dated 23 October 2026, with the status "AI-assisted editorial review
  only, not a native-speaker sign-off". No reviewer name is recorded, and this record does
  not add one.
- The studio therefore keeps its notice that the translation is AI-assisted and awaits
  review by a native speaker, in the wording the review itself corrected (row 7 of each
  sheet). Removing or rewording that notice is an owner decision.

## What changed in the product

All 77 corrections are applied to the language templates: `story_feed.py`, `recap_feed.py`
and `overlay_feed.py` in the API, and `story-chrome.ts`, `recap-chrome.ts`, `replay.tsx` and
`recap.tsx` in the studio. The main kinds of change:

- Player tallies read "Goles de Okafor: 1" and "Buts d’Okafor : 1" rather than putting the
  name before the noun.
- Spanish scores read "El marcador es 2–1"; French goal overlays read "Le score est de 2–1".
- Recaps say "56 % de la posesión" and "56 % de possession" rather than "of the ball", name
  the tackles leader in a full clause, label pass completion as "Precisión de pase" and
  "Précision des passes", and mark half-time as "DESC" and "MT".
- Shot-speed captions name the statistic ("VELOCIDAD DEL TIRO", "VITESSE DU TIR"); French
  shot speeds are "mesurée à" a speed.
- The caption persona is "Texto para pantalla" and "Texte à l’écran".
- Clock times in running text say "en el minuto 58:17", "à la 59e minute (58:17)" and "au
  temps de jeu 15:00".

Two consistency changes go slightly beyond the rows: French elision now uses the
typographic apostrophe (d’Okafor) wherever it is generated, as most corrections did, and the
French substitution overlay sets its colon off with a space ("Remplacement · Riverside :"),
as corrections 106 and 151 did for cards. The same correction to "Caption", "Most tackles"
and the half-time tag is applied wherever the string appears, not only at the row reviewed.

## How it was checked

- The review rows were regenerated from the corrected templates and compared with the
  workbook: every one of the 77 corrections now appears in the product text (ignoring only
  non-breaking spaces and apostrophe style), and every accepted row is unchanged except the
  French substitution overlay above.
- The verifier reads the English claim text, so no claim, number or verification result
  changed: the OpenAPI contract and its manifest are unchanged, and the generated feeds
  differ only in Spanish and French wording.
- Backend tests (1,655), lint and type checks, the foundation suite, the studio's unit tests
  (212) and the bundle budget all pass. Against a local studio build the browser suite
  passed apart from the workbench specs, which need the API running and are covered by the
  `runtime-browser` CI job; one story test was updated for the new caption label.

## Still open

- The corrected wording is in development once this change merges, and on the hosted demo
  only after the next deployment; it should be read once more on the live site in both
  languages.
- Issue #62 also covers live model output in the nine language and persona views, privacy
  and poisoned-input review, and an independent fluent review of model output. This record
  does not close those.
