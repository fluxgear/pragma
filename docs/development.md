# Development

## Local workflow overview

A typical local session uses Docker only for PostgreSQL, then runs the backend and admin SPA directly on the host:

1. Start the Docker-backed development database.
2. Run backend migrations.
3. Start FastAPI/Uvicorn.
4. Start the Vite admin dev server.
5. Complete setup if the database is fresh.

## Start the development database

```bash
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example up -d
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example ps
```

This compose file is DB-only. It is not a full Pragma app stack.

## Backend setup and run

```bash
cp backend/.env.example backend/.env
cd backend
uv sync --dev
set -a && . ./.env && set +a
uv run alembic upgrade head
uv run uvicorn pragma.app:create_app --factory --host 127.0.0.1 --port 8000 --proxy-headers
```

The example `backend/.env.example` values assume a local database reachable at `127.0.0.1:5433`; edit your `backend/.env` if you use different values.

Backend routes include:

- API routers under `/api/v1`: system, install, auth, content, media, search, AI, modules, users, and realtime.
- Public server-rendered routes: `/`, `/pages/{slug}`, `/posts/{slug}`, `/archive`, `/search`, `/theme/static/...`, and themed 404 handling.

## Admin setup and run

```bash
cd admin
npm ci
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```

Implemented admin routes are:

- `/login`
- `/setup`
- `/app`
- `/app/content`
- `/app/media`
- `/app/ai`
- `/app/users`
- `/app/account`

The admin API base defaults to `/api/v1`. During Vite development, set `VITE_BACKEND_PROXY_TARGET` when you want `/api` proxied to a local backend.

## Public frontend behavior

The public site is rendered by the backend through the active theme's Jinja templates. It is not a separate SPA. Public content is published-only, uses theme templates from the configured theme root, and serves theme static files through `/theme/static/...`.

## Theme and module working directories

- Themes are loaded from `PRAGMA_THEME_ROOT` and selected with `PRAGMA_THEME_ACTIVE_ID` plus `PRAGMA_THEME_DEFAULT_ID`. The checked-in default theme is `themes/default`.
- Modules are loaded from `PRAGMA_MODULE_ROOT`. No module directory or bundled module is currently checked in. Module APIs exist on the backend and require module-management permission.

## Reset and cleanup notes

The dev database volume is `pragma-postgres-dev-data`. To remove the dev DB container and volume:

```bash
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example down --volumes
```

For production-compose cleanup during smoke validation, use the validation script's own cleanup path rather than deleting volumes by hand unless you intend to lose data.
