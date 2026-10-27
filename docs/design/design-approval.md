# Sunset Studio - design approval and provenance

- **Design:** Sunset Studio, Colour Option F
- **Date:** 11 October 2026
- **Decision:** APPROVED as the visual design and navigation direction for the 14-screen MatchDesk front end
- **Owner approval scope:** aesthetic direction, page concepts, responsive patterns and custom feedback/dialogue approach
- **Implementation status at approval:** no implementation commit or deployment authorised by the sign-off itself
- **Current archive status:** partial; see [asset register](asset-register.md)

The owner approved the design in the 11 October 2026 MatchDesk design discussion and subsequently explicitly requested that the mock-ups be committed to repository design documentation. This record documents that instruction; it does not claim independent formal UX testing, a CI pass or a production-release approval.

The original source artefacts were produced outside this repository in the Microsoft Competition project. The Batch 2 review pack is named `MatchDesk_SunsetStudio_Batch2_ReviewPack.zip`; its seven interactive HTML design references were previously archived. On 11 October 2026, the user attached the original Batch 2 ZIP and its 14 desktop/mobile PNG exports were successfully validated and imported byte-for-byte. The source ZIP SHA-256 is `b99b29667d7f088536b041ed50a3b3244612826599543f5da2a973772a8fe959`; each imported image's SHA-256 is recorded in [the checksum manifest](asset-checksums.json). The seven approved Batch 1 raster concept boards remain outside Git because their source image bytes are still unavailable to this session; see [asset register](asset-register.md).

Do not replace the approved Sunset Studio direction with earlier Midnight Broadcast, Daylight Studio or Graphite Arena concepts. Existing documentation describing the foundation's cyan/navy workbench is historical and not a substitute for this newer visual approval.

This is a **design decision**, not evidence of:
- deployed or even compiled production UI;
- accessible contrast, keyboard or screen-reader compliance;
- operational sign-in or user permissions;
- verified live football data, a real-time stream or professional tracking;
- approval or publication endpoints, permissions or delivery.

The applicable engineering, security, evidence, change-control and release gates still apply.

## Subsequent enhancement approval — Sunset Studio v3

On 11 October 2026, the owner separately approved the **Sunset Studio v3** enhancement as the MatchDesk **frontend implementation baseline** for 14 screens. This supersedes the historical visual implementation direction while preserving the exact earlier approved source-image archive. It is not authorization for live data, production sign-in, publishing or protected-branch promotion.

Screens 01 and 02 are implemented in the isolated Next.js `/sunset-v3` synthetic route. Their exact-source CI/browser evidence is [the v3 acceptance record](sunset-v3-implementation-acceptance-20261011.md). The remaining screens are design requirements only. Batch 1 originals are SHA-256 verified outside Git but cannot be described as committed until their exact PNG blobs and 21-entry manifest are in the repo.
