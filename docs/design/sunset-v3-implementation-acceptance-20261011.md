# Sunset Studio v3 — screens 01–02 implementation acceptance (11 October 2026)

**Owner decision:** APPROVED as the MatchDesk frontend **implementation baseline** for
all 14 planned screens, retaining the previously approved Sunset Studio visual direction.
This is not a production-release, publishing, cloud-spend, privileged access or
authentication approval.

**Status:** TESTED / QUALIFIED for the isolated, **read-only synthetic demo**
at `/sunset-v3`. The existing `/` foundation event contract workbench remains
available and unchanged. Screens 03–14 have not been implemented in React.

## Exact tested source

- Qualified application + tests: [development `489b7cf4084ce90f4ddc549dd515fdc6eee5b1c5`](https://github.com/GOkwori/matchdesk/commit/489b7cf4084ce90f4ddc549dd515fdc6eee5b1c5).
- Initial isolated v3 route: [`be24ff86b4fa5f7946fe8fd6d8ba822bc66a9dbd`](https://github.com/GOkwori/matchdesk/commit/be24ff86b4fa5f7946fe8fd6d8ba822bc66a9dbd).
- Follow-up `489b7cf`: corrected a misleading Matches navigation target,
  introduced modal keyboard focus containment, Escape-to-close and focus
  restoration, and added Playwright browser regressions.
- Required hosted checks for the exact `489b7cf` source:

| Required workflow | GitHub run | Result |
| --- | --- | --- |
| Foundation CI | [38165967495](https://github.com/GOkwori/matchdesk/actions/runs/38165967495) | PASS |
| Foundation integration | [38165967490](https://github.com/GOkwori/matchdesk/actions/runs/38165967490) | PASS |
| Source security | [38165967516](https://github.com/GOkwori/matchdesk/actions/runs/38165967516) | PASS |
| Dependency audit | [38165967501](https://github.com/GOkwori/matchdesk/actions/runs/38165967501) | PASS |

Foundation integration: the `runtime-browser` and `native-images` jobs each
completed successfully. The actual built Compose web and API topology was used;
the disposable ID3J PostgreSQL negative qualification succeeded.

The Playwright log states **36 passed (17.9 s)**, with **no retries**. Of these,
12 are the four new `sunset-v3.spec.mjs` cases multiplied across the
`desktop` (1440 × 1000), `tablet` (820 × 1180), and `mobile`
(390 × 844) projects; the other 24 exercise the original event workbench.
The v3 responsive test additionally checks 390, 768, 1280 and 1440 pixel
widths, including no horizontal document overflow.

Hosted browser assertions cover:
1. Explicit synthetic replay state, disabled planned sign-in and Detect →
   Verify → Approve presentation.
2. Exact canonical event `E-1421`, significant moment `M-05/E-1366`,
   all seven registered design statistics, disabled Approve and the
   eligible-but-not-approved-or-published draft state.
3. No `/api/` requests during the read-only overview test and no uncaught
   page errors.
4. Custom blocked-approval dialogue with CL-0215/CL-0216 reasons,
   keyboard Tab/Shift+Tab containment, Escape and focus restoration.
5. Light theme selection and the four responsive breakpoint widths.

### Evidence artifact identities

| Archived GitHub artifact | GitHub artifact ID | Provider-reported archive SHA-256 |
| --- | ---: | --- |
| `integration-38165967490-1` | 11712161954 | fd9237d65c6543aade6989404d5d4cab23fb8c2442ae0895f6a80fc828ff2868 |
| `image-security-verdict-38165967490-1` | 11712072034 | 8dc9ba0dbfe0978f3dfbccb31ddd20958e934a011f3a2c38362a126b1b92a8f3 |
| `image-security-38165967490-1` | 11712281393 | 435457af2d1d40ef2a18d314ca9d080ce7706d30348857d31a2a35d7fd58c76f |
| `foundation-web-38165967495-1` | 11712690216 | a3445e7535f3c16519eddfa3e6f40e9bddc909a00647d6e99d5ae707c9d723eb |
| `foundation-python-38165967495-1` | 11712381115 | 013f3967d147c600a595f3fd18b7684453d4eac655fb5657e6e3a31b8402175f |

These are the digests reported by GitHub's artifact API, **not** a separate
local byte-level rehash of downloaded archives.

## Truth, authorization and scope

- The fixture is **Northbridge FC 2–1 Riverside United, 67:12 in a recorded
  synthetic replay**, dated 11 October 2026 with 1,284 synthetic events;
  latest `E-1421` at 67:08. All summary numbers are taken from the locked
  design fixture, not a live fixture feed.
- Visual pitch lines are abstract illustrations and explicitly say
  **No tracking data**. No xG, real-world tracking, video-computer-vision
  assurance or season-wide data is represented.
- CL-0215 remains pending; CL-0216 lacks season evidence and is failed.
  `D-031 v3` is ineligible; `D-029 v2` is eligible as an illustration but
  **not approved and not published**.
- The `/sunset-v3` screen does not provide an authenticated actor, a verified
  publication/approval execution boundary, active sign-in or real customer data.
  All such actions are disabled / planned. A client-side badge or confirmation
  is **never an authorization decision**.

**Retained limitations:** The tests establish observed behaviour of the defined
synthetic scope only. They do **not** independently certify WCAG 2.2 AA
contrast and screen-reader compatibility, manual design fidelity, third-party
browser coverage, production authentication, accessibility of unimplemented
screens, or live sports data. Those require separate acceptance.

## Design asset provenance and archival blocker

- Original Batch 2: 14 exact screenshots and seven static HTML reference
  prototypes already committed in `docs/design/`, with 14 checksums.
- Original Batch 1: the seven approved composite PNG originals
  `image-gen-1(1).png` through `image-gen-7(1).png` have been recovered
  and SHA-256/byte-length verified from the owner's original ZIP; a
  byte-preserving `git diff --binary` patch has also been applied and hashed
  in a disposable local test repository.
- The actual seven original PNG **GitHub blobs are NOT YET COMMITTED**:
  `docs/design/concepts/` remains absent. Do not claim a complete
  21-item in-repository image manifest until a Git-capable operator applies
  the binary patch (or imports the original bytes through a supported route)
  and verifies the protected branch. No substituted image is allowed.

The standalone 14-screen v3 review pack is an approved design specification
and review source **outside the repository**; only screens 01–02 currently
have React implementation. Later screens must be built from vetted components,
without pasting the prototype into production.

## Next controlled implementation wave

1. Finalize and verify exact Byte-for-byte Batch 1 original import under
   `docs/design/concepts/`, update the 21-image manifest, and verify Git blobs.
2. Perform manual visual-fidelity, colour contrast and screen-reader acceptance
   for both themes at the declared viewport widths.
3. Design and implement screens 03 Match Intelligence Command Centre and
   04 Tactical Analysis **read-only** first, using only event-record fields.
4. Run exact-SHA web, browser, Python, integration, source-security and
   dependency qualification on every follow-up implementation; retain blocked
   live provider, producer mutation and publication authority.

**Not authorized:** altering protected `main`, cloud deployment/spending,
customer sign-in, real database migration, editorial approval, broadcasting,
publishing or autonomous tool execution.
