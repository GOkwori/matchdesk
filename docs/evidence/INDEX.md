# Evidence index

Results are tied to source commits and execution environments. A passing build is not
an approval to deploy, and evidence from one source is not relabelled as another.

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
