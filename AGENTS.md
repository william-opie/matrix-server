# AGENTS.md

Guidance for coding agents working in this repository.

## Scope

- This repo is a Docker Compose-based Matrix stack.
- Main components:
  - `scripts/` for config rendering and bootstrap automation.
  - `admin-api/` FastAPI service for admin actions.
  - `admin-ui/` static HTML/CSS/JS frontend served by nginx.
  - `config/` templates rendered into `runtime/`.
  - `docs/` operator and troubleshooting docs.

## Rule Files Check

- Checked for Cursor/Copilot rule files:
  - `.cursor/rules/`: not present.
  - `.cursorrules`: not present.
  - `.github/copilot-instructions.md`: not present.
- If any of these are added later, treat them as higher-priority instructions and update this file.

## Environment + Setup

- Copy env file before running anything:
  - `cp .env.example .env` (Linux/macOS)
  - `copy .env.example .env` (Windows cmd)
- Fill required values in `.env` (especially secrets and bootstrap admin values).
- Do not commit `.env` or generated secrets.

## Build / Run Commands

Primary workflow is Docker Compose.

- Start full stack:
  - `docker compose up -d`
- Rebuild/recreate after config changes:
  - `docker compose up -d --force-recreate`
- Pull updated images:
  - `docker compose pull && docker compose up -d`
- Stop stack:
  - `docker compose down`

Service-focused commands:

- Render runtime config only:
  - `docker compose run --rm config-renderer`
- Run bootstrap only:
  - `docker compose run --rm matrix-bootstrap`
- Tail logs:
  - `docker compose logs -f synapse`
  - `docker compose logs -f admin-api`
  - `docker compose logs -f admin-ui`

Local (non-docker) commands useful during development:

- Admin API dependencies:
  - `python -m pip install -r admin-api/requirements.txt`
- Run Admin API locally from repo root:
  - `uvicorn admin-api.app.main:app --host 127.0.0.1 --port 9000`
  - If import path fails, run from `admin-api/`:
    - `uvicorn app.main:app --host 127.0.0.1 --port 9000`
- Run config renderer:
  - `python scripts/render_configs.py`
- Run bootstrap script:
  - `python scripts/bootstrap_matrix.py`

## Lint / Format / Static Checks

There is no configured lint/format toolchain in this repo yet (no ruff/black/eslint/prettier config present).

Use lightweight checks that do not change behavior:

- Python syntax check:
  - `python -m py_compile scripts/render_configs.py scripts/bootstrap_matrix.py admin-api/app/main.py`
- Optional compile-all check:
  - `python -m compileall scripts admin-api/app`

If introducing a formatter/linter, add config files in the same PR and document commands here.

## Test Commands

Current state:

- No automated test suite is present (`tests/` and pytest config are absent).
- Validate changes using targeted smoke checks and container logs.

Suggested smoke checks after changes:

- API health endpoint (when running):
  - `curl http://127.0.0.1:9000/api/health`
- Stack health/log sanity:
  - `docker compose ps`
  - `docker compose logs --tail=100 admin-api`

If tests are added (recommended: pytest), use these conventions:

- Run all tests:
  - `pytest`
- Run one file:
  - `pytest tests/test_file.py`
- Run one test (important for agents):
  - `pytest tests/test_file.py::test_case_name`
- Run one test method in class:
  - `pytest tests/test_file.py::TestClass::test_case_name`

## Code Style Guidelines

Follow existing style in touched files; avoid broad rewrites.

### Python (`scripts/`, `admin-api/`)

- Imports:
  - Group in order: standard library, third-party, local.
  - One import per line for clarity when practical.
- Formatting:
  - 4-space indentation.
  - Keep lines readable; prefer wrapping long literals and calls.
  - Preserve existing quote style unless editing nearby code requires consistency.
- Types:
  - Use built-in generics (`dict[str, str]`, `list[str]`).
  - Use `| None` unions (Python 3.10+ style).
  - Add type hints on public functions and return values.
- Naming:
  - `snake_case` for functions/variables.
  - `PascalCase` for Pydantic models/classes.
  - `UPPER_SNAKE_CASE` for module-level constants/env keys.
- Error handling:
  - Raise explicit `HTTPException` in API handlers for user-facing errors.
  - Preserve exception chaining (`raise ... from exc`) when translating errors.
  - Catch narrow exceptions when possible; avoid blanket catches unless required.
- API conventions:
  - Keep request/response payload keys stable; avoid breaking API shape.
  - Validate input with Pydantic models and `Field` constraints.
- Side effects:
  - Keep DB writes explicit and close DB connections promptly.
  - Keep bootstrap/config scripts idempotent where possible.

### JavaScript/CSS/HTML (`admin-ui/`)

- JavaScript:
  - Use `const` by default; `let` only when reassignment is required.
  - Prefer `async/await` over chained promises.
  - Use `camelCase` for functions/variables.
  - Keep DOM IDs and API paths as constants if reused in new code.
  - Surface actionable errors to UI status area; do not silently swallow failures.
- CSS:
  - Reuse existing CSS variables in `:root` for colors and spacing.
  - Keep styles simple and component-oriented (`.card`, `.panel`, `.grid`).
  - Avoid introducing new design systems/frameworks for small changes.
- HTML:
  - Keep semantic structure and existing IDs stable (JS relies on them).
  - Preserve accessibility basics (`label`, input types, button types).

### Config + Docs

- Template files in `config/` should remain environment-driven.
- Generated runtime files belong under `runtime/`; do not hand-edit generated output unless required for debugging.
- Update docs in `docs/` and `README.md` when behavior or operator steps change.

## Security + Secrets

- Never hardcode real credentials, tokens, or private hostnames.
- Treat all `CHANGE_ME_*` values as placeholders only.
- Avoid logging secrets or full tokens.
- Keep Tailnet-only assumptions intact unless a task explicitly changes deployment scope.

## Agent Workflow Expectations

- Make minimal, targeted edits.
- Prefer small PR-ready diffs over broad refactors.
- Verify touched paths with the commands above before finishing.
- If adding tools (tests/lint/format), include:
  - config files,
  - updated commands in this file,
  - brief doc updates explaining usage.
