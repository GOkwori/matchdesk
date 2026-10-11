# Sunset Studio - screen and asset register

**Status as at archival commit:** 7 of 14 screen concepts have their original review HTML source checked in. **No PNG renders or Batch 1 raster pages are checked in.** This is not a complete visual-asset handoff.

| Screen | Approved surface | Git source | Original visual files outside Git |
|---|---|---|---|
| 01 | Welcome & Access | Not committed (approved raster concept) | Batch 1 approved image - **pending raw import and filename verification** |
| 02 | Intelligence Overview | Not committed (approved raster concept) | Batch 1 approved image - **pending raw import and filename verification** |
| 03 | Match Intelligence Command Centre | Not committed (approved raster concept) | Batch 1 approved image - **pending raw import and filename verification** |
| 04 | Tactical Analysis | Not committed (approved raster concept) | Batch 1 approved image - **pending raw import and filename verification** |
| 05 | Moments & Timeline | Not committed (approved raster concept) | Batch 1 approved image - **pending raw import and filename verification** |
| 06 | AI Intelligence Workspace | Not committed (approved raster concept) | Batch 1 approved image - **pending raw import and filename verification** |
| 07 | Evidence Verification Explorer | Not committed (approved raster concept) | Batch 1 approved image - **pending raw import and filename verification** |
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
- Batch 1: seven approved raster concept screens in the same project design review. Do not assume generic `image-gen-*.png` filenames map to particular pages without inspecting the exact originals.
- Later review-only engineering candidate: `MatchDesk_UI01_SunsetStudio_ReviewOnly.zip` - **not** an approved design-asset replacement or a production commit.

## Raw-file import requirements

1. Retrieve the original approved image files through an authorised download, owner-provided upload or other supported raw-file export.
2. Verify each image against the approved visual review, associate it with the exact page and viewport, and record file name and SHA-256 in this register.
3. Commit the exact PNGs under `docs/design/screenshots/` and any original Batch 1 raster references under `docs/design/concepts/`; change their register entries from PENDING to COMMITTED only after verifying actual blobs in Git.
4. Re-review any revised designs instead of silently substituting re-rendered screenshots or generated pictures.

No invented binary placeholders or dead in-repository image links are included. The HTML prototypes remain executable **design-only** references, not React production components.
