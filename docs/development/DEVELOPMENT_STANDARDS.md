# Development Standards

The rules the code and CI enforce, and the conventions the tree consistently follows. The
principles themselves live in [CLAUDE.md](../../CLAUDE.md) (Principles, Patterns, Critical
Invariants); this page adds the how and the why, and names the gate behind each rule.

Related: [REPOSITORY_PATTERN.md](REPOSITORY_PATTERN.md) (database access),
[API_DESIGN_GUIDELINES.md](API_DESIGN_GUIDELINES.md) (REST shape),
[TESTING_GUIDELINES.md](TESTING_GUIDELINES.md) (writing tests),
[TEST_EXECUTION_GUIDE.md](TEST_EXECUTION_GUIDE.md) (running tests and the baselines).

## Gates at a glance

| Rule | Gate | Runs in |
|------|------|---------|
| Module size, 300 lines | `scripts/check_loc_ratchet.py` + `loc-ceilings.json` | `backend-tests.yml`, job `gates` |
| No history breadcrumbs, no line-number anchors in source | `scripts/check_breadcrumbs.py` | `backend-tests.yml`, job `gates` |
| Unused imports, redefinitions, unused locals | `ruff --select F401,F811,F841` (pinned in the workflow and in `.pre-commit-config.yaml`) | `backend-tests.yml`, job `gates`; pre-commit |
| Tests that assert nothing | `scripts/check_weak_assertions.py` (and `--zero`) | `backend-tests.yml`, job `gates` |
| Python types | `mypy` (config in `pyproject.toml`) | pre-commit; run by hand before a PR |
| Frontend types | `pnpm run type-check:prod` and `pnpm run type-check` | `frontend-typecheck.yml` (both must be clean) |
| Frontend tests that assert nothing | `pnpm run test:weak` (`scripts/check-weak-tests.mjs`) | `frontend-test.yml` |
| Doc path references and links | `.claude/commands/_audit-validate.sh` | `path-references.yml` |
| Test failures only ever shrink | `pytest-baseline.json`, `pytest-slow-baseline.json`, `test-baseline.json` | see [TEST_EXECUTION_GUIDE.md](TEST_EXECUTION_GUIDE.md) |

Every ratchet works the same way: a checked-in list records what is already wrong, a run fails
on anything not in the list, and the list may shrink but never grow. A ratchet that cannot be
met by fixing the code is a signal to split or fix, never to raise the number.

## Module size

Shipped modules stay under 300 lines (`auralis/`, `auralis-web/backend/`,
`auralis-web/frontend/src/`; tests, mocks, scripts and the Rust crate are out of scope).

`scripts/check_loc_ratchet.py` enforces it two ways:

- A file listed in `loc-ceilings.json` may not exceed the line count recorded there. The listed
  files are split targets that were closed once and tend to regrow a few lines at a time. A
  ceiling is written at the file's measured size, not at 300, so a 58-line file cannot quadruple
  unnoticed.
- A product file not in the list that passes 300 lines fails. Either split it, or enrol it in
  `loc-ceilings.json` at its exact size as a not-yet-split offender.

```bash
python scripts/check_loc_ratchet.py           # verify
python scripts/check_loc_ratchet.py --list    # current size against ceiling
python scripts/check_loc_ratchet.py --update  # lower ceilings to current sizes
```

When a split creates a new module, enrol it in the same commit. When a file shrinks, run
`--update`. A file that needs more room is split again; the ceiling does not go up.

The split pattern is the coordinator pattern: the original class keeps its public surface and
becomes a thin delegator, and the bodies move to sibling modules that take the host as their
first argument. `auralis/core/hybrid_processor.py` with `auralis/core/processing/mode_dispatch.py`
is an example. A host that is composed of mixins follows the next section.

### Mixin host hooks

A mixin that calls a method its composed host provides declares it as a bare class-level
annotation with a comment naming the provider. It does not define a
`raise NotImplementedError` stub: a runtime stub sits in the MRO ahead of the sibling mixin that
really implements the method and shadows it, and it reads as unfinished work.

```python
class PlayerQueueNavigationMixin:
    # Provided by PlayerFileLoadingMixin.
    load_file: Callable[[str], bool]
    load_track_from_library: Callable[[int], bool]
```

Source: `auralis/player/player_queue_navigation_mixin.py`.

## Comments, docstrings and deferrals

### Present tense, no history

A comment describes what the code does and why, now. Git carries the history. Do not write
"X was removed in #1234", "now-deleted", "went with #N", "is retired (#N)" or "removed following
#N" in source. `scripts/check_breadcrumbs.py` scans `auralis/`, `auralis-web/backend/`,
`auralis-web/frontend/src/` and `vendor/auralis-dsp/src/` and fails on those phrasings. Test
files are held only to the plainest form ("was removed in #N"), because a test docstring may
legitimately record which issue removed what it guards.

A constraint is fine: "Do not re-add X: <reason>" states a present-tense rule and does not match.
An issue number in a comment is fine when it explains why the code looks the way it does.

