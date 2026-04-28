#!/usr/bin/env sh
set -eu

read_secret_file() {
  secret_var="$1"
  secret_file_var="${secret_var}_FILE"
  eval "secret_file=\${${secret_file_var}:-}"
  eval "secret_value=\${${secret_var}:-}"

  if [ -n "$secret_file" ] && [ -n "$secret_value" ]; then
    echo "${secret_var} and ${secret_file_var} are mutually exclusive" >&2
    exit 1
  fi

  if [ -n "$secret_file" ]; then
    if [ ! -f "$secret_file" ]; then
      echo "Secret file not found for ${secret_file_var}: ${secret_file}" >&2
      exit 1
    fi
    secret_value="$(cat "$secret_file")"
    export "${secret_var}=${secret_value}"
  fi
}

load_file_secrets() {
  read_secret_file PRAGMA_DATABASE_PASSWORD
  read_secret_file PRAGMA_JWT_SECRET_KEY
}

prepare_writable_paths() {
  mkdir -p "${PRAGMA_MEDIA_ROOT:-/var/lib/pragma/media}" "${PRAGMA_MODULE_ROOT:-/app/modules}"
}

wait_for_database() {
  timeout_seconds="${PRAGMA_DB_WAIT_TIMEOUT_SECONDS:-90}"
  uv run --no-sync python - "$timeout_seconds" <<'PY'
import sys
import time

import psycopg
from psycopg import Error as PsycopgError

from pragma.config import get_settings

timeout_seconds = float(sys.argv[1])
deadline = time.monotonic() + timeout_seconds
last_error: BaseException | None = None
settings = get_settings()

while time.monotonic() < deadline:
    try:
        with psycopg.connect(settings.database_dsn, connect_timeout=5) as connection:
            connection.execute('SELECT 1').fetchone()
        raise SystemExit(0)
    except PsycopgError as exc:
        last_error = exc
        time.sleep(2)

sys.stderr.write(f'PostgreSQL did not become ready within {timeout_seconds:.0f}s: {last_error}\n')
raise SystemExit(1)
PY
}

run_healthcheck() {
  uv run --no-sync python <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

backend_port = os.environ.get('PRAGMA_BACKEND_PORT', '8000')
default_url = f'http://127.0.0.1:{backend_port}/api/v1/system/ready'
url = os.environ.get('PRAGMA_HEALTHCHECK_URL', default_url)

try:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.loads(response.read().decode('utf-8'))
except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
    sys.stderr.write(f'Readiness probe failed for {url}: {exc}\n')
    raise SystemExit(1)

capabilities = payload.get('capabilities', {})
pg_trgm = capabilities.get('pg_trgm', {})
pgvector = capabilities.get('pgvector', {})
if payload.get('schema_ready') is not True:
    sys.stderr.write('Readiness probe failed: schema_ready is not true\n')
    raise SystemExit(1)
if pg_trgm.get('installed') is not True or pgvector.get('installed') is not True:
    sys.stderr.write('Readiness probe failed: pg_trgm and pgvector must be installed\n')
    raise SystemExit(1)
PY
}

load_file_secrets
prepare_writable_paths

case "${1:-serve}" in
  migrate)
    wait_for_database
    exec uv run --no-sync alembic upgrade head
    ;;
  serve)
    wait_for_database
    if [ "${PRAGMA_RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
      uv run --no-sync alembic upgrade head
    fi
    exec uv run --no-sync uvicorn pragma.app:create_app --factory \
      --host "${PRAGMA_BACKEND_HOST:-0.0.0.0}" \
      --port "${PRAGMA_BACKEND_PORT:-8000}" \
      --proxy-headers
    ;;
  healthcheck)
    run_healthcheck
    ;;
  *)
    exec "$@"
    ;;
esac
