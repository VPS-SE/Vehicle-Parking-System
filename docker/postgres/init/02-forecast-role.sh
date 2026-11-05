#!/bin/sh
# Read-only login for the forecast trainer (SAD 3.6). Django's reports migration grants it
# SELECT on just the lot, slot and reservation columns the trainer reads.
set -e
if [ -z "$FORECAST_DB_PASSWORD" ]; then
    echo "FORECAST_DB_PASSWORD not set; skipping forecast_ro role"
    exit 0
fi
psql -v ON_ERROR_STOP=1 -v pw="$FORECAST_DB_PASSWORD" \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE forecast_ro LOGIN PASSWORD :'pw';
SELECT format('GRANT CONNECT ON DATABASE %I TO forecast_ro', current_database()) \gexec
GRANT USAGE ON SCHEMA public TO forecast_ro;
SQL
