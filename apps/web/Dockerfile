# Standalone production-mode build on the scanned Alpine candidate.
FROM node:22.23.3-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG MATCHDESK_API_ORIGIN=http://api:8000
ENV MATCHDESK_API_ORIGIN=$MATCHDESK_API_ORIGIN
RUN apk upgrade --no-cache
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY apps/web/ ./
RUN npm run typecheck && npm run build

FROM node:22.23.3-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN apk upgrade --no-cache
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
# node server.js does not need npm, Yarn or Corepack. Their removal eliminates
# build tooling from the final image rather than suppressing scanner inventory.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack /opt/yarn-* \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg \
    && node -e "const fs=require('node:fs'); for(const p of ['/usr/local/lib/node_modules/npm','/usr/local/lib/node_modules/corepack','/usr/local/bin/npm','/usr/local/bin/npx','/usr/local/bin/yarn']) { if(fs.existsSync(p)) throw new Error('Unexpected package manager: '+p); } if(fs.existsSync('/opt') && fs.readdirSync('/opt').some(p=>p.startsWith('yarn-'))) throw new Error('Unexpected Yarn distribution');"
USER node
EXPOSE 3000
CMD ["node", "server.js"]
