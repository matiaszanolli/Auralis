# Contributing to Auralis

The contributor on-ramp: what to install, which rules are enforced, how to test, and how a
change reaches `master`. For architecture, start at
[architecture/overview.md](architecture/overview.md).

---

## 1. Prerequisites

Python 3.14 (GIL build; `3.14t` is not supported), [uv](https://docs.astral.sh/uv/), Node 24+,
pnpm 10.20.0 (via `corepack enable`), a stable Rust toolchain with `maturin`, and the system
libraries libsndfile and FFmpeg. The versions are pinned by `.python-version`,
`packageManager` in each `package.json` and `vendor/auralis-dsp/rust-toolchain.toml`.

The Rust module (`auralis_dsp`) is required: fingerprinting and adaptive mastering fail without
it (see [subsystems/dsp-engine.md](subsystems/dsp-engine.md#5-rust-dsp-module-vendorauralis-dsp)).

---

## 2. First-time setup

Follow [FIRST_TIME_SETUP.md](../FIRST_TIME_SETUP.md). It covers the uv environment, the Python
and JavaScript installs, the Rust build, launching, and resetting `~/.auralis`.

Per-side tooling, debugging and failure fixes:
[development/DEVELOPMENT_SETUP_BACKEND.md](development/DEVELOPMENT_SETUP_BACKEND.md) and
[development/DEVELOPMENT_SETUP_FRONTEND.md](development/DEVELOPMENT_SETUP_FRONTEND.md).

Optional: `pre-commit install` runs the hooks in `.pre-commit-config.yaml` (ruff, black, isort,
mypy, pylint, and a path-reference check when a commit deletes or renames files).

---

## 3. Ground rules

[CLAUDE.md](../CLAUDE.md) is the source of truth; read its **Critical Invariants**, **Patterns**
and **Principles** sections before a first change. [development/DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md)
and [development/REPOSITORY_PATTERN.md](development/REPOSITORY_PATTERN.md) carry the detail. In
short: preserve sample counts in DSP, route all database access through
[`auralis/library/repositories/`](../auralis/library/repositories/), import frontend modules
through `@/` with tokens from `@/design-system`, keep modules under 300 lines, and improve
existing code rather than adding a parallel version.

Conventions the CI gates enforce, so they are worth knowing before the first push:

- **Deferrals are greppable.** Write `# TODO(#NNNN):` with a real, open issue number. Prose such
  as "for now" does not count.
- **No history in comments or docs.** `scripts/check_breadcrumbs.py` rejects "was removed in
  #N" phrasing and line-number anchors (a path followed by `:` and a number) in source. Docs cite
  a symbol instead, and a path that no longer exists is written in italics, not backticks.
- **Split files stay split.** `loc-ceilings.json` lists files that may not grow past their
  recorded line count.
- **New tests assert something.** `scripts/check_weak_assertions.py` rejects new tests whose only
  assertion is `is not None`, and tests with no assertion.

---

## 4. Testing

[development/TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md) is mandatory reading.
[development/TEST_EXECUTION_GUIDE.md](development/TEST_EXECUTION_GUIDE.md) covers markers and
selection.

```bash
# Python: scope every run. The whole backend suite takes tens of minutes.
python -m pytest -q -m "not slow" tests/<subdir>   # e.g. tests/auralis/dsp
python -m pytest tests/path.py::test_name -vv -s   # one test

# Frontend: the suite needs a 2 GB heap, so use the memory script
cd auralis-web/frontend && pnpm run test:memory -- <test-file-or-dir>

# Type checks
mypy auralis/ auralis-web/backend/ --ignore-missing-imports
cd auralis-web/frontend && pnpm run type-check
```

Two backend files hang when run whole, so a tree-wide run excludes them exactly as CI does:

```bash
python -m pytest -q -m "not slow" \
  --ignore=tests/backend/test_system_api.py \
  --ignore=tests/concurrency/test_thread_safety.py
```

`-m "not slow"` skips the tests the nightly job runs. Tests that boot the backend app use the
`_isolated_library_db` fixture (`tests/app_isolation.py`), so they do not touch `~/.auralis`.

---

## 5. CI gates

Neither test suite is fully green, so the two test gates are **ratchets**: a run is compared
with a checked-in list of known failures and fails only on failures that are not on the list.
The list may shrink and never grows. Fixing a failing test means regenerating the baseline in the
same change, or the stale entry keeps permitting that failure. The commands, baseline files and
gate scripts are tabulated in
[CLAUDE.md, CI gates and the failure baselines](../CLAUDE.md#ci-gates-and-the-failure-baselines);
that section is the one place they are maintained, including how to regenerate a baseline.

Other workflows under `.github/workflows/` that can fail a pull request:

| Workflow | What it enforces |
|----------|------------------|
| `backend-tests.yml` | pytest ratchet, plus a `gates` job: weak-assertion, LOC-ceiling and breadcrumb checks, and `ruff` for unused imports and locals (`F401`, `F811`, `F841`) |
| `frontend-test.yml` | Vitest ratchet and the weak-spec check (`pnpm run test:weak`) |
| `frontend-typecheck.yml` | `pnpm run type-check:prod`, which must be clean |
| `path-references.yml` | `.claude/commands/_audit-validate.sh`: every backticked path and Markdown link in the checked docs resolves |
| `lockfile-guard.yml`, `requirements-pin-guard.yml`, `action-pin-guard.yml` | One pnpm lockfile per package; pinned Python requirements; Actions pinned by SHA |
| `dependency-audit.yml`, `rust-audit.yml` | Advisories against the locked Python, npm and Rust dependency trees |
| `slow-tests.yml` | Nightly run of the `slow` tests against `pytest-slow-baseline.json` |

---

## 6. Git and pull requests

- Branch from `master`. Prefixes: `feature/`, `fix/`, `refactor/`, `docs/`.
- Commit messages are `type: description`, for example `fix: clamp currentTime to duration`.
- Commit each logical unit once its scoped tests pass.
- Before opening a pull request, run the scoped tests for what you touched, `mypy`, and the
  frontend `type-check`. The full suite is a CI job, not an inner loop.
- If you touched docs, run `.claude/commands/_audit-validate.sh`; it must report no stale
  references.
- `Closes #NNNN` in a commit message that reaches `master` closes the issue.
- Release binaries are built and published only by `.github/workflows/build-release.yml`. See
  [development/BUILD_QUICK_REFERENCE.md](development/BUILD_QUICK_REFERENCE.md).

---

## 7. Documentation

When a change alters behavior a developer relies on, update the doc that owns the fact and link to
it from anywhere else:

- Architecture or data flow: [architecture/](architecture/)
- Subsystem behavior: [subsystems/](subsystems/)
- Setup steps: [FIRST_TIME_SETUP.md](../FIRST_TIME_SETUP.md)
- Environment variables: [auralis-web/backend/CONFIG.md](../auralis-web/backend/CONFIG.md)
- Conventions and CI commands: [CLAUDE.md](../CLAUDE.md)

Keep the [docs hub](README.md) links working. Docs are written in the present tense and carry no
dates, version banners or change notes; git holds the history. Point-in-time write-ups belong in
[archive/](archive/).
