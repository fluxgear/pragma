# Changelog

## v0.7.1 — 2026-04-23

### Fixed
- Shipped the checked-in `themes/` tree in backend release artifacts via Hatch sdist and wheel packaging so installed environments resolve the default theme without manual `PRAGMA_THEME_ROOT` overrides
- Fixed default-theme sparse-render behavior by removing duplicate fallback titles, routing shared fallback navigation through working home/archive/search URLs, and keeping 404/post recovery links functional off the home page
- Preserved the server-rendered theme mode in `themes/default/static/js/theme.js`, aligned the shipped CSS/SCSS selector surface including `post-shell` and `meta-list`, restored the required copyright header in `backend/src/pragma/config.py`, and expanded backend theme verification coverage for packaging and sparse-render contracts

## v0.7.0 — 2026-04-22

### Added
- Added the checked-in `themes/default/` flagship theme with a strict manifest, full required public-page coverage, shared partials, dark-mode support, and premium corporate styling
- Added theme-owned static assets under `themes/default/static/`, including shipped runtime CSS, SCSS source structure, a minimal theme-toggle script, and supporting SVG artwork
- Added repo-backed backend smoke tests for checked-in theme discovery, required template coverage, sparse-context rendering, asset resolution, and app startup against the real default theme tree

## v0.6.1 — 2026-04-22

### Fixed
- Fixed M6 theme rendering fallback so active-theme render-time failures now retry the default theme instead of surfacing raw exceptions
- Fixed M6 nested template fallback locality so default-theme fallback no longer mixes active-theme `extends` or `include` fragments into the rendered output
- Normalized configured theme IDs before runtime lookup so padded or mixed-case `PRAGMA_THEME_ACTIVE_ID` and `PRAGMA_THEME_DEFAULT_ID` values resolve deterministically
- Added focused regression coverage for render-time fallback, nested fallback locality, theme ID normalization, and fallback-exhaustion error reporting

## v0.6.0 — 2026-04-22

### Added
- Added the M6 backend theme engine with config-backed theme selection via `PRAGMA_THEME_ROOT`, `PRAGMA_THEME_ACTIVE_ID`, and `PRAGMA_THEME_DEFAULT_ID`
- Added filesystem theme discovery, manifest validation, deterministic template and asset resolution, and lazy active-to-default fallback behavior under `backend/src/pragma/themes/`
- Added Jinja2-backed template loading so broken active-theme templates fall back cleanly to the default theme when possible
- Added focused backend coverage for theme discovery, activation, template precedence, broken-template fallback, asset lookup, and startup wiring

## v0.5.1 — 2026-04-22

### Fixed
- Enforced a valid refresh-cookie policy so `SameSite=None` now requires secure cookies
- Hardened local media writes against symlink escapes outside the configured media root and made failed file deletion abort the metadata delete instead of silently orphaning bytes
- Published structured media API error responses in router metadata and aligned the M5 media migration indexes with the default `updated_at` listing contract
- Added focused backend regression coverage for media policy validation, upload failure paths, missing files, storage escape attempts, delete failure semantics, and media OpenAPI metadata
- Extended the admin media API helpers with `limit`, `offset`, and `order_by` support plus regression coverage for query serialization
- Corrected the admin media library UI so load failures no longer render the empty-state message and added a focused regression test

## v0.5.0 — 2026-04-21

### Added
- Added the M5 media library with a new backend media module, pluggable storage backend abstraction, and local filesystem storage as the default backend
- Added authenticated media APIs for upload, browse, detail, content retrieval, and delete under `/api/v1/media/assets`
- Added image metadata extraction and stable media selection payloads suitable for later editor integration
- Added an admin media workspace under `/app/media` with upload, preview, browse, and delete flows plus focused frontend coverage
- Added Alembic schema/index support for media assets and backend integration coverage for migration, auth enforcement, validation, storage persistence, and derivative-failure isolation

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