### No line-number anchors

Never pin a reference to a line number (a path followed by `:` and a number) in source comments or in docs. It goes stale on the next edit of that
file. `check_breadcrumbs.py` rejects the form in source, and the path-reference gate rejects it in
docs. Cite a symbol (`module.function`, `<file>.py::<Symbol>`) instead.

### Deferrals are greppable

A deferred decision is written `# TODO(#NNNN): ...` with a real, open issue number. Prose such as
"for now" or "temporarily" is invisible to a marker sweep. A marker that cites a closed issue is
itself a defect. Shipped code (`auralis/`, `auralis-web/`, `vendor/`) carries a handful of these;
`tests/` carries none. See `auralis/core/processing/parameter_generator_eq.py` for the form.

### Docstrings

Every module opens with a docstring that states its single responsibility and carries the
licence line:

```python
"""
Mode Dispatch
~~~~~~~~~~~~~

What the module does, and what it deliberately does not.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""
```

The CI path-reference job rejects GPL-v3 licence text, so copy that line verbatim. Public
functions use Google-style `Args:` / `Returns:` / `Raises:` sections; comments explain why, not
what.

## Python

### Types

- `mypy` is strict for `auralis.*` and for the backend's `services.*` and `cache.*` packages
  (`[[tool.mypy.overrides]]` in `pyproject.toml`); the remaining backend modules are checked under
  the top-level flags (`disallow_untyped_defs`, `check_untyped_defs`, `warn_unreachable`, and
  others). Run `mypy auralis/ auralis-web/backend/ --ignore-missing-imports`.
- Annotations use built-in generics and `X | None` (Python 3.14), not `typing.List` / `Optional`.
  Import from `typing` only what lives there (`Any`, `Protocol`, `TypeVar`, `TYPE_CHECKING`).
- Annotations are deferred by PEP 649, so a self-referential return type needs no string quotes
  or `from __future__ import annotations`. The codebase relies on this; backend CI must stay on
  Python 3.14.
- Do not silence a type error with a bare `# type: ignore`. `warn_unused_ignores` is on, so a
  stale ignore is itself an error. Fix the annotation or narrow the type.

### Style

`black` (line length 88, `py314`), `isort` (black profile), `mypy` and `pylint` run from
`.pre-commit-config.yaml`; configuration is in `pyproject.toml`. The ruff step is deliberately
narrow (`F401,F811,F841`): the rules that are always safe to fix. Pre-commit runs it on
`auralis/`, `auralis-web/backend/`, `scripts/` and `tools/`, and CI runs the same check on the
same trees.

### Logging and errors

- Library code logs through `auralis.utils.logging` (`debug`, `info`, `warning`, `error`), not
  `print` and not a private logger. Log values that come from a client or a file through
  `sanitize_log_value`, and use `absolute_paths_to_file_names` before writing a path to a log
  line; user home directories do not belong in logs.
- Engine errors are `ModuleError` with a `Code` (`auralis/utils/logging.py`).
- Router handlers are `async def`, decorated with `@with_error_handling("<operation>")`
  (`auralis-web/backend/routers/dependencies.py`). It passes `HTTPException` through and converts
  everything else to a standard 500. A handler does not hand-roll `try/except` around its body.
  Reach services through the `require_*` helpers in the same module, which raise a 503 when a
  service is not up.
- Validate input at the boundary, before processing starts, and fail fast with a typed error. Do
  not swallow an exception to keep going; log it and re-raise or return a typed failure.

### Concurrency

Shared state is protected by a lock (`threading.RLock()` for player state). Moving code between
modules does not change lock order or scope; the mixin docstrings under `auralis/player/` record
this where it matters. A test that exercises threads bounds every wait and marks its threads
`daemon=True` so a hang cannot block process exit.

### Audio invariants

The invariants in CLAUDE.md (sample count preserved, NumPy arrays only, float32 or float64,
copy before modify) are the standard for any DSP change. `tests/auralis/test_audio_processing_invariants.py`
asserts them; extend it when adding a stage. Chunk geometry comes only from
`auralis-web/backend/core/chunk_boundaries.py`; do not restate `CHUNK_DURATION` or the overlap in
another module.

## Database

All access goes through `auralis/library/repositories/`; no raw SQL outside the migration engine.
[REPOSITORY_PATTERN.md](REPOSITORY_PATTERN.md) owns the details: session lifecycle, factory,
query rules. The points that bite:

- Eager-load every relationship a read path hands back, with `selectinload` (define the option
  tuple once at module scope). Repositories `expunge()` what they return, so an unloaded
  relationship raises `DetachedInstanceError` later. `to_dict()` reads relationships through
  `_safe_collection()` / `_safe_scalar()` in `auralis/library/models/_helpers.py`, which degrade
  to `[]` / `None` and log a warning naming the missing eager-load.
- Load collections and many-to-many relationships with `selectinload`; a `joinedload` over a
  many-to-many multiplies rows and scans SQLite. `joinedload` is for many-to-one (`Album.artist`).
