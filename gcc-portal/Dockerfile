# syntax=docker/dockerfile:1
# Two runtime targets from one file (build context = the gcc-portal folder). `web` is the LAST stage, so a plain
# `docker build .` (what most PaaS do) builds the web app. The worker has its own copy for platforms without build targets:
#   docker build --target web    -t gcc-web .        (same as: docker build -t gcc-web .)
#   docker build --target worker -t gcc-worker .     (same as: docker build -f Dockerfile.worker -t gcc-worker .)
# Keep Dockerfile.worker identical to the worker stage below.

# ---------- web: dependencies ----------
FROM node:20-alpine AS web-deps
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---------- web: build ----------
FROM node:20-alpine AS web-build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_STANDALONE=1 NODE_ENV=production
COPY --from=web-deps /app/node_modules ./node_modules
COPY web/ ./
# No database or secrets are needed at build time; pages render on request.
RUN npx next build

# ---------- worker: python jobs + scheduler ----------
FROM python:3.12-slim AS worker
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Kolkata SCHEDULER_TZ=Asia/Kolkata
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY workers/requirements.txt workers/requirements.txt
RUN pip install --no-cache-dir -r workers/requirements.txt
COPY workers workers
COPY db db
RUN useradd -r -u 10001 app && chown -R app /app && chmod +x workers/run_weekly.sh
USER app
WORKDIR /app/workers
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD python -c "import os,psycopg;psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=5).close()" || exit 1
# scheduler.py reads ./crontab (IST): news daily 06:00, deep refresh Sunday 02:30, digest Monday 07:00
CMD ["python", "scheduler.py"]

# ---------- web: runtime ----------
FROM node:20-alpine AS web
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S app && adduser -S app -G app
COPY --from=web-build --chown=app:app /app/.next/standalone ./
COPY --from=web-build --chown=app:app /app/.next/static ./.next/static
COPY --chown=app:app web/scripts ./scripts
COPY --chown=app:app db ./db
RUN chmod +x scripts/entrypoint.sh
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/health >/dev/null || exit 1
# entrypoint: refuse a default JWT_SECRET, apply db/schema.sql (idempotent), then exec the command
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["node", "server.js"]
