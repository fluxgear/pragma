# Testing and validation

## Backend test command

Run backend tests from the repo root with the shipped helper:

```bash
./scripts/run-backend-tests.sh
```

The script runs backend pytest through `uv` with defaults `-n 32 --dist loadscope`, prevents concurrent backend pytest runs with a lock, and accepts optional targets/flags (for example `./scripts/run-backend-tests.sh tests/test_public.py`).

## Admin test and build commands

```bash
cd admin
npm run test
npm run build
```

`npm run test` runs Vitest. `npm run build` runs `vue-tsc --noEmit` and Vite production build.

## Pre-commit-equivalent gate

Run the shipped repo-level helper from the repo root:

```bash
./scripts/pre-commit-checks.sh
```

This runs backend Ruff, backend pytest via `scripts/run-backend-tests.sh`, admin Vitest, and the admin production build (when `admin/` exists).

## Docker config validation

Development DB compose config:

```bash
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example config >/dev/null
```

Production compose config with the example env plus an explicit operator-chosen published DB port override:

```bash
PRAGMA_DATABASE_PUBLISHED_PORT=15432 \
  docker compose -f docker/docker-compose.yml --env-file docker/prod.env.example config >/dev/null
```

## Production validation

For static production validation without booting the stack, copy the template, replace placeholder secrets with real raw secrets or file-secret settings, then validate the real env file:

```bash
cp docker/prod.env.example docker/prod.env
# edit docker/prod.env before running validation
./docker/validate-production.sh docker/prod.env
```

`docker/prod.env.example` intentionally contains placeholder secrets and is rejected by the hardened production validator.

Optional smoke validation builds and boots the compose stack, checks PostgreSQL 18/extension state and application endpoints, then cleans up the smoke stack:

```bash
PRAGMA_VALIDATE_SMOKE=1 ./docker/validate-production.sh docker/prod.env
```

Use smoke validation only when you have a real `docker/prod.env` and the configured ports are available.

## Retry policy note

If the backend suite fails, rerun failed tests with the same worker count first, then reduce workers only as part of the documented retry policy. Do not run concurrent pytest commands.

## Markdown/link checks

No markdown formatter or link-checker command is currently defined in the repository. For documentation changes, use `git diff --check` and manually review relative links in `README.md`, `backend/README.md`, and `docs/*.md`.
