# Modules and themes

## Theme discovery and configuration

Themes are discovered from `PRAGMA_THEME_ROOT`. The active and default themes are selected by `PRAGMA_THEME_ACTIVE_ID` and `PRAGMA_THEME_DEFAULT_ID`; both ids are normalized and validated by backend settings/runtime code.

The default local root is `../themes` relative to the backend. Production Docker uses `/app/themes`.

## Default theme

A default theme is checked in at `themes/default` with `theme.json` plus templates for home, page, post, archive, search, 404, and shared layout. The default theme id is `default`.

## Theme structure

At a high level, a theme directory contains:

- `theme.json` manifest with id, name, version, description, author, and optional template/static directory settings.
- Template files under the theme's templates directory.
- Static assets under the theme's static directory when present.

Template/static paths must stay relative to the theme directory; absolute paths and parent traversal are rejected. Runtime lookup tries the active theme and falls back to the default theme.

There is no implemented admin UI for selecting, editing, installing, or deleting themes. Configure theme roots and ids through environment/settings.

## Module discovery and configuration

Modules are discovered from `PRAGMA_MODULE_ROOT`. The default local root is `../modules`; production Docker uses `/app/modules` and mounts a named `modules` volume.

No bundled modules or example modules are currently checked in. The repository implements the backend runtime/API surface, not a packaged module catalog.

## Module manifest and runtime behavior

A module manifest defines metadata such as id, name, version, description, author, load order, entrypoint, and hooks. Module ids are normalized to lowercase and may use letters, numbers, hyphens, and underscores. Entrypoints must be relative paths within the module root.

The runtime discovers manifests, loads persisted enablement state from PostgreSQL, imports enabled module entrypoints, binds content-entry hooks, and dispatches hooks in deterministic order. Hook failures are isolated and logged instead of being allowed to crash core content operations.

## Trusted operator-code boundary

Modules are trusted operator-installed Python code. When an enabled module is imported, its entrypoint executes inside the backend process with the same application privileges as Pragma code. Hooks also run in-process when dispatched. This is not a sandbox, permission boundary, or isolation mechanism against malicious module code.

Set `PRAGMA_MODULE_TRUST_STRICT=true` to reject enabled module loading when trust diagnostics find unsafe module paths. Strict mode does not sandbox Python code; it only prevents Pragma from importing enabled modules whose module root, manifest, or entrypoint is group/world writable, cannot be inspected, or is not owned by the backend process user on platforms that expose ownership. In advisory mode (`false`, the default), the same diagnostics are logged and module loading continues to preserve Docker named-volume deployments.

Only install modules from trusted sources, and control write access to `PRAGMA_MODULE_ROOT` at the host, volume, or deployment layer. A writable module root is equivalent to the ability to run backend Python code, including reading process-accessible secrets or changing process state. Docker production uses a named `modules` volume for `/app/modules`; keep the deployment process that writes that volume operator-controlled rather than world-writable.

Pragma logs a warning whenever it loads an enabled module entrypoint so operators can diagnose when trusted executable module code enters the process. Filesystem mode checks are advisory rather than enforced because supported Docker named-volume deployments may not expose uniform host permissions.

## Lifecycle and API caveats

Module APIs are backend APIs under `/api/v1/modules` and require module-management permission. The current admin SPA does not expose a module-management route, so operators should not expect a complete graphical module lifecycle screen.
