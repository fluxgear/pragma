# Configuration

The backend reads environment variables with the `PRAGMA_` prefix from `backend/.env` or the process environment. Production Docker passes the same settings through compose, with fixed container paths for media, themes, and modules.

## Required backend variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `PRAGMA_DATABASE_HOST` | yes | none | PostgreSQL host for the backend. |
| `PRAGMA_DATABASE_PORT` | yes | none | 1-65535. |
| `PRAGMA_DATABASE_NAME` | yes | none | Application database. |
| `PRAGMA_DATABASE_USER` | yes | none | Database user. |
| `PRAGMA_DATABASE_PASSWORD` | yes unless using file secret in Docker | none | Non-empty raw password. |
| `PRAGMA_JWT_SECRET_KEY` | yes unless using file secret in Docker | none | Minimum length 16; use a strong random value. |
| `PRAGMA_BASE_URL` | yes | none | Public base URL used for generated URLs. |

## Database and pool variables

| Variable | Default | Validation/behavior |
| --- | --- | --- |
| `PRAGMA_DATABASE_ADMIN_DATABASE` | `postgres` | Maintenance database for administrative checks. |
| `PRAGMA_DATABASE_POOL_MIN_SIZE` | `1` | Must be at least 1. |
| `PRAGMA_DATABASE_POOL_MAX_SIZE` | `10` | Must be at least 1. |

PostgreSQL 18 with `pg_trgm` and `vector`/pgvector is the supported target. Readiness reports extension state through `/api/v1/system/ready`.

## JWT and refresh-cookie variables

| Variable | Default | Notes |
| --- | --- | --- |
| `PRAGMA_JWT_ALGORITHM` | `HS256` | Minimum length 3. |
| `PRAGMA_JWT_ACCESS_TOKEN_TTL_MINUTES` | `15` | At least 1. |
| `PRAGMA_JWT_REFRESH_TOKEN_TTL_DAYS` | `7` | At least 1. |
| `PRAGMA_REFRESH_COOKIE_NAME` | `pragma_refresh_token` | Non-empty. |
| `PRAGMA_REFRESH_COOKIE_PATH` | `/api/v1/auth` | Non-empty. |
| `PRAGMA_REFRESH_COOKIE_SECURE` | `false` | Set true behind HTTPS. |
| `PRAGMA_REFRESH_COOKIE_SAMESITE` | `lax` | `lax`, `strict`, or `none`; `none` requires secure cookies. |

## Media variables

| Variable | Default | Notes |
| --- | --- | --- |
| `PRAGMA_MEDIA_STORAGE_BACKEND` | `local` | Local filesystem is the only implemented backend. |
| `PRAGMA_MEDIA_ROOT` | `media` | Relative paths resolve under `backend/`; production Docker uses `/var/lib/pragma/media`. |
| `PRAGMA_MEDIA_MAX_UPLOAD_BYTES` | `10485760` | 1 byte to 100 MiB. |
| `PRAGMA_MEDIA_ALLOWED_MIME_TYPES` | `image/jpeg,image/png,image/gif,image/webp` | Upload sniffing is implemented for these image types. |

There is no object storage/S3 backend, non-image upload support, or generated thumbnail/derivative pipeline in the current repo.

## Theme and module variables

| Variable | Default | Notes |
| --- | --- | --- |
| `PRAGMA_THEME_ROOT` | `../themes` | Filesystem theme root; production Docker uses `/app/themes`. |
| `PRAGMA_MODULE_ROOT` | `../modules` | Filesystem module root for trusted operator-installed Python modules; production Docker uses `/app/modules`. Control write access to this root. |
| `PRAGMA_THEME_ACTIVE_ID` | `default` | Lowercase letters, numbers, hyphens, underscores; must start/end alphanumeric. |
| `PRAGMA_THEME_DEFAULT_ID` | `default` | Fallback theme id; same validation as active id. |

## Search and AI behavior

| Variable | Default | Notes |
| --- | --- | --- |
| `PRAGMA_SEARCH_ENABLE_SEMANTIC` | `false` | Enables semantic/vector strategy only when database capabilities and embeddings are available. |

Search degrades to keyword/fuzzy behavior when semantic prerequisites or provider calls are unavailable. AI provider settings are managed through privileged admin/API flows, not through a backend env table. Settings changes can require explicit embedding rebuilds.

## Realtime variables

| Variable | Default | Validation/behavior |
| --- | --- | --- |
| `PRAGMA_REALTIME_ENABLED` | `true` | Enables ticketed WebSocket realtime endpoints. |
| `PRAGMA_REALTIME_CHANNEL` | `pragma_realtime` | Lowercase letters, numbers, underscores; max 63 chars. |
| `PRAGMA_REALTIME_QUEUE_SIZE` | `256` | 1-2048. |
| `PRAGMA_REALTIME_RECONNECT_MIN_SECONDS` | `0.5` | Greater than 0. |
| `PRAGMA_REALTIME_RECONNECT_MAX_SECONDS` | `30.0` | Greater than 0 and not below min. |
| `PRAGMA_REALTIME_TICKET_TTL_SECONDS` | `60` | 5-600. |

## Logging

| Variable | Default | Notes |
| --- | --- | --- |
| `PRAGMA_LOG_LEVEL` | `INFO` | Backend logging level string. |

## Production proxy variables

Production compose also consumes proxy/build variables such as `VITE_API_BASE`, `PRAGMA_PROXY_PUBLISHED_HOST`, `PRAGMA_PROXY_PUBLISHED_PORT`, `PRAGMA_PROXY_LISTEN_PORT`, `PRAGMA_PROXY_CLIENT_MAX_BODY_SIZE`, websocket timeout variables, and `PRAGMA_SERVER_NAME`. See `docker/prod.env.example` for the operator template.

The example proxy host/port values are examples. Change them to match your deployment.

## Docker secret-file variables

Production Docker supports file-based alternatives for the two required secrets:

- `PRAGMA_DATABASE_PASSWORD_FILE` instead of `PRAGMA_DATABASE_PASSWORD`
- `PRAGMA_JWT_SECRET_KEY_FILE` instead of `PRAGMA_JWT_SECRET_KEY`

For each secret, set exactly one raw value or file path. The backend entrypoint and production validator reject raw+file conflicts and missing secret sources.

When using the documented production bind-mount override, set the container file paths to:

```env
PRAGMA_DATABASE_PASSWORD_FILE=/run/secrets/pragma_database_password
PRAGMA_JWT_SECRET_KEY_FILE=/run/secrets/pragma_jwt_secret_key
```

Then provide host-side source files for the override mounts:

```env
PRAGMA_DATABASE_PASSWORD_SECRET_SOURCE=./docker/secrets/pragma_database_password
PRAGMA_JWT_SECRET_KEY_SECRET_SOURCE=./docker/secrets/pragma_jwt_secret_key
```

Use `docker/docker-compose.secrets.yml` together with the base compose file so those two files are mounted read-only into `db`, `migrate`, and `backend`. Raw-env deployments do not use the override file.
