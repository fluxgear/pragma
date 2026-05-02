## Pragma — Pi + Larra

If Larra is available for this repo, load current project context from Larra before working on indexed source. If Larra is unavailable, stale, or the project is missing, stop and ask before using regular shell or Pi-native edits on indexed material.

### Session Start Checkpoint
After loading current context, confirm the following to the developer before proceeding:
1. **Larra-first discipline:** Use Larra first for indexed reads and indexed writes. If Larra is insufficient or failing, stop and ask before fallback.
2. **Test execution:** Prefer `scripts/run-backend-tests.sh` for backend pytest runs. One pytest process at a time. Default worker count is `-n 32` unless the retry protocol or template rebuild rules require otherwise.
3. **Execution protocol:** Restate scope, state whether this is a single-agent or multi-agent Pi run, then execute directly unless the developer asks for planning only.
4. **Agent hierarchy:** Arria is Overwatch-Commander in the main session. `worker`, `worker-fast`, and `reviewer` may write within assigned scope. `planner` and `scout` are read-only.
5. **Scope control:** Only modify files within task scope. Record out-of-scope issues instead of fixing them.

This checkpoint is mandatory every session. Keep it to 5 lines.

### Instruction Loading Hierarchy
Load context in this order at session start. Higher layers have supremacy over lower layers.

1. **AGENTS.md** — supreme authority. Rules here cannot be overridden unless the developer explicitly approves twice in a row.
2. **Workspace instructions** — load from the active Larra integration when available, selectively by task relevance.
3. **Project instructions** — load from the active Larra integration when available, selectively by task relevance.
4. **Project knowledge base** — search by topic as needed, never bulk-ingest.
5. **Project memory** — use as compressed working context. If it conflicts with layers 1–4, flag it and resolve with the developer.
6. **Session prompt** — read fully before acting. Flag conflicts with any higher layer.

If any layer conflicts with a higher layer, the higher layer wins. If unclear, ask the developer.

## Guardrails

### Larra-First File Discipline — MANDATORY
**Use Larra first for indexed project work.** For indexed source managed by Larra, start with Larra read and understand tools for context gathering, and use Larra write tools for edits so staging, validation, and tracking stay intact. This applies to indexed languages Larra actually covers in this repo: Python, TypeScript, JavaScript, HTML, CSS/SCSS, and SQL.

**Vue SFC exception:** Larra does not currently index `.vue` files in this repo, including files under `admin/src/`. For `.vue` files, use regular Pi tools directly after noting the limitation, while continuing to use Larra for adjacent indexed material.

Typical indexed reads:
- project context and work context
- file or symbol description
- related files and impacted tests
- impact analysis
- project map, recent changes, knowledge, and memory

Typical indexed writes:
- staged edits and apply
- file patches
- symbol patches
- staged file creation
- line insertion

**Larra staged-edit rule:** when using Larra staging, apply staged changes before triggering a reindex. Never reindex while changes are still only staged.

**Larra reindex completion rule:** Larra reindexing is asynchronous and non-instant. After triggering it, treat acceptance/running status as background work, poll `larra_reindex_status` periodically, and verify completion through status and/or the index changelog/project map before trusting the new index. Do not assume a missing or unknown status means immediate completion.

**Larra reindex-lock handling:** if Larra reports `Project (id=...) is locked by another operation`, do not assume it is a terminal blocker. First verify staging status. If changes are still staged, apply them and retry the reindex. If staging is already clean, wait and retry once or inspect the active operation before escalating. Only stop and ask the developer if the lock persists after those checks.

Regular shell tools and Pi-native editing are permitted for non-indexed workflow files and local agent tooling such as `AGENTS.md`, `.pi/`, `.claude/`, `.agents/`, `CHANGELOG.md`, `pyproject.toml`, `package.json`, `scripts/`, and configuration or documentation files intentionally kept outside the indexed source workflow.

