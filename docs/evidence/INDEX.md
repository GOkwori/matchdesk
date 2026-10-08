# Evidence index

Results are tied to source commits and execution environments. A passing build is not
an approval to deploy, and evidence from one source is not relabelled as another.

## Current native image qualification

- [Native scans and first runtime remediation](native-image-remediation-20261008.md):
  source `c0e8f5c731e8688ceed37145e0f17c07b768df89`; 109 Python tests, nine runtime
  groups and 24 browser cases passed. Image security remains failed on remaining
  findings and overdue advisory metadata. Unused runtime installers were removed;
  four downloaded evidence archives were source-bound and hash-verified.
- [First native scan and retained failures](native-images-first-run-20261008.md):
  source `e8c76d093c4312c2ce74e1413cc77a36a5303b1c`; real reports exposed the native
  security gap despite passing application lock audits. Formatting failure retained.

No blanket vulnerability exemptions were added. Repository controls are prepared,
not applied, and there has been no foundation merge or production approval.

## Earlier dependency and source-security qualification

- [Patched dependencies, runtime and source-security results](security-remediation-20261008.md):
  source `e2ee20385f2d0da521dd9553eb5f9058d7b4b7e2`; four workflows passed. The report
  contains exact runs, artifact identities, 78 Python tests, nine runtime groups,
  24 Chromium cases and the scope of the passing scans.
- [First ASGI upgrade failure and supported-client correction](asgi-upgrade-first-run-20261008.md)
  preserves the test collection failure without suppressing the warning.
- [Patched ASGI candidates](patched-python-candidates-20261008.json) and
  [supported-client candidates](test-client-candidate-20261008.json) retain resolver provenance.
- [Secret-scan classification](secret-scan-classification-20261008.md) and its
  [exact reviewed digest record](secret-scan-reviewed-digests-20261008.json) preserve
  the initial 13 findings and narrow, recomputed non-secret classifications.

The native gate was not part of these earlier runs; they remain genuine for their
measured scope and do not override the later image findings above.

## Earlier built runtime, browser and security

- [Passing hosted runtime and browser qualification](hosted-integration-20261008.md):
  source `15996afa3219020c44dc1ff8f353e87d93e921e6`, integration run 37755579408;
  nine runtime groups and 24 Chromium cases passed.
- [Dependency advisory failure](dependency-audit-20261008.md): the same source,
  run 37755579414; eight distinct Python advisory IDs across three packages.
  This historical failure is resolved only for the later scanned graph above.
- [First failed integration attempt](integration-first-run-20261008.md): source
  `3b0ae4ae9569ebe97c0bae286720515ea50731ed`, run 37755125431; original assertions
  and failed evidence retained through the authentication/locator corrections.

Reports identify verified artifact digests, measured outcomes and what was not tested.
Screenshots do not establish approved visual baselines. Database probe results do not
establish application persistence, migrations or production disaster recovery.

## Hosted foundation

- [First passing Python and frontend qualification](hosted-foundation-20261008.md):
  source `c6de02db7ef268f9f144c8e108a0cb2e079e3111`, run 37751376812.
- [Initial dependency resolution](dependency-resolution-20261008.md) and its
  [raw manifest](dependency-resolution-20261008.json) preserve the first candidates.
- [Corrected dependency and formatting manifest](dependency-compatibility-20261008.json)
  records exact file identities from resolver run 37751193507.
- [Formatting review](formatting-review-20261008.json) records the checked source and
  unchanged functional AST, import bindings, docstrings and comments.
- [GitHub import and first hosted CI failure](github-import-20261008.md) records the
  exact imported tree and missing-lock failure.

The passing report links the earlier compatibility failure and exact artifact hashes.
Downloaded archives were checked against GitHub's reported SHA-256 digests. Raw hosted
artifacts contain JUnit, coverage and logs; durable report summaries remain in this repo.

## Historical local evidence

Dated subdirectories contain local commands, JUnit/coverage, source hashes and gate
status. `latest.json` identifies the latest **local collection**, not the latest hosted
build. Early attempt logs remain under `initial-attempts`; they are not attributed to
later source. Python 3.13.5 results are supplementary to hosted Python 3.12 qualification.
No cloud deployment, live model execution or production certification is implied.
