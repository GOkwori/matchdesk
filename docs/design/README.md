# MatchDesk - approved front-end design references

**Approved visual direction:** Sunset Studio (Colour Option F), 11 October 2026.
**Scope:** 14 responsive screen designs (desktop and mobile review).
**Archive state:** PARTIAL OVERALL - Batch 2 is fully archived (seven design HTML prototypes and 14 byte-verified original desktop/mobile PNGs). Seven approved Batch 1 concept PNGs for screens 01-07 remain pending exact-byte import.

This is the authoritative *approved visual direction* for future MatchDesk front-end work. Approval of the mock-ups is not approval to enable production login, producer mutations, publishing, or other privileged features. The present API and security boundaries remain authoritative.

## Sunset Studio v3 implementation baseline — 11 October 2026

The owner explicitly approved the Sunset Studio v3 enhancement as the **14-screen frontend implementation baseline**. This supersedes the earlier approval **for future implementation guidance**, not historical asset provenance: existing approved raster originals remain immutable and cannot be silently replaced.

[Exact-source v3 screens 01–02 browser and security acceptance](sunset-v3-implementation-acceptance-20261011.md) confirms 4/4 PASS on `489b7cf4084ce90f4ddc549dd515fdc6eee5b1c5` (36 Playwright tests across desktop/tablet/mobile; includes 12 new v3 checks). Only the `/sunset-v3` synthetic read-only route is implemented. No real authentication, editor approval, publishing or cloud release is enabled.

The original Batch 1 concept PNGs have been byte-verified outside Git and a binary import patch has passed offline roundtrip; **the seven actual source images are still missing from this Git repository**. Overall original-image archive status is **PARTIAL** until they and the 21-image manifest are committed. Treat the v3 review pack as approved design requirements, not as evidence that screens 03–14 have React implementations.

## Start here

- [Approval and design provenance](design-approval.md)
- [Fourteen-screen asset register](asset-register.md), including missing raw assets
- [Implementation and truthfulness guardrails](implementation-guardrails.md)
- [Producer UX architecture](../solution-design/09-ux.md) - existing foundation history is retained

## Available review prototypes

- [08 Producer Review Queue](prototypes/08-producer-review-queue.html)
- [09 Story & Commentary Composer](prototypes/09-story-commentary-composer.html)
- [10 Review & Publication Journey (Future State)](prototypes/10-review-publication-future-state.html)
- [11 Audience Experience](prototypes/11-audience-experience.html)
- [12 Activity, Audit & Settings](prototypes/12-activity-audit-settings.html)
- [13 Notification & Dialogue Library](prototypes/13-notification-dialogue-library.html)
- [14 Defensive States](prototypes/14-defensive-states.html)

Each prototype is a self-contained concept with inline CSS, SVG and local demo interactions. Open a trusted local copy to review; do not deploy these HTML files directly to the Next.js application. Interactions, fixture values and badges are illustrative and must not be mistaken for verified backend state.

## Original approved Batch 2 PNGs

The exact 14 desktop/mobile PNG files from the attached approved review pack are now archived under [screenshots](screenshots/) with original bytes intact. [SHA-256 manifest](asset-checksums.json) records dimensions, exact byte counts and digests.

| Screen | Desktop original | Mobile original |
|---|---|---|
| 08 Producer Review Queue | [1440px](screenshots/08-producer-review-queue-desktop.png) | [390px](screenshots/08-producer-review-queue-mobile.png) |
| 09 Story & Commentary Composer | [1440px](screenshots/09-story-commentary-composer-desktop.png) | [390px](screenshots/09-story-commentary-composer-mobile.png) |
| 10 Review & Publication Journey | [1440px](screenshots/10-review-publication-future-state-desktop.png) | [390px](screenshots/10-review-publication-future-state-mobile.png) |
| 11 Audience Experience | [1440px](screenshots/11-audience-experience-desktop.png) | [390px](screenshots/11-audience-experience-mobile.png) |
| 12 Activity, Audit & Settings | [1440px](screenshots/12-activity-audit-settings-desktop.png) | [390px](screenshots/12-activity-audit-settings-mobile.png) |
| 13 Notification & Dialogue Library | [1440px](screenshots/13-notification-dialogue-library-desktop.png) | [390px](screenshots/13-notification-dialogue-library-mobile.png) |
| 14 Defensive States | [1440px](screenshots/14-defensive-states-desktop.png) | [390px](screenshots/14-defensive-states-mobile.png) |

