# Testing and validation

## Backend test entrypoint

Use the repository wrapper from the repo root:

```bash
scripts/run-backend-tests.sh
```

The wrapper changes into `backend/`, adds `--dist loadscope` when not supplied, adds `-n 32` when not supplied, and runs `uv run pytest`. Run one pytest process at a time.

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

This runs backend Ruff (`uv run ruff check .`) and, when `admin/` exists, the admin production build. It does not run the backend pytest suite.

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

For static production validation without booting the stack:

```bash
./docker/validate-production.sh docker/prod.env.example
```

For a real production env file:

```bash
./docker/validate-production.sh docker/prod.env
```

Optional smoke validation builds and boots the compose stack, checks PostgreSQL 18/extension state and application endpoints, then cleans up the smoke stack:

```bash
PRAGMA_VALIDATE_SMOKE=1 ./docker/validate-production.sh docker/prod.env
```

Use smoke validation only when you have a real `docker/prod.env` and the configured ports are available.

## Retry policy note

If the backend suite fails, rerun failed tests with the same worker count first, then reduce workers only as part of the documented retry policy. Do not run concurrent pytest commands.

## Markdown/link checks

No markdown formatter or link-checker command is currently defined in the repository. For documentation changes, use `git diff --check` and manually review relative links in `README.md`, `backend/README.md`, and `docs/*.md`.
