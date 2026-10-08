# Build the official PostgreSQL filesystem without the upstream gosu binary.
# A deletion in a later layer is insufficient: scanners inspect all layers.
FROM postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea AS upstream
RUN set -eux; \
    apk upgrade --no-cache; \
    apk add --no-cache su-exec; \
    test -x /sbin/su-exec; \
    rm -f /usr/local/bin/gosu; \
    printf '#!/bin/sh\nexec /sbin/su-exec "$@"\n' > /usr/local/bin/gosu; \
    chmod 0755 /usr/local/bin/gosu; \
    test "$(/usr/local/bin/gosu postgres id -un)" = "postgres"

# A scratch final stage flattens the patched filesystem into a new image layer.
# The original upstream layers, including the removed Go executable, are not
# included in the final artifact. Re-declare the upstream runtime metadata.
FROM scratch
COPY --from=upstream / /
ENV LANG=en_US.utf8
ENV PG_MAJOR=16
ENV PGDATA=/var/lib/postgresql/data
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
VOLUME /var/lib/postgresql/data
EXPOSE 5432
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
