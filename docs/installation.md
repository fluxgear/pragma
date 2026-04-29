# Installation

This guide covers Pragma's supported installation paths without assuming one fixed host or port. Values shown from env examples are examples, not product requirements.

## Prerequisites

- Python 3.12 and `uv` for the backend.
- Node.js/npm for the admin SPA.
- Docker with Docker Compose for Docker-backed database or production paths.
- PostgreSQL 18 with `pg_trgm` and `vector`/pgvector for manual database provisioning.

## Environment file conventions

Pragma has two different env families for local Docker DB and backend runtime:

- `docker/dev.env.example` is consumed by `docker/docker-compose.dev.yml` and uses `PRAGMA_DB_*` for the development PostgreSQL container.
- `backend/.env.example` is consumed by the backend settings loader and uses `PRAGMA_DATABASE_*`.
- `docker/prod.env.example` is consumed by the production compose stack and also uses `PRAGMA_DATABASE_*` for backend and DB services.

Do not substitute `PRAGMA_DB_*` for backend runtime settings. The sample `127.0.0.1` and port values are examples for a local machine.

## Docker-backed development database

The development compose file starts PostgreSQL only. It does not start the backend, admin SPA, or proxy.

```bash
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example up -d
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example ps
```

The example dev env publishes the database on host port `5433` and creates database/user `pragma`. Change `docker/dev.env.example` values in your own env file if that port or credential set is not appropriate.

## Local backend and admin against that database

Create a backend env file and edit it for your database and secrets:

```bash
cp backend/.env.example backend/.env
```

With the example dev database above, `backend/.env.example` already points at `127.0.0.1:5433`; treat that as an example, not a requirement.

Install backend dependencies and run migrations:

```bash
cd backend
uv sync --dev
set -a && . ./.env && set +a
uv run alembic upgrade head
```

Run the backend:

```bash
cd backend
set -a && . ./.env && set +a
uv run uvicorn pragma.app:create_app --factory --host 127.0.0.1 --port 8000 --proxy-headers
```

Install and run the admin SPA in another shell:

```bash
cd admin
npm ci
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```

The Vite proxy target is optional but useful for local same-origin `/api` calls during development.

## Manual non-Docker path

Provision PostgreSQL 18 and install/enable the required extensions in the Pragma database and template you use for tests or future database creation:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
```

Then follow the backend/admin commands above with `backend/.env` pointed at your manually provisioned database. The backend settings require database host, port, name, user, password, JWT secret, and base URL.

## Setup wizard handoff

Once migrations have run and the backend answers `/api/v1/system/ready`, open the admin app and complete the [setup wizard](setup-wizard.md). The wizard creates the first administrator; it does not provision PostgreSQL or run migrations.