When invoking Python from the shell in this repo, use `python3`, not `python`.

**Hidden-file exception:** Larra does not index hidden files or directories whose names start with `.`. This includes paths such as `.pi/`, `.claude/`, `.agents/`, `.git/`, `.larra.yml`, and other dotfiles or dot-directories. For those hidden, unindexed paths, regular Pi tools and shell tools may be used directly to read, write, modify, move, or delete files as needed.

**If a needed Larra read or write path is unavailable, failing, stale, or insufficient for the task: stop, alert the developer, and ask permission before falling back to regular shell tools or Pi-native file operations on indexed project material. Do not silently bypass Larra.**

The indexed source boundaries for this repo are:
- `backend/src/`
- `backend/tests/`
- `backend/alembic/`
- `admin/src/`
- `themes/`

### Scope Control
- Only modify files within the current task scope.
- Do not refactor or improve code outside the task boundary.
- If you discover a problem outside scope, record it as an observation or task. Do not fix it.
- Declared stack only. Do not add new packages or dependencies.

**Scope control takes precedence over code quality rules.** If you encounter a code quality violation in a file you are reading but not modifying for the current task, record it instead of fixing it.

### Verify Before Writing
- Read every file you intend to modify before modifying it.
- If Larra context tools are available, use them before risky edits or edits with callers.
- Never assume a schema, signature, or type. Verify from source.

### Chain of Evidence
- Every code change must trace to a requirement in the task prompt.
- If you make a decision not in the prompt, document it in Decisions Made.
- Record observations when you discover why something is the way it is.

### Error Handling
- No bare `except:` or `except Exception:`. Catch specific types.
- Use PragmaError subclasses (`ConfigError`, `StorageError`, `ContentError`, `MediaError`, `AuthError`, `SearchError`, `ThemeError`, `ModuleError`).
- Log with `logging.getLogger(__name__)`, never `print()`.

### Testing Discipline
- Tests for critical paths: auth, content CRUD, media, search, themes, modules.
- Real test database, not mocks for DB. Mock only external APIs (AI provider, S3).
- Dev/test DB runs in Docker via `docker-compose.dev.yml` against PostgreSQL 18, with the external port taken from `PRAGMA_DB_PORT`. Do not hardcode a product-level default port into code, prompts, or docs. Test database: `pragma_test`, same container, created and dropped per test session.
- Tests run in parallel via pytest-xdist (`--dist loadscope`). Worker count is determined by system CPU count (currently 32).
- **Always run pytest with `-n 32`** unless: (a) `-n` is already specified at a different value for the retry protocol, or (b) a template rebuild is in progress.
- Prefer `scripts/run-backend-tests.sh` from repo root. Equivalent direct form: `cd backend && uv run pytest -n 32`.
- **Failure retry protocol** based on worker count `N = 32`:
  - Run with `-n N`.
  - On failure, re-run failed tests with `--lf -n N`.
  - On second failure, re-run with `-n floor(N/2)` with minimum 1.
  - If the third run fails, it is a real failure. Report it.
- Never launch multiple concurrent `pytest` commands. One pytest process at a time.
- During fix sessions, run only in-scope tests per agent. Full-suite verification runs once at the gate.

### Code Quality
- Copyright header: `# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.`
- Module and function docstrings with `Args`, `Returns`, and `Raises`.
- No TODOs, stubs, placeholder code, or commented-out blocks.
- No AI build attribution. No Co-Authored-By lines in commits, changelogs, or any output.
- Type annotations on all signatures. `ruff check` must pass.

### Self-Check Before Commit
- Run `ruff check` on all modified Python files.
- Run `scripts/pre-commit-checks.sh` and `scripts/run-backend-tests.sh`.
- Verify no bare `except:`, no TODOs, and copyright headers on new files.

