# Changelog

## v0.13.1 — 2026-04-27

### Fixed
- Fixed public `body_html` projection safety by trusting only schema-declared `rich_text` fields for HTML rendering and escaping plain-text `body_html` values
- Fixed public search handling so overlong queries fail visitor-safe with `search_error` state instead of surfacing validation exceptions as 500 responses
- Removed broad exception handling from public template rendering fallback and limited recovery behavior to `ThemeError`-driven paths with focused regression coverage

## v0.13.0 — 2026-04-27

### Added
- Added the M13 public frontend with server-rendered Jinja2 routes for home, pages, posts, archive, search, theme assets, and themed 404 handling
- Added published-only public view-model assembly, SEO metadata generation, archive/search pagination, and visitor-safe render fallback behavior
- Added backend integration coverage for public rendering, unpublished-content isolation, archive/search states, theme assets, API 404 preservation, and render-failure fallback

## v0.12.0 — 2026-04-27

### Added
- Added the M12 PostgreSQL-native realtime pipeline with explicit event envelopes, `LISTEN/NOTIFY` publication and listener bridging, bounded WebSocket fanout, and authenticated short-lived subscription tickets
- Added admin realtime client/store behavior with reconnect, disconnect, auth-close handling, live status display, and content-entry invalidation refreshes in the admin workspace
- Added focused backend and frontend coverage for notification delivery, subscription authorization, reconnect/disconnect handling, realtime failure isolation from content CRUD, and admin refresh behavior

## v0.11.1 — 2026-04-27

### Fixed
- Closed the M11 audit bug line by blocking non-publishers from modifying or unpublishing already-published entries, revoking refresh sessions after self-service password changes, and assigning the bootstrap root the persisted `administrator` role with explicit role/permission metadata
- Added focused M11 migration regression coverage for RBAC schema/seed assertions, legacy superuser-only administrator backfill, and downgrade preservation of pre-M11 user data while removing RBAC tables and columns
- Removed duplicate admin router title-hook work, cleaned the router EOF formatting regression, and aligned legacy AI/modules permission-denial tests with the new bootstrap administrator-role behavior

## v0.11.0 — 2026-04-27

### Added
- Added the M11 roles-and-permissions foundation with seeded built-in roles, persisted role/permission assignments, forced-password-change state, and a new administrative user-management API under `/api/v1/users`
- Added authenticated account password-change flow, administrative password reset with session revocation, role-assignment management, and focused backend/frontend regression coverage for M11 authorization and user lifecycle behavior
- Added admin user-management and account views under `/app/users` and `/app/account`, permission-aware navigation gating, and typed admin API clients for user, role, and account-management flows

### Fixed
- Replaced binary login-only or superuser-only authorization checks with explicit permission enforcement across content, media, AI settings, and module management routes, including structured `AUTH_PERMISSION_DENIED` failures and publish-specific content enforcement
- Preserved M11 verification reliability by fixing role-assignment persistence against psycopg connection capabilities, aligning legacy auth/module/AI tests with the new permission-denial contract, and restoring clean frontend spec parsing plus password-reset UI feedback behavior

## v0.10.0 — 2026-04-26

### Added
- Added the constrained M10 backend modules subsystem under `backend/src/pragma/modules/` with strict manifest validation, filesystem discovery, persisted enable/disable lifecycle state, deterministic hook loading, and explicit superuser-only management APIs
- Added focused backend module coverage for migration contracts, module-state API behavior, event dispatch ordering, malformed module identifiers, and post-commit content hook execution

### Fixed
- Preserved core CMS resilience by dispatching module hooks only after successful content-entry transactions commit, isolating module load/hook failures from CRUD responses, and documenting the configurable `PRAGMA_MODULE_ROOT` discovery surface

## v0.9.1 — 2026-04-26

### Fixed
- Restricted AI settings reads and `/app/ai` routing to superusers so provider configuration metadata is no longer exposed to ordinary authenticated users
- Allowed disabled AI settings to clear optional provider metadata cleanly while preserving strict completeness requirements when AI is enabled
- Validated provider base URLs before persistence/use and translated malformed provider URL failures into structured semantic-search fallback behavior instead of surfacing unexpected exceptions
- Blocked AI settings saves after load failures and added focused backend/frontend regression coverage for the M9 audit fixes

## v0.9.0 — 2026-04-26

### Added
- Added optional AI/provider integration under `backend/src/pragma/ai/` with persisted singleton provider settings, authenticated admin/API setup surfaces, provider connectivity testing, and explicit search-embedding rebuild flows
- Added query-time semantic embedding generation for `/api/v1/search/entries` when semantic search is enabled and provider, pgvector, and embedding-column prerequisites are available
- Added an admin AI settings workspace under `/app/ai` with PrimeVue configuration, provider testing, rebuild controls, route/nav integration, and focused frontend coverage

### Fixed
- Preserved core CMS isolation by keeping external provider calls out of content CRUD/search-document sync hooks, clearing stale stored embeddings on AI settings changes, and falling back cleanly to keyword/fuzzy search when AI configuration or provider requests fail
- Hardened provider failure handling so low-level request timeouts are translated into structured search-domain errors instead of surfacing as unexpected exceptions

## v0.8.1 — 2026-04-24

### Fixed
- Aligned the M8 search migration backfill with runtime search-document derivation for ordered title/body fields and searchable field names
- Isolated derived search indexing and rebuild failures from primary content CRUD writes while preserving structured search error handling at search boundaries
- Hardened vector search against mixed-dimension embeddings, removed duplicate search strategy aliasing, and added focused search/content regression coverage

## v0.8.0 — 2026-04-23

### Added
- Added the M8 PostgreSQL-native search foundation with a public `/api/v1/search/entries` endpoint covering keyword, fuzzy, vector, and hybrid search modes with stable paginated result contracts
- Added a derived `pragma_search_documents` search index table, extension-aware `pg_trgm`/`pgvector` support, hybrid reciprocal-rank fusion, and transactional search-document sync/rebuild hooks on content writes
- Added focused backend search coverage for migration contracts, ranking modes, degraded extension behavior, OpenAPI error metadata, and content/search synchronization

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

