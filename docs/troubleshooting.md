# Troubleshooting

## DB connection or port mismatch

Symptoms: backend startup fails, `/api/v1/system/ready` fails, or compose DB health is unhealthy.

Checks:

```bash
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example ps
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example logs postgres
```

Confirm that `docker/dev.env.example` or your dev env uses `PRAGMA_DB_*`, while `backend/.env` uses `PRAGMA_DATABASE_*`. The example dev port `5433` is not required; it just must match your backend env.

## Missing PostgreSQL extensions

Readiness and production healthchecks expect PostgreSQL 18 with `pg_trgm` and `vector`/pgvector. Check:

- `/api/v1/system/ready`
- `/readyz` through the production proxy
- `docker compose -f docker/docker-compose.yml --env-file docker/prod.env ps`

For production Docker, use the checked-in Postgres image path rather than replacing it with stock PostgreSQL unless you provide pgvector yourself.

## Setup wizard blocked by readiness

The wizard depends on install status and system readiness. If setup is blocked, verify migrations and readiness:

```bash
cd backend
set -a && . ./.env && set +a
uv run alembic upgrade head
```

Then check `/api/v1/system/ready`.

## JWT or cookie misconfiguration

Symptoms: login works once but refresh/logout/session restore fails, or browsers drop refresh cookies.

Check `PRAGMA_JWT_SECRET_KEY`, `PRAGMA_REFRESH_COOKIE_NAME`, `PRAGMA_REFRESH_COOKIE_PATH`, `PRAGMA_REFRESH_COOKIE_SECURE`, and `PRAGMA_REFRESH_COOKIE_SAMESITE`. `SameSite=None` requires secure cookies. For production Docker file secrets, set exactly one of raw or `*_FILE` values.

## Media path permissions

Uploads require the backend to write to `PRAGMA_MEDIA_ROOT`. Production Docker mounts the `media` volume at `/var/lib/pragma/media`. For local runs, relative `media` resolves under `backend/`.

If uploads fail, inspect backend logs and verify the directory exists and is writable by the backend process. Supported uploads are PNG, JPEG, GIF, WebP, PDF, MP3, WAV, OGG, MP4, and WebM by default. SVG remains unsupported because raw SVG can carry active content. Raster images generate thumbnail derivatives; if derivative generation fails, Pragma preserves the original upload and logs a warning.

## Theme fallback errors

If public pages render 404s or theme errors, verify `PRAGMA_THEME_ROOT`, `PRAGMA_THEME_ACTIVE_ID`, and `PRAGMA_THEME_DEFAULT_ID`. The checked-in fallback is `themes/default` with id `default`. Theme ids must use the configured identifier format, and template/static paths must stay inside the theme directory.

## Module load isolation

Module discovery/loading failures should not take down core content operations, but failed modules may not register hooks. Check backend logs and `/api/v1/modules` with a user that has module-management permission. A `MODULE_TRUSTED_CODE_EXECUTION` warning means Pragma imported an enabled module entrypoint as trusted in-process Python code; verify that `PRAGMA_MODULE_ROOT` is writable only by your operator-controlled deployment path. No bundled modules are expected in a fresh checkout.

## Semantic search fallback

If semantic results are absent, check `PRAGMA_SEARCH_ENABLE_SEMANTIC`, database extension capability from `/api/v1/system/ready`, and AI provider settings in the admin AI area. Search should still degrade to keyword/fuzzy behavior when semantic prerequisites are missing or provider calls fail.

## Realtime disabled or unavailable

Check `PRAGMA_REALTIME_ENABLED` and the realtime settings in [Configuration](configuration.md). In production, the proxy must upgrade `/api/v1/realtime/stream`. If realtime is unavailable, the admin should still rely on normal API fetch/resync behavior.

## Production validation failures

Run static validation first:

```bash
./docker/validate-production.sh docker/prod.env
```

Common failures include missing Docker Compose, raw/file secret conflicts, missing required secrets, invalid compose config, nginx template errors, unavailable published ports during smoke validation, or failed DB extension checks. Use compose logs for the affected service:

```bash
docker compose -f docker/docker-compose.yml --env-file docker/prod.env logs db migrate backend proxy
```

Health endpoints to check through the proxy are `/healthz` and `/readyz`; direct backend equivalents are `/api/v1/system/health` and `/api/v1/system/ready`.