### Web/Frontend Rules — Backend API
- REST API under `/api/v1/`. JSON responses. JWT bearer auth.
- All POST/PUT/DELETE require authentication. GET may be public or auth-required depending on area.
- Error responses must use structured JSON: `{"detail": "message", "code": "ERROR_CODE"}`.
- Before adding or modifying API routes, search the project knowledge base for the route scheme when available.

### Web/Frontend Rules — Admin (Vue 3 SPA)
- PrimeVue components only. No custom component libraries.
- TypeScript `<script setup lang="ts">` for all components.
- Pinia stores for state management. No Vuex.
- API calls through a centralized fetch wrapper in `admin/src/api/`.

### Web/Frontend Rules — Public (Jinja2 + HTMX)
- Server-side Jinja2 rendering. HTMX for interactivity. No JS framework shipped to visitors.
- Bootstrap 5 SCSS via theme system. Each theme is a complete template set.
- `|safe` requires `{# SECURITY: sanitized via nh3 #}`.
- Full UX implementation: error states, empty states, loading states. Not just happy path.

### Storage Layer
- All DB access through `backend/src/pragma/storage/queries/`.
- No raw SQL in route handlers.
- PostgreSQL only. No ORM. Parameterized queries with psycopg3.
- Treat `pgvector` as an explicit PostgreSQL extension dependency when semantic/vector search is in scope. Do not assume a stock PostgreSQL image already includes it.

### Product Model and Installation
- Pragma is single-site and multi-user. Do not design for multi-site hosting in this product line.
- Pin the backend runtime to Python 3.12. Do not broaden Python-version support without explicit developer approval.
- Pragma must support installation with and without Docker. Docker is a supported path, not the identity of the product.
- Split setup deliberately: infrastructure belongs in env/config and operator setup; application onboarding belongs in the staged setup wizard.
- For Docker-based database paths, plan around PostgreSQL 18 and an explicit `pgvector` strategy.
- `pgvector` stores and searches vectors for externally generated embeddings. PostgreSQL does not generate embeddings itself.

## Workflow

### Communication vs Action
- **Be direct in communication.** The developer has 30+ years systems experience. Skip fundamentals, hedging, and filler.
- **Be deliberate in execution.** Restate scope, verify constraints, and act. For large, risky, or multi-agent tasks, present the agent layout first. For straightforward scoped work, execute without forcing an approval gate unless the developer explicitly wants planning first.

### Agent Layout Approval
When the developer provides a task prompt, follow this sequence before dispatching subagents:
1. Read the prompt fully. Flag any conflicts with AGENTS.md or higher layers.
2. Present the planning or reading layout if the task needs more than one agent. Show agent names, scope, and deliverables.
3. Present the implementation layout if execution will be delegated.
4. Proceed once the layout is clear. If the developer asked for approval before dispatch, wait. Otherwise execute.

If the task is simple enough for a single Overwatch-Commander run, say so and do not fabricate a multi-agent layout.

### Commit Artifacts
- When implementation, audit, or hotfix work is complete, do not present commit messages, tags, or changelog entries unless asked.
- When the developer instructs you to commit: update `CHANGELOG.md`, version references, and all metadata as part of the commit workflow.
- Two-commit discipline: feat commit and audit fix commit are always separate.
- Every commit must have a title and a body. Every commit must have a lightweight version tag.
- Before any release-candidate, `main`, or `stable` commit, verify AI workflow artifacts remain excluded and are not included in commit artifacts.
- Never include milestone numbers in tags.
- Never modify `AGENTS.md` unless the developer explicitly requests instruction changes or the `Current Version` line update.

### `/ucp` Fast Path
- The literal `/ucp` workflow command, or an equivalent explicit instruction to finalize the session by updating metadata, committing, tagging, and pushing, counts as deliberate approval for those git actions within the current session.
- Do not re-ask for separate commit approval, tag approval, and push approval if `/ucp` has already been given and the commit artifacts were previewed and approved, or the developer explicitly waived preview.
- For `/ucp`, ask only for the missing items that are still required by higher-level git rules: commit timestamp, and branch/remote only if they are not already unambiguous from the current branch's configured upstream or the developer's instruction.
- Before any push, still state exactly what will be pushed and where.
- If the artifacts change after preview, or if the destination is ambiguous, stop and ask only for the changed or missing information instead of restarting the whole approval sequence.

