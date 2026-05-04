# Deployment

## Production compose overview

The implemented production Docker path is `docker/docker-compose.yml`. It defines four services with this order:

```text
db -> migrate -> backend -> proxy
```

- `db`: PostgreSQL 18 image with `pg_trgm` and `vector`/pgvector available and installed.
- `migrate`: runs Alembic migrations and exits.
- `backend`: runs Uvicorn with `pragma.app:create_app --factory`.
- `proxy`: builds/serves the admin SPA and proxies API, WebSocket, health, readiness, and public routes.

### Module trusted-code boundary

Enabled modules are unrestricted in-process Python code. Treat write access to the `modules` named volume or non-Docker `PRAGMA_MODULE_ROOT` as backend code-execution authority. The backend logs advisory diagnostics when enabled module roots, manifests, or entrypoints are group/world writable, fail filesystem inspection, or are not owned by the backend process user where ownership is meaningful. Advisory mode is the default so Docker named-volume deployments continue to work across host filesystems. Operators who can guarantee tighter ownership and mode semantics can set `PRAGMA_MODULE_TRUST_STRICT=true`; strict mode rejects unsafe enabled module loading instead of importing the entrypoint.

Named volumes are `db-data`, `media`, and `modules`. The `modules` volume contains trusted executable Python module code when modules are installed; keep writes to it under operator control.

## PostgreSQL requirement

The Docker PostgreSQL image is built from `docker/postgres/Dockerfile`, using `pgvector/pgvector:pg18` by default. `docker/postgres/init.sql` fails fast unless PostgreSQL 18+, `pg_trgm`, and `vector` are available, then creates the extensions.

Non-Docker deployments must provide the same PostgreSQL 18 and extension availability. Stock PostgreSQL without pgvector is not enough for the supported contract.

## Docker base image pinning

Production Dockerfiles keep the human-readable upstream tag and pin each build-time image to an immutable digest (`name:tag@sha256:...`). This covers the backend uv/Python runtime, admin Node build image, Nginx runtime image, Dockerfile frontend, and PostgreSQL 18 pgvector image.

Refresh these pins on a monthly maintenance cadence, and sooner for relevant upstream CVEs. Resolve replacement digests without pulling layers, for example:

```bash
docker buildx imagetools inspect node:24-alpine --format '{{json .Manifest}}'
```

When updating the pgvector base, preserve the PostgreSQL 18-compatible `pgvector/pgvector:pg18` tag plus the new digest, then run compose configuration validation and the production validator before release.

## Environment preparation

Copy the production template and replace placeholders:

```bash
cp docker/prod.env.example docker/prod.env
```

Set database credentials, JWT secret, `PRAGMA_BASE_URL`, published ports, and proxy settings for your deployment. Template host/port values are examples only.

### Raw secrets vs file secrets

For production Docker, configure exactly one source for each secret:

- `PRAGMA_DATABASE_PASSWORD` or `PRAGMA_DATABASE_PASSWORD_FILE`
- `PRAGMA_JWT_SECRET_KEY` or `PRAGMA_JWT_SECRET_KEY_FILE`
- `PRAGMA_SETUP_SECRET` or `PRAGMA_SETUP_SECRET_FILE`

Raw-secret deployments use only `docker/docker-compose.yml` and set the raw variables in `docker/prod.env`.

File-secret deployments use the supported bind-mount override file so the same paths exist in `db`, `migrate`, and `backend`. The default host-side directory is `docker/secrets/`, which is ignored by Git; keep it local-only and never commit secret source files:

```bash
mkdir -p docker/secrets
(
  umask 077
  openssl rand -base64 48 > docker/secrets/pragma_database_password
  openssl rand -base64 48 > docker/secrets/pragma_jwt_secret_key
  openssl rand -base64 48 > docker/secrets/pragma_setup_secret
)
chmod 600 docker/secrets/pragma_database_password docker/secrets/pragma_jwt_secret_key docker/secrets/pragma_setup_secret
```

Then leave `PRAGMA_DATABASE_PASSWORD`, `PRAGMA_JWT_SECRET_KEY`, and `PRAGMA_SETUP_SECRET` empty in `docker/prod.env` so only the `*_FILE` variants are set, then set the host source paths relative to the compose file directory (`docker/`):

```env
PRAGMA_DATABASE_PASSWORD_FILE=/run/secrets/pragma_database_password
PRAGMA_JWT_SECRET_KEY_FILE=/run/secrets/pragma_jwt_secret_key
PRAGMA_SETUP_SECRET_FILE=/run/secrets/pragma_setup_secret
PRAGMA_DATABASE_PASSWORD_SECRET_SOURCE=./secrets/pragma_database_password
PRAGMA_JWT_SECRET_KEY_SECRET_SOURCE=./secrets/pragma_jwt_secret_key
PRAGMA_SETUP_SECRET_SECRET_SOURCE=./secrets/pragma_setup_secret
```

