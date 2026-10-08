# Standalone production-mode build; this is not the Next development server.
FROM node:22.16.0-bookworm-slim@sha256:048ed02c5fd52e86fda6fbd2f6a76cf0d4492fd6c6fee9e2c463ed5108da0e34 AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# Next rewrites are compiled into the build. This non-secret upstream must match
# the target topology; changing it requires rebuilding this foundation image.
ARG MATCHDESK_API_ORIGIN=http://api:8000
ENV MATCHDESK_API_ORIGIN=$MATCHDESK_API_ORIGIN
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY apps/web/ ./
RUN npm run typecheck && npm run build

FROM node:22.16.0-bookworm-slim@sha256:048ed02c5fd52e86fda6fbd2f6a76cf0d4492fd6c6fee9e2c463ed5108da0e34 AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
# Only traced runtime dependencies and built static files enter the final image.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
