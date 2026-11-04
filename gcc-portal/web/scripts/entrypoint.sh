#!/bin/sh
# Container entrypoint: apply db/schema.sql (idempotent, lock-safe), then start the server.
set -e
if [ "${NODE_ENV:-}" = "production" ] && { [ -z "${JWT_SECRET:-}" ] || [ "${JWT_SECRET}" = "dev-only-change-me" ]; }; then
  echo "FATAL: JWT_SECRET is not set (or is the default). Generate one: openssl rand -hex 32" >&2; exit 1
fi
if [ "${SKIP_MIGRATE:-0}" != "1" ]; then node scripts/migrate.mjs; fi
exec "$@"
