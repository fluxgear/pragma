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

## Lifecycle and API caveats

Module APIs are backend APIs under `/api/v1/modules` and require module-management permission. The current admin SPA does not expose a module-management route, so operators should not expect a complete graphical module lifecycle screen.

Because modules are filesystem-discovered Python code, treat module installation as an operator-controlled deployment action. Keep module roots writable only where required by your deployment model.
