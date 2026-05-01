# Testing and validation

## Backend test entrypoint

Use the repository wrapper from the repo root:

```bash
scripts/run-backend-tests.sh
```

The wrapper changes into `backend/`, acquires the shared backend pytest lock, adds `--dist loadscope` when not supplied, adds `-n 32` when not supplied, and runs `uv run pytest`. By default, a simultaneous backend pytest run fails fast; set `PRAGMA_BACKEND_TEST_LOCK_WAIT=1` to wait indefinitely or `PRAGMA_BACKEND_TEST_LOCK_WAIT=<seconds>` to wait with a timeout.

## Admin test and build commands

```bash
cd admin
npm run test
npm run build
```

`npm run test` runs Vitest. `npm run build` runs `vue-tsc --noEmit` and Vite production build.

## Pre-commit gate

```bash
scripts/pre-commit-checks.sh
```

This runs backend Ruff (`uv run ruff check .`), a fast backend pytest gate through `scripts/run-backend-tests.sh` (default target `tests/test_conftest.py`, override with `PRAGMA_PRE_COMMIT_BACKEND_TEST_TARGET`), and, when `admin/` exists, the admin Vitest suite plus production build.

## Docker config validation

Development DB compose config:

```bash
docker compose -f docker/docker-compose.dev.yml --env-file docker/dev.env.example config >/dev/null
```

Production compose config with the example env:

```bash
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
