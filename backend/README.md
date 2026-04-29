# Pragma Backend

The Pragma backend is the FastAPI package for the PostgreSQL-native CMS. It serves the `/api/v1` REST API, setup/bootstrap endpoints, authenticated admin data, local media files, optional search/AI integration, modules, realtime WebSockets, and the backend-rendered public site.

The package metadata in `pyproject.toml` publishes this file as the backend package README; the full operator and contributor documentation lives at the repository root.

## Requirements

- Python 3.12
- `uv` for dependency sync and command execution
- PostgreSQL 18 with `pg_trgm` and `vector`/pgvector available

## Local backend setup

From the repository root:

```bash
cp backend/.env.example backend/.env
cd backend
uv sync --dev
```

Edit `backend/.env` for your database and secrets. The sample host and port values are examples, not requirements.

Run migrations:

```bash
cd backend
set -a && . ./.env && set +a
uv run alembic upgrade head
```

Run the API/public frontend server:

```bash
cd backend
set -a && . ./.env && set +a
uv run uvicorn pragma.app:create_app --factory --host 127.0.0.1 --port 8000 --proxy-headers
```

Run backend tests from the repository root with the supported wrapper:

```bash
scripts/run-backend-tests.sh
```

## More documentation

- Root overview: [`../README.md`](../README.md)
- Installation: [`../docs/installation.md`](../docs/installation.md)
- Configuration: [`../docs/configuration.md`](../docs/configuration.md)
- Development: [`../docs/development.md`](../docs/development.md)
- Deployment: [`../docs/deployment.md`](../docs/deployment.md)