Start or validate with both compose files:

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.secrets.yml --env-file docker/prod.env up -d --build
```

The base compose file forwards both secret variants, `docker/docker-compose.secrets.yml` bind-mounts database/JWT secret files to the documented `/run/secrets/...` paths for `db`, `migrate`, and `backend`, and bind-mounts the setup secret for `migrate` and `backend`. The backend entrypoint loads file secrets, validation rejects raw+file conflicts or missing values, and the admin setup wizard sends the operator setup secret as `X-Pragma-Setup-Secret` during first-run bootstrap.

## Migration and start commands

Build and start the production stack:

```bash
docker compose -f docker/docker-compose.yml --env-file docker/prod.env up -d --build
```

The compose dependency graph runs migrations before the backend is considered startable. To inspect services:

```bash
docker compose -f docker/docker-compose.yml --env-file docker/prod.env ps
docker compose -f docker/docker-compose.yml --env-file docker/prod.env logs backend proxy
```

## Health and readiness

Backend API endpoints:

- `/api/v1/system/health`
- `/api/v1/system/ready`

Proxy aliases:

- `/healthz` -> `/api/v1/system/health`
- `/readyz` -> `/api/v1/system/ready`

The backend container healthcheck calls readiness and requires schema readiness plus installed `pg_trgm` and `pgvector`.

## Proxy routes

The production proxy:

- serves admin SPA routes `/login`, `/setup`, `/app`, and `/app/...`;
- proxies `/api/v1` and `/api/v1/...` to the backend;
- upgrades `/api/v1/realtime/stream` for WebSockets;
- forwards `/` and other public paths to backend-rendered public pages.

## Smoke validation

Static validation:

```bash
./docker/validate-production.sh docker/prod.env
```

Optional smoke validation, with real secrets and available ports:

```bash
PRAGMA_VALIDATE_SMOKE=1 ./docker/validate-production.sh docker/prod.env
```

Smoke validation builds and boots the stack, checks DB extension state, verifies `/healthz`, `/readyz`, `/api/v1/system/health`, `/login`, and `/app`, then cleans up the smoke stack.

## Backup, restore, upgrade, and rollback runbook

### Backup scope

Treat these as the production state set and back them up together:

- `db-data` volume (PostgreSQL data directory)
- `media` volume (uploaded files)
- `modules` volume (trusted installed module code)
- `docker/prod.env` (or your external secret/config source), excluding plaintext secret exports to shared storage

### Backup procedure

1. Confirm stack health before backup (`/readyz`, `/api/v1/system/ready`).
2. Create a PostgreSQL dump from the running `db` service and store it with a timestamped name:

   ```bash
   ts=$(date -u +%Y%m%dT%H%M%SZ)
   mkdir -p backups/$ts
   docker compose -f docker/docker-compose.yml --env-file docker/prod.env exec -T db \
     pg_dump -U "$PRAGMA_DATABASE_USER" -d "$PRAGMA_DATABASE_NAME" -Fc > backups/$ts/database.dump
   ```

3. Archive `media` and `modules` volume contents in the same backup set. Determine the concrete Docker volume names first (`docker volume ls`), then archive each volume:

   ```bash
   docker run --rm -v <media_volume_name>:/src -v "$PWD/backups/$ts":/backup alpine \
     sh -c 'cd /src && tar -czf /backup/media.tar.gz .'
   docker run --rm -v <modules_volume_name>:/src -v "$PWD/backups/$ts":/backup alpine \
     sh -c 'cd /src && tar -czf /backup/modules.tar.gz .'
   ```

4. Record the running image digests/tag set (`docker compose ... images`) with the backup.

### Restore procedure

1. Stop application services (`proxy`, `backend`, `migrate`) before data restore.
2. Restore `db-data` from `database.dump` into PostgreSQL (empty target DB or rebuilt cluster).
3. Restore `media` and `modules` archives back into their volumes.
4. Bring the stack up and run migration-forward (`migrate` service / `alembic upgrade head`).
5. Run smoke checks listed below before reopening traffic.

### Upgrade order

Use this order for every production upgrade:

1. Take a fresh backup set (`db-data`, `media`, `modules`).
2. Update images/configuration.
3. Run migrations first (`db -> migrate`).
4. Start `backend`, then `proxy`.
5. Run smoke checks.

### Rollback policy

- If smoke checks fail after an upgrade, roll back as a full set: previous images/config + matching `database.dump` + matching `media`/`modules` archives.
- Do not run downgrade migrations for emergency rollback unless the migration explicitly documents safe reversal. Default policy is restore-from-backup.
- After rollback restore, rerun migration-forward only when redeploying a fixed build.

### Post-change smoke checks

After restore, upgrade, or rollback, verify at minimum:

- `GET /healthz` and `GET /readyz` return success
- `GET /api/v1/system/ready` reports schema/extensions ready
- Admin login and `/app` load
- Public homepage loads
- Representative media asset and installed module behavior still work

## Non-Docker deployment notes

The repo does not include systemd, nginx, or other non-Docker service-manager artifacts. The current manual path is:

1. Provision PostgreSQL 18 with `pg_trgm` and `vector`/pgvector.
2. Prepare `backend/.env` with runtime settings, strong secrets, and `PRAGMA_RUNTIME_ENVIRONMENT=production` before running migrations or starting the backend. This activates production secret-strength and setup-secret fail-closed validation; leaving the development default in place can let a production process start with placeholder/weak values. For production first-run bootstrap, set exactly one of `PRAGMA_SETUP_SECRET` or `PRAGMA_SETUP_SECRET_FILE`; enter the same value in the setup wizard's Operator setup secret field.
3. Run backend dependencies and migrations:

   ```bash
   cd backend
   uv sync --dev
   set -a && . ./.env && set +a
   uv run alembic upgrade head
   ```

4. Run Uvicorn behind your chosen process manager/reverse proxy:

   ```bash
   cd backend
   set -a && . ./.env && set +a
   uv run uvicorn pragma.app:create_app --factory --host 127.0.0.1 --port 8000 --proxy-headers
   ```

5. Build the admin SPA and serve `admin/dist` with your external web server/reverse proxy:

   ```bash
   cd admin
   npm ci
   npm run build
   ```

Route `/api/v1` and websocket traffic to the backend, admin SPA routes to the built admin assets, and public `/` traffic to the backend if you want the same split as the Docker proxy.
