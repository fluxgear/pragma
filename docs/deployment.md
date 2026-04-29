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

Named volumes are `db-data`, `media`, and `modules`.

## PostgreSQL requirement

The Docker PostgreSQL image is built from `docker/postgres/Dockerfile`, using `pgvector/pgvector:pg18` by default. `docker/postgres/init.sql` fails fast unless PostgreSQL 18+, `pg_trgm`, and `vector` are available, then creates the extensions.

Non-Docker deployments must provide the same PostgreSQL 18 and extension availability. Stock PostgreSQL without pgvector is not enough for the supported contract.

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

The compose file forwards both variants, the backend entrypoint loads file secrets, and validation rejects raw+file conflicts or missing values.

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

## Non-Docker deployment notes

The repo does not include systemd, nginx, or other non-Docker service-manager artifacts. The current manual path is:

1. Provision PostgreSQL 18 with `pg_trgm` and `vector`/pgvector.
2. Prepare `backend/.env` with runtime settings and strong secrets.
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
