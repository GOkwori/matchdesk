# Sunset Studio - screen and asset register

**Status as at archival commit:** 7 of 14 screen concepts have their original review HTML source checked in. **No PNG renders or Batch 1 raster pages are checked in.** This is not a complete visual-asset handoff.

| Screen | Approved surface | Git source | Original visual files outside Git |
|---|---|---|---|
| 01 | Welcome & Access | Not committed (approved raster concept) | `image-gen-1(1).png` - **identified visually; pending raw import** |
| 02 | Intelligence Overview | Not committed (approved raster concept) | `image-gen-2(1).png` - **identified visually; pending raw import** |
| 03 | Match Intelligence Command Centre | Not committed (approved raster concept) | `image-gen-3(1).png` - **identified visually; pending raw import** |
| 04 | Tactical Analysis | Not committed (approved raster concept) | `image-gen-4(1).png` - **identified visually; pending raw import** |
| 05 | Moments & Timeline | Not committed (approved raster concept) | `image-gen-5(1).png` - **identified visually; pending raw import** |
| 06 | AI Intelligence Workspace | Not committed (approved raster concept) | `image-gen-6(1).png` - **identified visually; pending raw import** |
| 07 | Evidence Verification Explorer | Not committed (approved raster concept) | `image-gen-7(1).png` - **identified visually; pending raw import** |
| 08 | Producer Review Queue | [HTML prototype](prototypes/08-producer-review-queue.html) (committed) | `08-producer-review-queue-desktop.png` / `08-producer-review-queue-mobile.png` - **pending raw import** |
| 09 | Story & Commentary Composer | [HTML prototype](prototypes/09-story-commentary-composer.html) (committed) | `09-story-commentary-composer-desktop.png` / `09-story-commentary-composer-mobile.png` - **pending raw import** |
| 10 | Review & Publication Journey (Future State) | [HTML prototype](prototypes/10-review-publication-future-state.html) (committed) | `10-review-publication-future-state-desktop.png` / `10-review-publication-future-state-mobile.png` - **pending raw import** |
| 11 | Audience Experience | [HTML prototype](prototypes/11-audience-experience.html) (committed) | `11-audience-experience-desktop.png` / `11-audience-experience-mobile.png` - **pending raw import** |
| 12 | Activity, Audit & Settings | [HTML prototype](prototypes/12-activity-audit-settings.html) (committed) | `12-activity-audit-settings-desktop.png` / `12-activity-audit-settings-mobile.png` - **pending raw import** |
| 13 | Notification & Dialogue Library | [HTML prototype](prototypes/13-notification-dialogue-library.html) (committed) | `13-notification-dialogue-library-desktop.png` / `13-notification-dialogue-library-mobile.png` - **pending raw import** |
| 14 | Defensive States | [HTML prototype](prototypes/14-defensive-states.html) (committed) | `14-defensive-states-desktop.png` / `14-defensive-states-mobile.png` - **pending raw import** |

## Source locations to recover

- Project: ChatGPT **Microsoft Competition** Library, 11 October 2026.
- Batch 2 pack: `MatchDesk_SunsetStudio_Batch2_ReviewPack.zip` (7 HTML files plus 14 desktop/mobile PNGs).
- Batch 1: the seven confirmed Sunset Studio desktop-and-mobile concept boards are named `image-gen-1(1).png` through `image-gen-7(1).png` (literal parentheses included). They have been visually inspected and mapped to screens 01-07. These are composite visual concepts, **not** individually exportable desktop/mobile screenshots and **not** production-valid match data. The earlier `image-gen-1.png` is a separate *Final Design Review* board and is not screen 01. The `image-gen-2.png` through `image-gen-7.png` series has not been substituted for the approved individual source files.
- Later review-only engineering candidate: `MatchDesk_UI01_SunsetStudio_ReviewOnly.zip` - **not** an approved design-asset replacement or a production commit.


## Visually verified Batch 1 filename-to-page mapping

Original files remain in the Microsoft Competition Library. File sizes below were reported by the Library and assist later source matching; they are **not** cryptographic integrity checks. SHA-256 is pending until the exact original binary files can be exported and hashed.

| Screen | Approved original PNG | Recorded source bytes | Visual identification |
|---|---|---:|---|
| 01 | `image-gen-1(1).png` | 2,011,072 | Welcome & Access (desktop and phone on one board) |
| 02 | `image-gen-2(1).png` | 1,914,676 | Intelligence Overview |
| 03 | `image-gen-3(1).png` | 2,024,796 | Match Intelligence Command Centre |
| 04 | `image-gen-4(1).png` | 1,969,792 | Tactical Analysis |
| 05 | `image-gen-5(1).png` | 2,084,190 | Moments & Timeline |
| 06 | `image-gen-6(1).png` | 2,195,314 | AI Intelligence Workspace |
| 07 | `image-gen-7(1).png` | 2,024,214 | Evidence Verification Explorer |

**Important:** Raster concepts may depict unsupported video, tracking, claim states, timelines or percentages. They are approved as visual direction only. The [implementation guardrails](implementation-guardrails.md) and actual verified product contracts supersede illustrative visual content.

## Batch 2 exact screenshot filenames

These are the 14 **original** PNG exports in `MatchDesk_SunsetStudio_Batch2_ReviewPack.zip`; all remain pending exact-byte import.

| Screen | Desktop PNG | Mobile PNG |
|---|---|---|
| 08 | `08-producer-review-queue-desktop.png` | `08-producer-review-queue-mobile.png` |
| 09 | `09-story-commentary-composer-desktop.png` | `09-story-commentary-composer-mobile.png` |
| 10 | `10-review-publication-future-state-desktop.png` | `10-review-publication-future-state-mobile.png` |
| 11 | `11-audience-experience-desktop.png` | `11-audience-experience-mobile.png` |
| 12 | `12-activity-audit-settings-desktop.png` | `12-activity-audit-settings-mobile.png` |
| 13 | `13-notification-dialogue-library-desktop.png` | `13-notification-dialogue-library-mobile.png` |
| 14 | `14-defensive-states-desktop.png` | `14-defensive-states-mobile.png` |

## Raw-file import requirements

1. Retrieve the original approved image files through an authorised download, owner-provided upload or other supported raw-file export.
2. Verify each image against the approved visual review, associate it with the exact page and viewport, and record file name and SHA-256 in this register.
3. Commit the exact PNGs under `docs/design/screenshots/` and any original Batch 1 raster references under `docs/design/concepts/`; change their register entries from PENDING to COMMITTED only after verifying actual blobs in Git.
4. Re-review any revised designs instead of silently substituting re-rendered screenshots or generated pictures.

No invented binary placeholders or dead in-repository image links are included. The HTML prototypes remain executable **design-only** references, not React production components.
