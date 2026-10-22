# Spanish and French review sheet

Every Spanish and French string a visitor can see, for a native speaker to check. The fan-story copy
was written with AI assistance and can be corrected in `apps/web/src/studio/data.ts`. The audience
versions are part of recorded runs and are shown exactly as the model wrote them; a reviewer can mark
them, but they are not edited in place (a new run replaces them).

For each row record **OK**, **Fix** (with the corrected text) or **Wrong meaning**, and sign at the end.
The studio shows "AI-assisted translation, native-speaker review pending" until this sheet is signed.

| # | Lang | Where | Text | Verdict | Correction |
| --- | --- | --- | --- | --- | --- |
| 1 | es | Fan story · label | Español | | |
| 2 | es | Fan story · title | Cómo lo comprobamos | | |
| 3 | es | Fan story · headline | Gol de Northbridge FC en el 58′ | | |
| 4 | es | Fan story · body | Okafor remata de cabeza un córner desde la derecha, su segundo gol del partido, y Northbridge vuelve a ponerse por delante. | | |
| 5 | es | Fan story · checks | Autor del gol / Córner y gol 14 s después / Posición de los defensas | | |
| 6 | es | Fan story · matches | Coincide con el registro de eventos | | |
| 7 | es | Fan story · failed | No coincide con el registro de eventos | | |
| 8 | es | Fan story · notChecked | Sin comprobar · sin datos | | |
| 9 | es | Fan story · note | Los aficionados solo lo ven cuando un productor lo aprueba. | | |
| 10 | es | Fan story · caption | ① Córner desde la derecha · ② Cabezazo de Okafor, 14 segundos después | | |
| 11 | es | Fan story · translation | Traducción asistida por IA, pendiente de revisión por un hablante nativo. | | |
| 12 | es | Fan story · verified | Momento verificado / comprobado con el registro de eventos del partido | | |
| 13 | es | Fan story · score | Northbridge 2, Riverside 1 en el 58:17 | | |
| 14 | es | Fan story · diagram | Diagrama: córner desde la derecha en el 58:03, gol de cabeza dentro del área pequeña en el 58:17 | | |
| 15 | fr | Fan story · label | Français | | |
| 16 | fr | Fan story · title | Comment nous l’avons vérifié | | |
| 17 | fr | Fan story · headline | But de Northbridge FC à la 58e | | |
| 18 | fr | Fan story · body | Okafor reprend de la tête un corner venu de la droite, son deuxième but du match, et Northbridge repasse devant. | | |
| 19 | fr | Fan story · checks | Buteur / Corner, puis but 14 s plus tard / Position des défenseurs | | |
| 20 | fr | Fan story · matches | Conforme au journal d’événements | | |
| 21 | fr | Fan story · failed | Non conforme au journal d’événements | | |
| 22 | fr | Fan story · notChecked | Non vérifié · pas de données | | |
| 23 | fr | Fan story · note | Les supporters ne le voient qu’après validation par un producteur. | | |
| 24 | fr | Fan story · caption | ① Corner côté droit · ② Tête d’Okafor, 14 secondes plus tard | | |
| 25 | fr | Fan story · translation | Traduction assistée par IA, relecture par un locuteur natif en attente. | | |
| 26 | fr | Fan story · verified | Moment vérifié / contrôlé avec le journal d’événements du match | | |
| 27 | fr | Fan story · score | Northbridge 2, Riverside 1 à 58:17 | | |
| 28 | fr | Fan story · diagram | Schéma : corner côté droit à 58:03, but de la tête dans les six mètres à 58:17 | | |
| 29 | es | Live run (21 Oct) · analyst | A las 58:17, Okafor anotó un gol clave para Northbridge, influyendo mucho en el resultado del juego. | | |
| 30 | es | Live run (21 Oct) · casual_fan | ¡Increíble! Okafor anotó para Northbridge a las 58:17. ¡Qué actuación! | | |
| 31 | es | Live run (21 Oct) · broadcast_caption | 58:17: Gol anotado por Okafor para Northbridge. ¡Momento clave del juego! | | |
| 32 | fr | Live run (21 Oct) · analyst | À 58:17, Okafor a marqué un but important pour Northbridge, influençant significativement le résultat du jeu. | | |
| 33 | fr | Live run (21 Oct) · casual_fan | Incroyable ! Okafor a marqué pour Northbridge à 58:17 ! Quelle performance ! | | |
| 34 | fr | Live run (21 Oct) · broadcast_caption | 58:17 : But marqué par Okafor pour Northbridge. Un moment clé du match ! | | |
| 35 | es | Rehearsal · analyst | Okafor ha marcado los dos goles del Northbridge; su cabezazo llegó 14 segundos después de un córner. | | |
| 36 | es | Rehearsal · casual_fan | ¡Okafor otra vez! Un cabezazo 14 segundos después de un córner devuelve la ventaja al Northbridge. | | |
| 37 | es | Rehearsal · broadcast_caption | Okafor · cabezazo 14 s tras córner | | |
| 38 | fr | Rehearsal · analyst | Okafor a marqué les deux buts de Northbridge ; sa tête est arrivée 14 secondes après un corner. | | |
| 39 | fr | Rehearsal · casual_fan | Encore Okafor ! Une tête 14 secondes après un corner, et Northbridge repasse devant. | | |
| 40 | fr | Rehearsal · broadcast_caption | Okafor · tête 14 s après corner | | |

Reviewer (Spanish): ______________ Date: ________

Reviewer (French): ______________ Date: ________

Once signed, remove the `translation` note for that language in `storyCopy` and record the review in
[the traceability matrix](../competition/traceability-matrix.md) (R7).