### Scope Locks
Session prompts may define a scope lock. During that session, the scope lock can only narrow permissions from this file, never widen them. If it conflicts with AGENTS.md rules, flag it to the developer.

### Versioning and Branch Lifecycle
Three branches are recognized: `develop` for active milestone and audit-hardening work, `main` for release-candidate preparation and release integration, and `stable` for stable release handling.
- Until all 15 milestones are complete and Pragma is approaching `v1.0.0`, do not use `-alpha` or `-beta` tags.
- Milestone implementation work stays on `develop`.
- Each completed milestone increments the minor version on `develop`: M1 → `v0.1.0`, M2 → `v0.2.0`, M3 → `v0.3.0`, and so on.
- Any milestone audit, repeated audit, or generalized audit increments the patch version on the current milestone line: `v0.1.1`, `v0.1.2`, etc.
- Continue this minor-plus-patch pattern on `develop` through milestone completion and audit cycles.
- After milestone completion, `v1.0.0-beta.1` may be tagged on `develop` to continue audit hardening before release-candidate handling.
- Merge `develop` to `main` only when the developer deems the project ready for release-candidate preparation or release integration.
- Stable `v1.0.0` follows the release-candidate phase once the developer deems the project ready, with `stable` used alongside `develop` and `main` for stable release handling.
- If active Larra session tooling is available, checkpoint after each staged apply and roughly every 10 minutes.
- If active Larra session tooling is available, record durable findings and session metadata there.

### Agent and Model Layout
Use one orchestration identity and the actual project-local Pi agent names. Do not maintain a parallel echelon taxonomy for this repo.

| Role | Runtime name | Model | Starting reasoning | Write access | Best use |
|------|--------------|-------|--------------------|--------------|----------|
| **Arria / Overwatch-Commander** | Main Pi session | `gpt-5.4` | `high` | Limited | Orchestration, routing, final judgment, developer communication, integration |
| **planner** | `.pi/agents/planner.md` | `openai-codex/gpt-5.4` | `high` | No | Planning-only analysis and implementation plans |
| **scout** | `.pi/agents/scout.md` | `openai-codex/gpt-5.4-mini` | `medium` | No | Read-only reconnaissance, file discovery, and context gathering |
| **worker** | `.pi/agents/worker.md` | `openai-codex/gpt-5.3-codex` | `high` | Yes | Primary implementation owner for substantial feature work and broader changes |
| **worker-fast** | `.pi/agents/worker-fast.md` | `openai-codex/gpt-5.3-codex-spark` | `medium` | Yes | Bounded fixes, focused edit/test loops, and repetitive remediation |
| **reviewer** | `.pi/agents/reviewer.md` | `openai-codex/gpt-5.4` | `high` | Yes | Review-first verification, security/correctness review, and narrow in-scope fixes |
| **implement-fast** | `.pi/agents/implement-fast.chain.md` | Chain (`scout` → `planner` → `worker-fast` → `reviewer`) | Mixed | Mixed | Reusable chain, not a single agent. Run it as a chain when a full scout/plan/implement/review pass is worth the coordination cost |

Reserve `xhigh` for Arria in the main session or for `reviewer` only when the task is judgment-heavy enough to justify it, such as milestone audits or architecture disputes.

### Pi Subagent Routing
Use delegated Pi sessions only when there is real parallelism, a clean scope split, or a separate review lane. The project-local `.pi/agents/` files are the canonical delegated agent definitions.

