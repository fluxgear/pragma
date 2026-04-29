# Setup wizard

The setup wizard is application onboarding. It does not install PostgreSQL, create extensions, or run Alembic migrations.

## When setup appears

The admin router sends users to `/setup` whenever the backend install status says the application is not installed. Once installation is complete, `/setup` redirects into the normal login/dashboard flow.

## Backend endpoints

All setup endpoints are under `/api/v1`:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/install/status` | Returns `schema_ready`, `is_installed`, `superuser_exists`, and extension capability status. |
| `GET /api/v1/system/ready` | Checks database connectivity, schema state, and PostgreSQL capability details. |
| `POST /api/v1/install/bootstrap` | Creates the first administrator and marks the install complete. |

## Readiness dependency

The admin install store checks install status and system readiness before bootstrap. If the schema is not ready or the backend cannot reach PostgreSQL, complete database setup and migrations first.

## Bootstrap payload

`POST /api/v1/install/bootstrap` accepts:

```json
{
  "email": "admin@example.test",
  "username": "admin",
  "password": "change-this-long-password",
  "full_name": "Site Administrator"
}
```

Validation rules implemented by the backend include:

- `email`: 3-320 characters
- `username`: 3-64 characters
- `password`: 12-512 characters
- `full_name`: optional, up to 255 characters

## First administrator result

Successful bootstrap returns HTTP 201 with `installed: true` and the created user. The first user is a superuser and is assigned the built-in `administrator` role.

Bootstrap is single-use. Once the install is complete or a superuser already exists, create and manage additional users through authenticated admin APIs and the admin UI.

## Post-setup login

After bootstrap, sign in through `/login`. The admin SPA then uses `/api/v1/auth` session endpoints and permission-aware routes for `/app`, `/app/content`, `/app/media`, `/app/ai`, `/app/users`, and `/app/account`.
