# Changelog

## v0.4.1 — 2026-04-21

### Fixed
- Routed the admin content API helpers through the active bearer access token so protected `/api/v1/content/*` requests no longer fail after login
- Preserved unchanged legacy `rich_text` HTML during entry updates and content-type revalidation while keeping strict M4 validation for new or modified rich-text payloads
- Added focused frontend and backend regression coverage for protected content API auth propagation and legacy rich-text round-tripping
- Replaced the shared admin-shell milestone label with the generic `Admin workbench` text
- Split the admin production bundle into smaller chunks so the previous Vite chunk-size warning no longer appears during builds

## v0.4.0 — 2026-04-21

### Added
- Added a new admin content-entry workspace under `/app/content` with content-type selection, entry listing, and create/edit dialogs
- Added dynamic admin field rendering for content entries, including TipTap 2-backed editing for `rich_text` fields
- Added admin content API client helpers and TypeScript contracts for content types and content entries
- Added frontend verification for rich-text editor integration, form serialization, and content workspace flows

### Fixed
- Enforced a backend rich-text HTML contract for `rich_text` fields so unsupported tags, attributes, malformed fragments, and visually empty required documents now fail cleanly
- Verified rich-text save/load round-tripping across create, reload, and update flows without changing the existing JSONB content-entry schema

## v0.3.1 — 2026-04-21

### Fixed
- Kept installed systems on the boot error/retry flow whenever startup or session-restore failures persist, instead of falling through to non-boot routes after initialization
- Redirected the protected dashboard back to login immediately when post-mount identity sync fails
- Added targeted frontend regression coverage for startup guard failures, persisted startup errors, non-startup auth errors, and dashboard auth-loss redirects

## v0.3.0 — 2026-04-20

### Added
- Added the `admin/` Vue 3 + TypeScript + Vite workspace for the Pragma admin SPA
- Added centralized frontend API clients for install status, bootstrap, readiness, login, refresh, logout, and current-user flows under `admin/src/api/`
- Added Pinia auth/install stores plus install-aware and auth-aware Vue Router guards for admin navigation
- Added the M3 phase-1 setup wizard, login flow, and dashboard/workbench shell with PrimeVue-based layout primitives
- Added frontend coverage for route-guard behavior, auth-store session handling, and setup-wizard success/conflict flows

### Fixed
- Suppressed the expected anonymous-state `401` refresh failure during session restore so the login screen no longer shows a spurious `Refresh token is required` banner after protected-route redirects or logout

## v0.2.1 — 2026-04-20

### Fixed
- Rejected whitespace-only content-type names during request validation for create and update flows
- Added focused M2 content validation coverage for blank names, unknown fields, missing required fields, and wrong-type field values
- Removed the Alembic `path_separator` deprecation warning and restored standalone `alembic upgrade head` verification from the local backend workspace configuration
- Updated backend package metadata wording and version references for the M2 audit patch release

## v0.2.0 — 2026-04-20

### Added
- Implemented the M2 content engine with authenticated content-type CRUD APIs and field-definition validation under `/api/v1/content/types`
- Implemented JSONB-backed content entry CRUD APIs under `/api/v1/content/entries` with explicit structured validation errors
- Added content slug normalization, scoped entry-slug conflict handling, auto-generated slugs, and publish-state transitions for draft, published, and archived entries
- Added a dedicated raw-SQL content query layer, Alembic schema/indexes for content tables, and backend integration coverage for migrations, auth enforcement, CRUD flows, and failure paths

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

