# Official PostgreSQL 16.15 Alpine image resolved to an immutable digest by
# hosted candidate run 37778408263. The runtime is patched during image build.
FROM postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea

# The upstream entrypoint calls /usr/local/bin/gosu only when it starts as root.
# gosu 1.19 is currently built with a Go runtime carrying scanner-reported CVEs.
# Alpine's su-exec package provides the same user-switch contract without that
# embedded Go runtime. Use the package-owned /sbin path explicitly: resolving
# "su-exec" through PATH can select an image-provided compatibility path and made
# the qualification build hang. Keep the pathname expected by the upstream
# entrypoint so the entrypoint itself stays unmodified and easy to compare.
RUN set -eux; \
    apk upgrade --no-cache; \
    apk add --no-cache su-exec; \
    test -x /sbin/su-exec; \
    rm -f /usr/local/bin/gosu; \
    printf '#!/bin/sh\nexec /sbin/su-exec "$@"\n' > /usr/local/bin/gosu; \
    chmod 0755 /usr/local/bin/gosu; \
    test "$(/usr/local/bin/gosu postgres id -un)" = "postgres"