Original source pack: `MatchDesk_SunsetStudio_Batch2_ReviewPack.zip`; SHA-256: `b99b29667d7f088536b041ed50a3b3244612826599543f5da2a973772a8fe959`. The archived screen designs remain visual references only, not certified functionality or verified live match data. Batch 1 source files remain uncommitted until supplied.

## Preserved design language

- Dark premium sports-media UI: background `#10151c`, panel `#19222d`, raised surface `#23303c`, primary sunset accent `#ff9159`, warm highlight `#ffc084`, light text `#f5f7fa` (observed in the archived Batch 2 source).
- Responsive navigation and layouts for mobile, tablet, laptop and desktop; semantic state icons and text, clear focus indicators, accessible controls and a light/dark design treatment.
- Custom in-app **success, information, warning and error** banners, plus accessible custom confirmation dialogues. Never use `window.alert`, `window.confirm`, `window.prompt`, the browser Notification API or operating-system notifications.
- Explicit differentiation of synthetic replay, deterministic verified evidence, AI interpretation, pending/failed checks, human approval eligibility and confirmed publication.
- Human control: AI proposes; verified server-side policy and the authorised human decide; approval is not publication.

**Important:** Visual concepts contain known design-data and accessibility discrepancies; [implementation-guardrails.md](implementation-guardrails.md) is required reading before implementation. The screenshot-only sources are NOT silently replaced with generated alternatives.

## Batch 1 original-file archival policy

**Owner decision (11 October 2026): Option B — strict per-screen originals.** The seven previously supplied paired review-board images are references only and **must not** be cropped, relabelled or substituted as the seven approved Batch 1 originals. The archive remains PARTIAL until the exact `image-gen-1(1).png` through `image-gen-7(1).png` files are imported byte-for-byte with SHA-256 proof. See [the Batch 1 decision and import gate](asset-register.md#batch-1-archive-decision--option-b-11-october-2026).

## Importing the original approved PNGs

Use the repository's [approved-asset importer](tools/import_approved_assets.py) only with the exact original assets. It accepts the original `MatchDesk_SunsetStudio_Batch2_ReviewPack.zip` and the folder containing `image-gen-1(1).png` to `image-gen-7(1).png`.

From the **repository root**:

```bash
python docs/design/tools/import_approved_assets.py --batch2-zip /path/to/MatchDesk_SunsetStudio_Batch2_ReviewPack.zip --batch1-dir /path/to/approved-batch1
```

The default is **dry-run**; inspect the resulting file names and SHA-256 hashes. Add `--write` to write the verified original PNGs under `docs/design/screenshots/` and `docs/design/concepts/` and create `docs/design/asset-checksums.json`. Existing differing files are never overwritten. Batch 1 and Batch 2 may be imported separately; one complete batch must be supplied for each import. No files are staged or committed by this script. Commit exactly the reviewed asset paths only after checking the output and updating the [asset register](asset-register.md).

Run the importer regression suite locally before use:

```bash
python -m unittest discover -s docs/design/tools -p 'test_*.py' -v
```

The importer uses only Python's standard library. Local synthetic tests exercise archive-path safety, strict filenames, PNG integrity, missing sources, conflicts, repeat imports and checksum tampering. The 14 **Batch 2 originals** have additionally passed actual source-file inspection and exact Git blob identity checks. The seven **Batch 1 originals** remain unavailable for byte validation. None of these checks replaces application CI, human design review or the production security gates.
