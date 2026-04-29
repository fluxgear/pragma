# Architecture

## High-level system

Pragma is a single-site CMS with three main surfaces:

- FastAPI backend for APIs, setup, auth, content, media, search/AI, modules, users, realtime, and public rendering.
- Vue 3 admin SPA for authenticated administration.
- Backend-rendered public frontend using filesystem themes and Jinja templates.

PostgreSQL is the system of record. Database access is raw SQL through psycopg-backed query modules under `backend/src/pragma/storage/queries/`; there is no ORM.

## Backend lifecycle

`pragma.app:create_app` loads settings, configures logging, builds the FastAPI lifespan, attaches storage/theme/module/realtime runtime state, registers exception handling, mounts API routers under `/api/v1`, and mounts the public router at root.

## REST API under `/api/v1`

Implemented routers include system, install, auth, content, media, search, AI, modules, users, and realtime. APIs return JSON except the realtime WebSocket transport. Authenticated write operations are protected by bearer access tokens and permission checks.

## Admin SPA

The admin app is a Vue 3/Vite SPA with routes for `/login`, `/setup`, `/app`, `/app/content`, `/app/media`, `/app/ai`, `/app/users`, and `/app/account`. Router guards check install status, authentication, forced-password-change state, and permissions.

## Backend-rendered public frontend

Public visitor routes are served by FastAPI and rendered through the active theme. Implemented public paths include `/`, `/pages/{slug}`, `/posts/{slug}`, `/archive`, `/search`, `/theme/static/...`, and themed 404s. Public views expose published content only.

## Storage model

- PostgreSQL stores users, roles/permissions, install state, content types, entries, media metadata, search documents, AI settings, module state, sessions, and related state.
- Local filesystem stores media bytes.
- Theme and module definitions are discovered from filesystem roots.
- Search uses PostgreSQL-native keyword/fuzzy/vector storage and ranking; semantic search is optional and degrades when unavailable.

## Auth and RBAC

Authentication uses bearer access tokens plus an HTTP-only refresh cookie. Built-in roles are `administrator`, `editor`, `author`, and `viewer`. Permissions gate content, media, AI settings, modules, and users. Superusers bypass permission checks, and the bootstrap administrator is a superuser with the administrator role.

## Content, media, search, and AI integration

Content saves validate structured fields and rich text, then isolate side effects: search indexing, realtime publishing, and module hook dispatch should not turn optional subsystem failures into content CRUD failures.

Media is local-filesystem backed and currently supports image uploads for JPEG, PNG, GIF, and WebP.

Search supports keyword/fuzzy/vector/hybrid behavior. AI settings are privileged/admin-managed and support embeddings for semantic search; provider failures degrade search rather than making semantic search mandatory.

## Realtime

Realtime is admin-facing. Authenticated users obtain short-lived tickets, then connect to `/api/v1/realtime/stream`. Delivery uses WebSockets and PostgreSQL LISTEN/NOTIFY; no external broker is part of the repo.

## Modules

Modules are filesystem-discovered backend extensions with manifests, persisted enablement state, and content-entry hooks. Module APIs are backend-only and permission-gated. There are no bundled modules and no admin module-management route in the current SPA.

## Themes

Themes are filesystem-discovered template/static bundles selected by settings. The repo includes `themes/default`. Theme fallback resolves active/default templates and assets on the backend; no theme-management admin UI is currently implemented.

## Production routing

The Docker production proxy serves admin SPA routes from built static assets, proxies `/api/v1` and realtime WebSockets to the backend, maps `/healthz` and `/readyz` to backend health/readiness, and forwards public `/` traffic to backend-rendered pages.
