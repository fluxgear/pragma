#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.yml"
SECRETS_COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.secrets.yml"
ENV_FILE="${1:-${REPO_ROOT}/docker/prod.env.example}"
PROJECT_NAME="${PRAGMA_VALIDATE_PROJECT_NAME:-pragma-m14-validate}"
SMOKE="${PRAGMA_VALIDATE_SMOKE:-0}"
USE_SECRETS_COMPOSE=0
MIN_RAW_SECRET_LENGTH=32
DATABASE_PASSWORD_SECRET_DEFAULT_SOURCE="./secrets/pragma_database_password"
JWT_SECRET_KEY_SECRET_DEFAULT_SOURCE="./secrets/pragma_jwt_secret_key"
SETUP_SECRET_SECRET_DEFAULT_SOURCE="./secrets/pragma_setup_secret"

if [ ! -f "$ENV_FILE" ]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

run() {
  echo "+ $*"
  "$@"
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required for compose/nginx validation" >&2
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose v2 is required" >&2
    exit 1
  fi
}

load_env_file() {
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
}

load_env_for_smoke() {
  load_env_file
}

validate_raw_secret_value() {
  value_var="$1"
  secret_value="$2"

  case "$secret_value" in
    replace-with-*|REPLACE-WITH-*|change-me|CHANGE-ME|changeme|CHANGEME)
      echo "${value_var} must not use a placeholder value" >&2
      exit 1
      ;;
  esac

  if [ "${#secret_value}" -lt "$MIN_RAW_SECRET_LENGTH" ]; then
    echo "${value_var} must be at least ${MIN_RAW_SECRET_LENGTH} characters for production" >&2
    exit 1
  fi
}

require_secret_value_or_file() {
  value_var="$1"
  file_var="$2"
  eval "secret_value=\${${value_var}:-}"
  eval "secret_file=\${${file_var}:-}"

  if [ -n "$secret_value" ] && [ -n "$secret_file" ]; then
    echo "Set only one of ${value_var} or ${file_var}" >&2
    exit 1
  fi
  if [ -z "$secret_value" ] && [ -z "$secret_file" ]; then
    echo "Set either ${value_var} or ${file_var}" >&2
    exit 1
  fi
  if [ -n "$secret_value" ]; then
    validate_raw_secret_value "$value_var" "$secret_value"
  fi
}

resolve_host_secret_path() {
  source_file="$1"

  case "$source_file" in
    /*) printf '%s\n' "$source_file" ;;
    ./*) printf '%s/%s\n' "$SCRIPT_DIR" "${source_file#./}" ;;
    *) printf '%s/%s\n' "$SCRIPT_DIR" "$source_file" ;;
  esac
}

validate_host_secret_source_file() {
  source_label="$1"
  source_file="$2"
  resolved_source_file="$(resolve_host_secret_path "$source_file")"

  if [ ! -f "$resolved_source_file" ]; then
    echo "Secret source file not found for ${source_label}: ${source_file} (${resolved_source_file})" >&2
    exit 1
  fi
  if [ ! -r "$resolved_source_file" ]; then
    echo "Secret source file is not readable for ${source_label}: ${source_file} (${resolved_source_file})" >&2
    exit 1
  fi

  secret_file_value="$(sed -e '1s/^[[:space:]]*//' -e '$s/[[:space:]]*$//' "$resolved_source_file")"
  validate_raw_secret_value "$source_label" "$secret_file_value"
}

validate_secret_source_file() {
  source_var="$1"
  eval "source_file=\${${source_var}:-}"

  if [ -n "$source_file" ]; then
    validate_host_secret_source_file "$source_var" "$source_file"
  fi
}

validate_effective_secret_source_file() {
  file_var="$1"
  source_var="$2"
  default_source_file="$3"
  eval "secret_file=\${${file_var}:-}"
  eval "source_file=\${${source_var}:-}"

  if [ -z "$secret_file" ]; then
    return 0
  fi
  if [ -n "$source_file" ]; then
    validate_host_secret_source_file "$source_var" "$source_file"
  else
    validate_host_secret_source_file "${source_var} default" "$default_source_file"
  fi
}

uses_file_secret() {
  [ -n "${PRAGMA_DATABASE_PASSWORD_FILE:-}" ] || \
    [ -n "${PRAGMA_JWT_SECRET_KEY_FILE:-}" ] || \
    [ -n "${PRAGMA_SETUP_SECRET_FILE:-}" ]
}

configure_compose_override() {
  if uses_file_secret; then
    if [ ! -f "$SECRETS_COMPOSE_FILE" ]; then
      echo "Secrets compose override not found: $SECRETS_COMPOSE_FILE" >&2
      exit 1
    fi
    USE_SECRETS_COMPOSE=1
  fi
}

run_docker_compose() {
  if [ "$USE_SECRETS_COMPOSE" = "1" ]; then
    run docker compose -f "$COMPOSE_FILE" -f "$SECRETS_COMPOSE_FILE" "$@"
  else
    run docker compose -f "$COMPOSE_FILE" "$@"
  fi
}

docker_compose() {
  if [ "$USE_SECRETS_COMPOSE" = "1" ]; then
    docker compose -f "$COMPOSE_FILE" -f "$SECRETS_COMPOSE_FILE" "$@"
  else
    docker compose -f "$COMPOSE_FILE" "$@"
  fi
}

