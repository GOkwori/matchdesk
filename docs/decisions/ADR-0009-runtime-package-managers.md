# ADR-0009: Remove unused package managers from final service images

Date: 8 October 2026. Status: implementation candidate; hosted requalification required.

## Context

The first native image scan found vulnerable components not covered by application
lockfiles. The Python base carries pip, and the Node base carries npm and Yarn-related
libraries. Neither service needs to install dependencies after its image is built.

## Decision

Keep dependency installation in the existing build stages. Remove base-image pip
from the final API image and npm, Yarn and Corepack distributions/launchers from the
final web image. The Python copied environment and Next standalone application
libraries remain present. Build-time assertions verify the selected package managers
are absent; runtime/browser tests and full inventories still qualify the final images.

Do not remove package metadata to conceal findings, exclude scanner paths or disable
vulnerability categories. Do not change ordinary user databases or running containers.
The changes occur only in new image builds and do not alter the pinned base identities.

## Consequences and limits

Packages cannot be installed interactively in these application images. Repairs must
produce reviewed new images rather than mutate a deployed container. OS packages,
interpreters, native libraries and PostgreSQL/gosu findings remain independently
reviewable. Removal of unnecessary tools is not a claim that the images are now clean.
A fresh scan and the existing functional checks are mandatory before any merge decision.

See the [first native scan](../evidence/native-images-first-run-20261008.md) and
[image-security method](../testing/runtime-image-security.md).
