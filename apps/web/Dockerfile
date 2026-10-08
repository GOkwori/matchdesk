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
# node server.js does not need package managers. Remove their code and launchers
# from the final image only; retain npm in the isolated build stage above.
# This removes unused attack surface rather than hiding inventory from the scanner.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack /opt/yarn-* \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg \
    && node -e "const fs=require('node:fs'); for(const p of ['/usr/local/lib/node_modules/npm','/usr/local/lib/node_modules/corepack','/usr/local/bin/npm','/usr/local/bin/npx','/usr/local/bin/yarn']) { if(fs.existsSync(p)) throw new Error('Unexpected package manager: '+p); } if(fs.readdirSync('/opt').some(p=>p.startsWith('yarn-'))) throw new Error('Unexpected Yarn distribution');"
USER node
EXPOSE 3000
CMD ["node", "server.js"]