- `refresh()` expires an instance without re-applying query options; touch the relationship
  while the instance is still attached.
- Schema changes are a migration step run by `auralis/library/migration_manager.py`; bump
  `__db_schema_version__` in `auralis/__version__.py`.

## No variants

There is one implementation of each concept. Do not add an "Enhanced", "V2" or "Advanced" copy
next to its base; refactor the base in place. The rule is about copies that coexist with their
base. `Streamlined*`, `UnifiedConfig` and `unified_loader` are the only implementations and keep
their names. Intentional variation that looks like duplication is listed in
[STREAMLINING_PLAN.md](STREAMLINING_PLAN.md); read it before collapsing anything. When a feature
is removed, delete it and its tests in the same change. There are no deprecation shims and no
commented-out code.

## Frontend

Stack: React 18, TypeScript (strict), Redux Toolkit, MUI, Vite, Vitest.

- Imports use the `@/` alias (`tsconfig.json` `paths`, mirrored in `vitest.config.ts`). The tree
  has no `../` imports in production code; keep it that way.
- Colours, spacing, typography, radii, shadows and z-index come from design tokens:
  `import { tokens } from '@/design-system'`. Do not write a hex colour or a pixel literal that a
  token already names. `src/design-system/__tests__/unreadTokens.test.ts` fails when a token leaf
  has no reader, so delete a token with its last consumer and run
  `pnpm exec vitest run src/design-system` after removing components. Primitives live in
  `src/design-system/primitives/`; see `src/design-system/README.md`.
- Components stay under 300 lines (the LOC ratchet covers `auralis-web/frontend/src/`, excluding
  tests). Extract a hook or a child component rather than growing the file.
- There is no ESLint or Prettier. The compiler is the linter: `strict`, `noUnusedLocals`,
  `noUnusedParameters` and `noFallthroughCasesInSwitch` are on. `noUncheckedIndexedAccess` is off
  by design; `tsconfig.json` records the cost of enabling it. Do not paper over a type error with
  `any` or a non-null assertion.
- `pnpm run type-check` covers every source file including tests; `pnpm run type-check:prod`
  (`tsconfig.build.json`) covers shipped code only. CI requires both to report zero errors.
- Server data goes through the typed hooks under `src/hooks/` (`useRestAPI` is the generic REST
  hook); components do not call `fetch` directly. Shared UI state lives in the Redux store under
  `src/store/`.
- Frontend tests use `vi.*` from Vitest and `render` from `@/test/test-utils`; see
  [TESTING_GUIDELINES.md](TESTING_GUIDELINES.md).

## Tests as a standard

A test must be able to fail. The two weak-assertion gates reject the cheap ways to write one that
cannot:

- `scripts/check_weak_assertions.py` fails on a `test_*` function whose only assertions are
  `X is not None`, or that carries an assertion which cannot fail (`assert True`, `... or True`,
  `len(X) >= 0`). The default mode uses `weak-assertions-baseline.json`.
- `scripts/check_weak_assertions.py --zero` fails on a `test_*` function with no assertion at all
  (no `assert`, no `pytest.raises` / `warns`, no `assert*` / `check*` / `verify*` / `expect*`
  call), against `zero-assertions-baseline.json`.
- `scripts/check-weak-tests.mjs` is the frontend twin: a spec with no `expect`, a spec whose every
  assertion is a presence check (`toBeDefined`, `toBeTruthy`, `not.toBeNull`,
  `not.toBeUndefined`), and a spec whose only assertion sits inside an `if` with no `else`. The
  baseline is `weak-tests-baseline.json`.

Baselines list offenders by `path::test name`, never by count, so strengthening one test cannot
offset weakening another. `tests/conftest.py` also warns at collection time about a new
`is not None`-only test in any file it collects. Fix the test; do not add it to a baseline.

## Git

Branch from `master` with a `feature/`, `fix/`, `refactor/` or `docs/` prefix. Commit messages
are `type: description (#NNNN)` with `type` one of `fix`, `feat`, `refactor`, `perf`, `test`,
`docs`, `ci`, `chore`. `Closes #NNNN` in a pushed commit closes the issue. Commit each logical
unit once its scoped tests pass; before a PR, run the scoped tests for what changed plus `mypy`
and `type-check`. The full suite is a CI job, not an inner loop.

## Documentation

- Present tense and evergreen: no "Version / Last Updated" banners, no "as of", no "was removed in
  #N". Git carries history. A short "Do not re-add X: <reason>" is allowed.
- Cite symbols, not line numbers.
- A path that no longer exists is written in *italics*, never in backticks, because the path
  gate resolves every backticked path against the tree. Markdown links must resolve relative to
  the file that contains them.
- Do not hardcode counts that a script can compute; run `python scripts/check_doc_counts.py` and
  update CLAUDE.md and `.claude/commands/_audit-common.md` together.
- Link the owning document instead of restating it.
