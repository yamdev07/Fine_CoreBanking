FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

ARG NEXT_PUBLIC_ACCOUNTING_URL=http://localhost:8000
ARG NEXT_PUBLIC_REPORTING_URL=http://localhost:8001
ENV NEXT_PUBLIC_ACCOUNTING_URL=$NEXT_PUBLIC_ACCOUNTING_URL
ENV NEXT_PUBLIC_REPORTING_URL=$NEXT_PUBLIC_REPORTING_URL

RUN npm run build

# ── Runtime ────────────────────────────────────────────────────────────────────
FROM node:20-alpine
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