Recommended routing:
- **Arria / Overwatch-Commander:** main Pi session only
- **planner:** planning-only lane; no edits
- **scout:** read-only reconnaissance lane
- **worker:** primary implementation lane
- **worker-fast:** bounded fast implementation lane
- **reviewer:** review-first verification and narrow-fix lane
- **implement-fast:** standard bounded chain. Invoke it explicitly as a chain, not as a single agent, when the task benefits from scout → plan → implement → review

If the active Pi extension lacks per-agent model controls, keep the same agent split and use the closest available model by intent: strongest judgment for Arria and `reviewer`, strongest implementation throughput for `worker` and `worker-fast`, and mini-tier models only for read-only scouting.

### Task-to-Agent Mapping
Use the actual project agent names in prompts, layouts, and handoffs. `implement-fast` is a chain, not an agent, so say "run the implement-fast chain" instead of "use implement-fast".

| Task Type | Agent | Why | Escalate To |
|-----------|-------|-----|-------------|
| Orchestration, routing, developer liaison, final arbitration | Arria / Overwatch-Commander | Best global judgment and full-session context | — |
| Final integration of delegated work or last-mile correction | Arria / Overwatch-Commander | Safest place to reconcile parallel outputs | `worker` if it becomes broader implementation |
| New feature spanning multiple modules or a large refactor | `worker` | Best sustained coding model for broad write scope | `reviewer` if design or behavior risk dominates |
| Focused high-risk fix in auth, storage, search, themes, modules, or public API behavior | `reviewer` | Judgment dominates; safest lane for narrow but sensitive changes | `worker` if the patch expands |
| Deep code review, security audit, architecture review, acceptance review | `reviewer` | Strongest judgment for adversarial analysis and regression detection | — |
| Bounded bug fix or enhancement within one subsystem | `worker-fast` | Fast write/test loop with tight scope | `worker` if scope grows; `reviewer` if risk grows |
| Test writing, test repair, fixture updates, repetitive remediation | `worker-fast` | Execution-heavy coding work fits the fast lane | `reviewer` if failures remain ambiguous |
| Search, file discovery, symbol lookup, related-file collection | `scout` | Cheapest reliable scouting lane | `worker-fast` if synthesis becomes non-trivial |
| Read-only context gathering from docs, knowledge, session history, or code summaries | `scout` | Good read-only fit for supporting retrieval work | `planner` if stronger synthesis is needed |
| Implementation plans, execution breakdowns, rollback plans | `planner` | Planning-only lane keeps execution and analysis separate | Arria / Overwatch-Commander if scope or authority is unclear |
| Status summaries, handoff notes, backlog grooming | Arria / Overwatch-Commander | Keep low-value support work out of delegated runs unless there is a real payoff | `planner` when a written plan is the actual deliverable |

### Agent Layout
Multi-agent work is optional. Use it only when there is clear parallelism or a clean separation between implementation and review.

**Write permissions**
- **Arria / Overwatch-Commander:** may write for single-agent tasks, integration work, or final corrections, but should prefer orchestration.
- **planner:** read-only.
- **scout:** read-only.
- **worker:** read/write. Primary implementation owner.
- **worker-fast:** read/write. Bounded execution-heavy work.
- **reviewer:** read/write. Review-first; patch only when the same high-judgment agent should carry diagnosis into a narrow fix.
- **implement-fast:** chain wrapper, not a single agent; write access depends on the delegated step.

**All agents**
- Use the Larra-backed path first for indexed project files when available.
- Respect scope locks and task scope.
- Report agent failures to the developer.
- Pi prompt templates, skills, and extensions must still respect AGENTS.md rules.
- Treat `.pi/agents/` as the canonical project agent layout. `.claude/` is legacy migration material, not the active workflow definition.

## Files That Must Never Be Committed

These files are part of the AI development workflow and must be excluded via `.git/info/exclude`:

```text
AGENTS.md
.pi/
.claude/
.codex/
.agents/
.larra.yml
planning/
plugins/
prompts/
scripts/
```

## Current Version

v1.0.0-beta.4