validate_secret_configuration() {
  load_env_file
  require_secret_value_or_file PRAGMA_DATABASE_PASSWORD PRAGMA_DATABASE_PASSWORD_FILE
  require_secret_value_or_file PRAGMA_JWT_SECRET_KEY PRAGMA_JWT_SECRET_KEY_FILE
  require_secret_value_or_file PRAGMA_SETUP_SECRET PRAGMA_SETUP_SECRET_FILE
  validate_secret_source_file PRAGMA_DATABASE_PASSWORD_SECRET_SOURCE
  validate_secret_source_file PRAGMA_JWT_SECRET_KEY_SECRET_SOURCE
  validate_secret_source_file PRAGMA_SETUP_SECRET_SECRET_SOURCE
  validate_effective_secret_source_file PRAGMA_DATABASE_PASSWORD_FILE PRAGMA_DATABASE_PASSWORD_SECRET_SOURCE "$DATABASE_PASSWORD_SECRET_DEFAULT_SOURCE"
  validate_effective_secret_source_file PRAGMA_JWT_SECRET_KEY_FILE PRAGMA_JWT_SECRET_KEY_SECRET_SOURCE "$JWT_SECRET_KEY_SECRET_DEFAULT_SOURCE"
  validate_effective_secret_source_file PRAGMA_SETUP_SECRET_FILE PRAGMA_SETUP_SECRET_SECRET_SOURCE "$SETUP_SECRET_SECRET_DEFAULT_SOURCE"
  configure_compose_override
}

run_static_checks() {
  run sh -n "${REPO_ROOT}/docker/backend/entrypoint.sh"
  run sh -n "${REPO_ROOT}/docker/validate-production.sh"

  if command -v docker >/dev/null 2>&1; then
    run docker run --rm \
      -e PRAGMA_BACKEND_UPSTREAM=127.0.0.1:8000 \
      -e PRAGMA_PROXY_CLIENT_MAX_BODY_SIZE=25m \
      -e PRAGMA_PROXY_LISTEN_PORT=8080 \
      -e PRAGMA_PROXY_WEBSOCKET_READ_TIMEOUT=1h \
      -e PRAGMA_PROXY_WEBSOCKET_SEND_TIMEOUT=1h \
      -e PRAGMA_SERVER_NAME=_ \
      -v "${REPO_ROOT}/docker/proxy/templates/default.conf.template:/etc/nginx/templates/default.conf.template:ro" \
      nginx:1.29-alpine nginx -t
  else
    echo "Skipping nginx syntax check: docker is not available" >&2
  fi
}

run_compose_config() {
  require_docker
  run_docker_compose --env-file "$ENV_FILE" config >/dev/null
}

wait_for_url() {
  url="$1"
  seconds="$2"
  deadline=$((seconds * 2))
  count=0
  while [ "$count" -lt "$deadline" ]; do
    if command -v curl >/dev/null 2>&1; then
      if curl -fsS "$url" >/dev/null 2>&1; then
        return 0
      fi
    elif command -v wget >/dev/null 2>&1; then
      if wget -qO- "$url" >/dev/null 2>&1; then
        return 0
      fi
    else
      echo "curl or wget is required for smoke URL checks" >&2
      return 1
    fi
    count=$((count + 1))
    sleep 0.5
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

run_smoke_checks() {
  require_docker
  load_env_for_smoke

  run_docker_compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" build
  run_docker_compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" up -d db
  run_docker_compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" up --exit-code-from migrate migrate
  run_docker_compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" up -d backend proxy

  extension_status="$(docker_compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" exec -T db \
    psql -U "$PRAGMA_DATABASE_USER" -d "$PRAGMA_DATABASE_NAME" -v ON_ERROR_STOP=1 -tA -c \
    "SELECT current_setting('server_version_num')::integer >= 180000 AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')")"
  echo "PostgreSQL 18+/vector/pg_trgm check: $extension_status"
  if [ "$extension_status" != "t" ]; then
    echo "PostgreSQL 18, vector, and pg_trgm must all be available and installed" >&2
    exit 1
  fi

  proxy_host="${PRAGMA_PROXY_PUBLISHED_HOST:-127.0.0.1}"
  if [ "$proxy_host" = "0.0.0.0" ]; then
    proxy_host="127.0.0.1"
  fi

  wait_for_url "http://${proxy_host}:${PRAGMA_PROXY_PUBLISHED_PORT}/healthz" 60
  wait_for_url "http://${proxy_host}:${PRAGMA_PROXY_PUBLISHED_PORT}/readyz" 60
  wait_for_url "http://${proxy_host}:${PRAGMA_PROXY_PUBLISHED_PORT}/api/v1/system/health" 60
  wait_for_url "http://${proxy_host}:${PRAGMA_PROXY_PUBLISHED_PORT}/login" 60
  wait_for_url "http://${proxy_host}:${PRAGMA_PROXY_PUBLISHED_PORT}/app" 60
}

cleanup_smoke_stack() {
  if [ "$SMOKE" = "1" ] && command -v docker >/dev/null 2>&1; then
    docker_compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
}

trap cleanup_smoke_stack EXIT INT TERM

validate_secret_configuration
run_static_checks
run_compose_config

if [ "$SMOKE" = "1" ]; then
  run_smoke_checks
else
  echo "Skipping smoke boot checks. Set PRAGMA_VALIDATE_SMOKE=1 to build, boot, and smoke-test the stack."
fi

echo "Production Docker validation checks completed."
