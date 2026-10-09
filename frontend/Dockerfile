# Next.js dashboard image (Roadmap Phase 10).
#
# NOTE: Docker was not available on the dev machine when this file was written —
# NOT built or run locally (see docs/PHASE_REPORTS/PHASE_10.md).

FROM node:22-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000
ENV PORT=3000
CMD ["npm", "run", "start"]
