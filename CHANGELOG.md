# Changelog

## v0.1.1 — 2026-04-20

### Fixed
- Removed the silent `PRAGMA_DB_PORT` host-port fallback from `docker/docker-compose.dev.yml`; the dev PostgreSQL Docker path now fails fast unless the operator sets the published port explicitly
- Corrected capability reporting so the public `pgvector` capability maps to PostgreSQL's actual `vector` extension name
- Provisioned `pg_trgm` and `vector` in each test-created database and strengthened install/readiness tests to assert capability payload values

## v0.1.0 — 2026-04-20

### Added
- Scaffolded the Pragma backend for M1 under `backend/src/pragma/`
- Added config-driven FastAPI application startup and structured error handling
- Added PostgreSQL storage pool and raw-SQL query layer
- Added standalone Alembic setup and the initial auth/install baseline migration
- Added install-state detection, readiness/liveness endpoints, and first-admin bootstrap flow
- Added JWT authentication with login, refresh, logout, and current-user endpoints
- Added backend integration tests for startup, install status, migrations, bootstrap, and auth flows
- Added Docker-backed PostgreSQL 18 development database setup with `pg_trgm` and `pgvector`

