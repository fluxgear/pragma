# Pragma

Pragma is a single-site, multi-user PostgreSQL-native CMS. The repository currently contains a FastAPI backend, a Vue 3 admin SPA, and a backend-rendered public frontend. It is intended to run with PostgreSQL 18 plus `pg_trgm` and `vector`/pgvector.

## Implemented capabilities

- FastAPI backend with REST APIs under `/api/v1`.
- Setup wizard/bootstrap flow for the first administrator.
- JWT bearer access tokens with an HTTP-only refresh cookie.
- Built-in roles: `administrator`, `editor`, `author`, and `viewer`.
- Content-type and content-entry administration.
- Local image media library for JPEG, PNG, GIF, and WebP uploads.
- Public search with keyword/fuzzy modes and optional semantic/vector behavior.
- Optional AI provider settings for search embeddings, managed by privileged admin users.
- Filesystem-discovered themes with a checked-in default theme.
- Filesystem-discovered backend modules with permission-gated APIs.
- Admin-facing realtime updates over ticketed WebSockets and PostgreSQL LISTEN/NOTIFY.
- Backend-rendered public routes for home, pages, posts, archive, search, theme static assets, and themed 404s.
- Production Docker Compose stack with PostgreSQL, migration, backend, and proxy services.

## Architecture at a glance

```text
Browser
├─ /login, /setup, /app/*  -> Vue admin SPA
├─ /api/v1/*               -> FastAPI REST/WebSocket API
└─ /, /pages/*, /posts/*   -> FastAPI + Jinja theme rendering

FastAPI backend -> PostgreSQL 18 + pg_trgm + pgvector
                -> local media filesystem
                -> theme/module filesystem roots
```

The backend uses raw SQL through psycopg-backed query modules, not an ORM. See [Architecture](docs/architecture.md).

## Quick-start choices

Choose one path:

1. [Docker-backed development database + local backend/admin](docs/installation.md#docker-backed-development-database). This is the normal local development path. The development compose file starts PostgreSQL only; it is not a full application stack.
2. [Manual non-Docker installation](docs/installation.md#manual-non-docker-path). Provision PostgreSQL 18 and extensions yourself, then run backend and admin commands locally.
3. [Production Docker deployment](docs/deployment.md#production-compose-overview). Compose starts `db -> migrate -> backend -> proxy`.

After the backend is reachable, use the [setup wizard](docs/setup-wizard.md) to create the first administrator.

## Repository layout

```text
backend/   FastAPI application, Alembic migrations, tests, package README
admin/     Vue 3 admin SPA and Vitest tests
docker/    Development DB compose, production compose, images, proxy, validation
themes/    Filesystem themes; `themes/default` is checked in
docs/      Installation, configuration, development, testing, deployment, architecture
```

## Requirements

- Python 3.12 for the backend.
- `uv` for backend dependency and command execution.
- Node.js/npm for the admin SPA.
- Docker with Docker Compose for Docker-backed paths.
- PostgreSQL 18 with `pg_trgm` and `vector`/pgvector for supported database operation.

Example host and port values in env files are examples only; configure them for your machine or deployment.

## Docker vs non-Docker summary

| Path | What the repo provides | Primary docs |
| --- | --- | --- |
| Docker development | PostgreSQL 18 dev database only | [Installation](docs/installation.md), [Development](docs/development.md) |
| Docker production | Full compose stack: DB, migrations, backend, proxy | [Deployment](docs/deployment.md) |
| Non-Docker | Manual DB, backend, and admin commands | [Installation](docs/installation.md), [Deployment](docs/deployment.md#non-docker-deployment-notes) |

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Setup wizard](docs/setup-wizard.md)
- [Development](docs/development.md)
- [Testing](docs/testing.md)
- [Deployment](docs/deployment.md)
- [Architecture](docs/architecture.md)
- [Modules and themes](docs/modules-themes.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Backend package README](backend/README.md)

## Non-goals and unsupported claims

Current repository docs intentionally do not claim: a full-stack Docker development app stack, bundled modules, module or theme management screens in the admin SPA, object storage/S3, non-image uploads, generated thumbnails/derivatives, mandatory semantic search, multi-site hosting, or checked-in non-Docker service-manager/reverse-proxy units.
