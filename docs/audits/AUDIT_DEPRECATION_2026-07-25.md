# Deprecation Audit — 2026-07-25

**Scope**: Whole repository at `/mnt/data/src/matchering` — Python stdlib/language, NumPy/SciPy/audio
libraries, FastAPI/Pydantic/SQLAlchemy, React/Redux/MUI, Node/npm/build tooling, Rust/PyO3/Cargo,
internal deprecations, configuration & CI.
**Method**: Fresh static analysis of the current tree (HEAD `54d055df`). No prior audit report was used
as a source of findings; prior reports and `gh issue list` (400 issues) were used only for
deduplication.
**Baseline**: Python 3.14+ target (`.python-version` still 3.13.9, transitional — known, not reported).
Node 24+. pnpm-only. `numpy==2.3.5`, `scipy==1.16.3`, `pydantic==2.12.4`, `SQLAlchemy==2.0.44`,
`fastapi==0.122.0`, React 18.3.1, MUI 9.0.1, Vitest 4.1.7, Vite 7, Electron 39, pyo3/numpy-rs 0.23.

---

## Executive Summary

**Total findings: 18** — CRITICAL 0 · HIGH 3 · MEDIUM 6 · LOW 9

The application source is in unusually good shape for a deprecation audit. Every "classic" removed-API
check came back clean: zero `datetime.utcnow()`, zero removed NumPy aliases, zero SciPy legacy
entry points, zero Pydantic V1 syntax, zero SQLAlchemy 1.x `Query` API in production, zero React 16/17
legacy APIs, zero `@mui/styles`, zero deprecated npm packages installed. Production Python has been
fully migrated to PEP 585/604 typing and the ORM is fully SQLAlchemy 2.0 (`DeclarativeBase` +
`Mapped[]` + `mapped_column`).

**All 18 findings sit in the packaging, tooling, and dead-shim layers, not in the application code.**
The three HIGH findings share a single theme: *the declared build/test contract has drifted away from
the working one*, so a clean environment resolves a stack that does not work.

### Key upgrade blockers

1. `pyproject.toml`'s `[project.dependencies]` no longer describes the real dependency set — it omits
   SQLAlchemy entirely, still floors NumPy at `>=1.20.0` (a range in which the removed `np.float`
   aliases are legal), and floors FastAPI at `>=0.68.0` (pre-lifespan, pre-Pydantic-v2). Four declared
   dependencies have zero imports anywhere, including PyQt6.
2. `tests/conftest.py` uses the pytest hook signature removed in pytest 9.1, and nothing pins pytest
   below it. The two hooks that would otherwise cover the same behaviour are dead duplicates.
3. `vendor/auralis-dsp/Cargo.lock` is `.gitignore`d for a `cdylib` that ships inside the desktop
   installer — the exact condition that previously hid an ndarray 0.15/0.16 conflict until a release
   build broke.

### Recommended migration order

| # | Finding | Why first |
|---|---------|-----------|
| 1 | DEP-3 (`Cargo.lock` untracked) | One-line `.gitignore` change; protects the shipped binary |
| 2 | DEP-2 (pytest hook + floor) | Unblocks a clean dev environment; ~15 lines |
| 3 | DEP-1 (`pyproject` dependencies) | Unblocks `pip install -e .`; metadata-only |
| 4 | DEP-4 (pytest-asyncio 1.x fixtures) | Removes three silently-inert fixtures |
| 5 | DEP-6 / DEP-8 (npm holdouts, uvicorn extras) | Build/ship reproducibility |
| 6 | DEP-5 (`navigator.platform`) | Only deprecated Web API on a live code path |
| 7 | LOW batch | Opportunistic |

### Existing issues confirmed still present (NOT re-reported)

`#4313` `require_library_manager` shim · `#4332` `asyncio.get_event_loop_policy()` in test fixtures ·
`#4333` `Session.query()` in 13 test files (47 call sites — count re-verified) · `#4334`
`realtime_processor.py` re-export shim · `#4335` `base_spectrum_analyzer.py` 4 BC wrappers · `#4336`
black/mypy `py314` target vs dev-tool floors · `#4337` `edge_cases` marker with zero usages.

---

## HIGH

### DEP-1: `pyproject.toml` `[project.dependencies]` has drifted off the real dependency set
- **Severity**: HIGH
- **Dimension**: Config/CI
- **Location**: `pyproject.toml:24-36` (runtime deps), `pyproject.toml:38-47` (dev extras)
- **Status**: NEW
- **Deprecated API**: Dependency floors that admit removed APIs (`numpy>=1.20.0`, `fastapi>=0.68.0`,
  `librosa>=0.9.0`, `scipy>=1.7.0`, `uvicorn>=0.15.0`) plus four dependencies with zero imports
- **Deprecated Since**: NumPy 1.24 removed `np.bool`/`np.int`/`np.float`/`np.complex`/`np.object`/`np.str`;
  NumPy 2.0 removed ~40 more aliases. FastAPI 0.93 introduced `lifespan` (deprecating `on_event`);
  FastAPI < 0.100 predates Pydantic V2 support entirely.
- **Removal Version**: Already removed — the floors admit versions where the removals have *not* happened,
  which is the inverse hazard: a resolver may legally pick NumPy 1.20 and the codebase's NumPy 2.x
  assumptions silently break.
- **Replacement**: Mirror the vetted pins from `requirements.txt` (the de-facto source of truth) or at
  minimum raise floors to `numpy>=2.0`, `scipy>=1.16`, `fastapi>=0.115`, `pydantic>=2.12`, and add the
  missing runtime dependencies.
- **Affected Files**: 1 (`pyproject.toml`); contrast with `requirements.txt` and
  `auralis-web/backend/requirements.txt`
- **Evidence**:
  ```toml
  # pyproject.toml:24-36
  dependencies = [
      "numpy>=1.20.0",       # requirements.txt pins numpy==2.3.5
      "scipy>=1.7.0",        # requirements.txt pins scipy==1.16.3
      "sounddevice>=0.4.5",  # zero `import sounddevice` in auralis/ or auralis-web/ (test-only)
      "soundfile>=0.10.0",
      "audioread>=3.0.0",    # zero direct imports (transitive via librosa)
      "librosa>=0.9.0",
      "websockets>=10.0",    # zero direct imports (transitive via uvicorn[standard])
      "fastapi>=0.68.0",     # predates lifespan AND Pydantic V2 support
      "uvicorn>=0.15.0",
      "pydantic>=2.0.0",
      "PyQt6>=6.2.0",        # "For development UI" — ZERO occurrences repo-wide
  ]
  ```
  Missing entirely, despite being core runtime: `SQLAlchemy` (0 mentions in `pyproject.toml`),
  `mutagen`, `pillow`, `aiohttp`, `psutil`, `python-dotenv`, `pydantic-settings`, `python-multipart`,
  `resampy`.
  Verification: `grep -rn "PyQt6\|from PyQt" --include='*.py' .` → 0 hits;
  `grep -rln "import sounddevice" auralis/ auralis-web/` → 0 hits.
- **Migration Path**:
  1. Regenerate `[project.dependencies]` from `requirements.txt`, keeping `>=` floors at the pinned
     major/minor rather than at 2021-era values.
  2. Add `SQLAlchemy`, `mutagen`, `pillow`, `aiohttp`, `psutil`, `python-dotenv`, `pydantic-settings`,
     `python-multipart`, `resampy`.
  3. Delete `PyQt6` and `audioread`; move `sounddevice` to the `dev` extra (it is imported only by
     `tests/conftest.py::_ensure_portaudio`); drop `websockets` or keep it explicitly if the direct
     dependency is intended.
  4. Extend the existing `requirements-pin-guard.yml` CI job to also diff `pyproject.toml`'s
     dependency names against `requirements.txt`, so the two cannot silently diverge again.
- **Effort**: Small (1 file, ~15 lines)
- **Risk**: `pip install -e .` / `pip install -e .[dev]` — the flow implied by having a `dev` extra —
  produces an environment that cannot import `auralis.library` (no SQLAlchemy) and may resolve a
  NumPy 1.x in which large parts of the DSP code's dtype and promotion assumptions are wrong. PyQt6
  is a ~100 MB dependency pulled for nothing. The project also publishes under the name
  `matchering-player`, so this metadata is what a downstream consumer would see.

### DEP-2: `pytest_ignore_collect(path, config)` legacy signature + unbounded `pytest>=7.0.0` floor, with both fallback hooks dead
- **Severity**: HIGH
- **Dimension**: Config/CI
- **Location**: `tests/conftest.py:45-50` (deprecated hook), `tests/conftest.py:38` & `tests/conftest.py:500`
  (duplicate `pytest_configure`), `tests/conftest.py:52` & `tests/conftest.py:514` (duplicate
  `pytest_collection_modifyitems`), `pyproject.toml:39` (floor pin)
- **Status**: NEW (the floor-pin/hook-signature pair; distinct from the marker findings in #4336/#4337)
- **Deprecated API**: `pytest_ignore_collect(path, config)` — the `path` parameter (`py.path.local`)
- **Deprecated Since**: pytest 7.0 (superseded by `collection_path: pathlib.Path`)
- **Removal Version**: pytest 9.1 — the legacy signature is gone; collection crashes outright
- **Replacement**: `def pytest_ignore_collect(collection_path: Path, config) -> bool | None:` using
  `collection_path.name` instead of `path.basename`
- **Affected Files**: 2 (`tests/conftest.py`, `pyproject.toml`)
- **Evidence**:
  ```python
  # tests/conftest.py:45
  def pytest_ignore_collect(path, config):
      """Ignore test files that depend on missing/refactored modules"""
      filename = path.basename          # py.path.local API, removed in pytest 9.1
      if filename in _SKIP_BENCHMARK_TESTS:
          return True
      return None
  ```
  ```toml
  # pyproject.toml:38-40
  dev = [
      "pytest>=7.0.0",          # no upper bound -> a fresh resolve picks >=9.1 and crashes collection
  ```
  The working environment has `pytest==9.0.1` installed (`.venv`), but nothing in the repo records
  that constraint.

  **Amplifier — the fallback is dead.** `tests/conftest.py` defines `pytest_configure` twice (`:38`,
  `:500`) and `pytest_collection_modifyitems` twice (`:52`, `:514`). Python module semantics mean the
  later definition wins, so:
  - the `:38` hook that registers the `benchmark` marker is dead (harmless — `pytest.ini` also
    declares it),
  - the `:52` hook that skips the 8 `_SKIP_BENCHMARK_TESTS` files is dead, replaced by `:514` which
    is a bare `pass`.

  `pytest_ignore_collect` at `:45` is therefore the *only* surviving mechanism keeping those 8 broken
  benchmark files out of collection. When it stops firing, they are collected and error at import.
- **Migration Path**:
  1. Rewrite `pytest_ignore_collect` to the `collection_path` signature (2 lines).
  2. Delete the dead duplicate `pytest_configure` (`:38-43`) and merge its content into `:500`; delete
     the dead `pytest_collection_modifyitems` (`:52-60`) or restore its logic into `:514`.
  3. Replace `item.fspath.basename` at `tests/conftest.py:55` with `item.path.name` (`fspath` is the
     same deprecated `py.path` surface).
  4. Constrain the floor: `"pytest>=9.0.1,<9.1"` until step 1 lands, then relax to `"pytest>=9.0.1"`.
- **Effort**: Small (< 10 call sites)
- **Risk**: Any fresh clone + `pip install -e .[dev]` (or `uv pip install -e .[dev]`) yields **zero
  collectible tests** — pytest aborts during collection with a hook-signature error. Amplified by the
  fact that no active CI workflow runs pytest at all (`.github/workflows/` contains only
  `build-release`, `frontend-typecheck`, `lockfile-guard`, `requirements-pin-guard`, `rust-audit`), so
  this would surface only on a developer's machine, at the worst possible moment.

### DEP-3: `Cargo.lock` is `.gitignore`d for a `cdylib` that ships in the desktop installer
- **Severity**: HIGH
- **Dimension**: Rust/PyO3
- **Location**: `.gitignore:184` and `.gitignore:186`; `vendor/auralis-dsp/Cargo.toml:17-18`
- **Status**: NEW
- **Deprecated API**: Not an API — a superseded Cargo convention. The historical "libraries don't
  commit `Cargo.lock`" rule was **retired by the Cargo team in 2023**; current official guidance is to
  commit `Cargo.lock` for every package, and it has always been mandatory for packages producing a
  final artifact.
- **Deprecated Since**: Cargo book guidance changed with Rust 1.72 (Aug 2023)
- **Removal Version**: n/a (convention change)
- **Replacement**: Track `vendor/auralis-dsp/Cargo.lock` in git; remove the two ignore rules.
- **Affected Files**: 2 (`.gitignore`, plus the untracked `vendor/auralis-dsp/Cargo.lock` on disk)
- **Evidence**:
  ```gitignore
  # .gitignore:183-186
  vendor/auralis-dsp/target/
  vendor/auralis-dsp/Cargo.lock
  vendor/**/target/
  vendor/**/Cargo.lock
  ```
  `git ls-files vendor/auralis-dsp/` returns `Cargo.toml`, `UPGRADE_PLAN.md`, and 18 `src/*.rs` files —
  no lockfile. The crate is `crate-type = ["cdylib", "rlib"]` and is compiled into
  `desktop/resources/` by `.github/workflows/build-release.yml` for all four release targets, so it is
  unambiguously a final artifact.

  This is a known-realised risk, not a theoretical one: the absence of a tracked lockfile is what let
  an `ndarray` 0.15/0.16 conflict sit undetected until a release build broke (see
  `vendor/auralis-dsp/UPGRADE_PLAN.md`, which records the 0.15 → 0.16 bump).

  Compounding it, there is no *rust-toolchain.toml* anywhere in the repo, and CI uses
  `dtolnay/rust-toolchain@stable` (3 call sites in `.github/workflows/build-release.yml` and
  `.github/workflows/rust-audit.yml`) — so both the compiler version *and* the dependency graph float
  between builds.
- **Migration Path**:
  1. Delete `.gitignore:184` and narrow `.gitignore:186` (`vendor/**/Cargo.lock`) so it does not cover
     `auralis-dsp`.
  2. `git add -f vendor/auralis-dsp/Cargo.lock` and commit the currently-resolved graph.
  3. Add a *vendor/auralis-dsp/rust-toolchain.toml* pinning a channel, and switch CI to
     `dtolnay/rust-toolchain@<pinned>` or let the toolchain file drive it.
  4. Optionally extend `rust-audit.yml` to run `cargo build --locked` so a drifted lockfile fails CI.
- **Effort**: Small (2 lines + 1 commit)
- **Risk**: Every release build re-resolves the crate graph from scratch. A semver-compatible upstream
  release between two builds changes what ships without any diff in the repo, and the resulting binary
  is not reproducible from a git checkout. Given the crate performs HPSS/YIN/chroma/limiter DSP on the
  audio path, a silent transitive change is an audio-integrity risk with no paper trail.

---

## MEDIUM

### DEP-4: Three `event_loop` fixture overrides that pytest-asyncio 1.0 removed
- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `tests/backend/conftest.py:48-58`, `tests/integration/test_phase4_player_workflow.py:138-143`,
  `tests/backend/test_scan_progress_callback.py:77`; `pytest.ini:3`
- **Status**: NEW — root cause distinct from **#4332**, which reports the
  `asyncio.get_event_loop_policy()` call *inside* two of these fixtures. This finding is that the
  fixtures themselves are inert under the installed pytest-asyncio.
- **Deprecated API**: Redefining the `event_loop` fixture to control the async test loop
- **Deprecated Since**: pytest-asyncio 0.23
- **Removal Version**: pytest-asyncio 1.0 — the `event_loop` fixture no longer exists; a user-defined
  fixture of that name is just an ordinary, unused fixture
- **Replacement**: `asyncio_default_fixture_loop_scope` / `asyncio_default_test_loop_scope` in
  `pytest.ini`, or `@pytest.mark.asyncio(loop_scope="session")` per test
- **Affected Files**: 3 test files + `pytest.ini`
- **Evidence**:
  ```python
  # tests/backend/conftest.py:48-58
  @pytest.fixture(scope="session")
  def event_loop():
      """This fixture ensures pytest-asyncio works correctly."""   # it no longer does
      policy = asyncio.get_event_loop_policy()
      loop = policy.new_event_loop()
      yield loop
      loop.close()
  ```
  Installed version: `pytest_asyncio.__version__ == '1.4.0'` (in `.venv`).
  `pytest.ini:3` sets `asyncio_mode = auto` but never sets `asyncio_default_fixture_loop_scope`, which
  pytest-asyncio ≥ 0.24 warns about on every run.
  `tests/integration/test_phase4_player_workflow.py:138` is worse — it declares `async def event_loop()`,
  an async generator fixture that would never have worked as a loop provider even under 0.2x.
- **Migration Path**:
  1. Delete all three `event_loop` fixtures.
  2. Add `asyncio_default_fixture_loop_scope = function` (or `session`, matching current intent) to
     `pytest.ini`.
  3. Where session-scoped loop sharing was actually needed, use `@pytest.mark.asyncio(loop_scope="session")`.
  4. This also resolves **#4332** — the deprecated `get_event_loop_policy()` calls disappear with the
     fixtures.
- **Effort**: Small (3 files)
- **Risk**: Tests that believe they share a session-scoped loop silently get per-test loops. Any test
  relying on cross-test loop identity (WebSocket listeners in
  `tests/integration/test_phase4_player_workflow.py`) is passing for the wrong reason or flaky. A
  DeprecationWarning is also emitted on every run and is invisible because of DEP-7.

### DEP-5: `navigator.platform` — deprecated Web API on a live code path, triplicated
- **Severity**: MEDIUM
- **Dimension**: React/Redux/MUI
- **Location**: `auralis-web/frontend/src/services/keyboardShortcutsService.ts:173`,
  `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:131`,
  `auralis-web/frontend/src/components/shared/useShortcutFormatting.ts:24`
- **Status**: NEW
- **Deprecated API**: `Navigator.platform`
- **Deprecated Since**: Deprecated in the HTML Living Standard; MDN marks it Deprecated and warns it
  "should be avoided" — browsers freeze or spoof its value
- **Removal Version**: Not announced; value is already frozen/unreliable in Chromium
- **Replacement**: `navigator.userAgentData?.platform` (available in Chromium, which is the only engine
  this Electron app runs on) with a `navigator.userAgent` regex fallback
- **Affected Files**: 3 production files (identical logic in all three)
- **Evidence**:
  ```ts
  // services/keyboardShortcutsService.ts:173 — and byte-identical at
  // hooks/app/useKeyboardShortcuts.ts:131 and components/shared/useShortcutFormatting.ts:24
  navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  ```
- **Siblings**: All three sites listed above — one finding, one fix.
- **Migration Path**:
  1. Add a single `isMacPlatform()` helper (e.g. in `services/keyboardShortcutsService.ts`) using
     `navigator.userAgentData?.platform ?? navigator.platform`.
  2. Replace all three call sites with it; the DRY consolidation is the larger win.
- **Effort**: Small (3 call sites)
- **Risk**: Chromium already reports a frozen `navigator.platform`. When it is finally reduced further,
  every macOS user silently sees `Ctrl` glyphs instead of `⌘` in the shortcut UI — a cosmetic but
  user-visible regression, and the triplication guarantees a partial fix.

### DEP-6: npm/yarn holdouts in executable scripts and the onboarding doc, against pnpm-only (#4357)
- **Severity**: MEDIUM
- **Dimension**: Node/npm/Build
- **Location**: `package.json:16-18` (executable), `FIRST_TIME_SETUP.md:94`, `FIRST_TIME_SETUP.md:167`,
  `FIRST_TIME_SETUP.md:237`; ~40 further doc-only occurrences under `docs/`
- **Status**: NEW
- **Deprecated API**: `npm install` / `npm run` as the project's package manager
- **Deprecated Since**: #4357 established pnpm as the single supported manager; `packageManager` is
  declared as `pnpm@10.20.0` in all three `package.json` files
- **Removal Version**: n/a (policy)
- **Replacement**: `pnpm install` / `pnpm run` / `pnpm -r`
- **Affected Files**: 2 that matter (`package.json`, `FIRST_TIME_SETUP.md`) + ~40 docs
- **Evidence**:
  ```json
  // package.json:16-18 — the ONLY executable npm invocations left in the repo
  "install:all":      "npm run install:desktop && npm run install:frontend",
  "install:desktop":  "cd desktop && npm install",
  "install:frontend": "cd auralis-web/frontend && npm install",
  ```
  ```markdown
  <!-- FIRST_TIME_SETUP.md:94 — the doc CLAUDE.md points new contributors to -->
  npm install
  ```
  Everything else is already converted: `README.md`, `CLAUDE.md`, `AGENTS.md`, and all five active
  workflows use `pnpm install --frozen-lockfile`.
- **Siblings**: Non-executable/advisory only — `build.js:320-322` (printed build hints),
  `auralis-web/frontend/scripts/memory-test-failsafe.js:17-19` (module docstring), plus ~40 files
  under `docs/`.
- **Migration Path**:
  1. Rewrite `package.json:16-18` to `pnpm install` (or replace all three with a single
     `pnpm -r install`, since `packageManager` is set in every package).
  2. Update `FIRST_TIME_SETUP.md` (3 sites) — highest-value doc fix, it is the entry point for a new
     contributor.
  3. Sweep `docs/` and `build.js` / `memory-test-failsafe.js` strings opportunistically.
- **Effort**: Small for the executable + onboarding fix; Medium if the full `docs/` sweep is included
- **Risk**: `pnpm run install:all` currently shells out to `npm install`, producing a
  a *package-lock.json* and an npm-resolved `node_modules` that ignores `pnpm-lock.yaml`. The
  `lockfile-guard.yml` CI job only fails on a *committed* stray lockfile — it cannot see a local one —
  so a contributor gets a silently different dependency graph than CI builds and ships, including a
  different resolution for the `rollup >=4.59.0` security override.

### DEP-7: `pytest.ini` suppresses the warning summary and declares a stale `minversion`
- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `pytest.ini:19` (`--disable-warnings` in `addopts`), `pytest.ini` `minversion = 6.0`
- **Status**: NEW
- **Deprecated API**: n/a — this is the mechanism that *hides* every other deprecation in this report
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Drop `--disable-warnings`; keep `filterwarnings = default::DeprecationWarning`
  (already present and correct) so the summary is actually rendered. Raise `minversion` to `9.0.1`.
- **Affected Files**: 1
- **Evidence**:
  ```ini
  # pytest.ini addopts
  addopts =
      --verbose
      --tb=short
      --strict-markers
      --strict-config
      --disable-warnings     # suppresses the warnings summary section

  # ...and further down, contradicting it:
  filterwarnings =
      default::DeprecationWarning
  ```
  `minversion = 6.0` while the suite only actually works on pytest 9.0.1 (see DEP-2) and
  `pyproject.toml` floors at 7.0.0 — three different declared minimums, none of them right.
- **Migration Path**:
  1. Remove `--disable-warnings` from `addopts`.
  2. Set `minversion = 9.0.1` (consistent with DEP-2's pin).
  3. Expect an initial burst of warnings; the module-scoped `ignore::DeprecationWarning:pyaudio` /
     `:soundfile` filters already present will absorb the known third-party noise.
- **Effort**: Small (1 file)
- **Risk**: The project is structurally blind to `DeprecationWarning`s. Both `LibraryManager.__init__`
  (`auralis/library/manager.py:89`) and `require_library_manager`
  (`auralis-web/backend/routers/dependencies.py:48`) deliberately emit `DeprecationWarning` to drive
  migration, and every one of those signals is discarded — including the pytest-asyncio 1.x warnings
  from DEP-4. This is why a deprecation audit has to be run manually here.

### DEP-8: `uvicorn` vs `uvicorn[standard]` drift between the root and shipped requirements
- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `requirements.txt:19` vs `auralis-web/backend/requirements.txt:27`
- **Status**: NEW
- **Deprecated API**: n/a — extras drift in files whose own header mandates they be identical
- **Deprecated Since**: n/a
- **Removal Version**: n/a
- **Replacement**: Make both `uvicorn[standard]==0.38.0` (or both bare, if the extras are unwanted)
- **Affected Files**: 2
- **Evidence**:
  ```
  requirements.txt:19                        uvicorn==0.38.0
  auralis-web/backend/requirements.txt:27    uvicorn[standard]==0.38.0
  ```
  `auralis-web/backend/requirements.txt` opens with:
  > "It MUST mirror the root requirements.txt (the single source of truth) … To update: change root
  > requirements.txt first, then copy its pins here."

  This is the only line where they differ (verified by a sorted diff of all `pkg==version` entries).
  The `[standard]` extra is not cosmetic — it pulls `uvloop`, `httptools`, `watchfiles`, `websockets`,
  and `PyYAML`.
- **Migration Path**:
  1. Decide which is correct — the shipped app almost certainly wants `[standard]` for `uvloop`.
  2. Add `uvicorn` to the sensitive-package loop in `.github/workflows/requirements-pin-guard.yml`, or
     better, replace that loop with a full sorted diff of the two files so *any* future drift fails CI.
- **Effort**: Small (1 line + 1 CI tweak)
- **Risk**: The shipped desktop app runs on `uvloop` + `httptools`; the dev and CI environments run on
  the pure-Python asyncio loop and `h11`. Every async timing characteristic of the WebSocket audio
  stream — the most latency-sensitive path in the product — is therefore exercised on a different
  event-loop implementation from the one users get. The `requirements-pin-guard` job passes because it
  only checks `numpy`/`scipy`/`soundfile`/`mutagen`.

### DEP-9: `.github/workflows.backup/` is tracked, stale, and its README claims the workflows are active
- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `.github/workflows.backup/` (5 tracked files)
- **Status**: NEW
- **Deprecated API**: Python 3.9/3.10/3.11 test matrices; `actions/setup-python@v5`,
  `actions/checkout@v4`, `codecov/codecov-action@v4`
- **Deprecated Since**: Python 3.9 reached EOL Oct 2025; the project requires 3.14+
- **Removal Version**: n/a
- **Replacement**: Delete the directory (git history preserves it), or rename it to something that
  cannot be mistaken for live config and fix the README.
- **Affected Files**: 5 (`README.md`, `backend-tests.yml`, `build-release.yml`, `ci.yml`,
  `frontend-build.yml`)
- **Evidence**:
  ```markdown
  <!-- .github/workflows.backup/README.md -->
  # GitHub Actions Workflows
  This directory contains automated CI/CD workflows for Auralis.
  ## Active Workflows
  ### 🔄 ci.yml - Main CI Pipeline
  **Triggers**: Every push and PR to master/develop
  - **test-python**: Run backend tests on Python 3.9, 3.10, 3.11
  ```
  None of these run — GitHub only executes `.github/workflows/`. Action-version inventory in the
  backup: 11× `actions/checkout@v4`, 7× `actions/setup-python@v5`, 5× `actions/setup-node@v4`.
- **Migration Path**: `git rm -r .github/workflows.backup/`. If any content is still wanted (the
  `backend-tests.yml` Python test job is the obvious candidate, given no active workflow runs pytest —
  see DEP-2), port it forward to `.github/workflows/` on Python 3.14 with current action versions
  first.
- **Effort**: Small
- **Risk**: A contributor reading `.github/workflows.backup/README.md` concludes that backend tests,
  linting, and Codecov upload run on every PR. None of them do. That false confidence is the direct
  reason DEP-2 could ship undetected.

---

## LOW

### DEP-10: `tsconfig.node.json` project reference points at a file that no longer exists
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/tsconfig.node.json` (`"include": ["vite.config.ts"]` — a file that does not exist),
  referenced from `auralis-web/frontend/tsconfig.json`
- **Status**: NEW
- **Deprecated API**: Stale TS project reference
- **Deprecated Since**: whenever the config was renamed to `vite.config.mts`
- **Removal Version**: n/a
- **Replacement**: `"include": ["vite.config.mts"]`
- **Affected Files**: 1
- **Evidence**: The frontend's Vite config is `auralis-web/frontend/vite.config.mts`; *vite.config.ts*
  does not exist (`find . -name 'vite.config.*'` returns only the `.mts` file). `tsconfig.node.json`
  sets `composite: true`, so a composite build (`tsc -b`) over an empty include set errors with
  *"No inputs were found in config file"*.
- **Migration Path**: Change the include to `vite.config.mts`. Note `type-check` runs `tsc --noEmit`
  (not `-b`), which is why this has stayed invisible.
- **Effort**: Small (1 line)
- **Risk**: `vite.config.mts` is never type-checked, and any future switch to `tsc -b` fails outright.

### DEP-11: Dead CRA-era `jsconfig.json` alongside `tsconfig.json`
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/jsconfig.json`
- **Status**: NEW
- **Deprecated API**: `jsconfig.json` in a TypeScript project; `"module": "commonjs"`, `"target": "ES6"`
- **Deprecated Since**: Superseded when the frontend became TypeScript + Vite + ESM
- **Removal Version**: n/a
- **Replacement**: Delete — TypeScript ignores `jsconfig.json` entirely when a `tsconfig.json` exists.
- **Affected Files**: 1
- **Evidence**:
  ```json
  // auralis-web/frontend/jsconfig.json
  { "compilerOptions": { "baseUrl": "src", "paths": { "*": ["*"] },
      "target": "ES6", "module": "commonjs" } }
  ```
  Every value contradicts `tsconfig.json` (`target: ES2020`, `module: ESNext`,
  `moduleResolution: bundler`, `paths: {"@/*": ["./src/*"]}`), and `"exclude": ["node_modules", "build"]`
  references a `build/` output dir that Vite does not use (`outDir: 'dist'`).
- **Migration Path**: `git rm auralis-web/frontend/jsconfig.json`.
- **Effort**: Small
- **Risk**: Editor/IDE tooling that prefers `jsconfig.json` resolves the wrong path aliases and module
  system, producing phantom import errors.

### DEP-12: Node built-ins imported without the `node:` protocol prefix
- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: 20 import sites across 7 files
- **Status**: NEW
- **Deprecated API**: Bare specifiers for Node core modules (`require('fs')`, `import path from 'path'`)
- **Deprecated Since**: `node:` prefix introduced in Node 14.18/16; recommended practice since Node 18
- **Removal Version**: Not announced — bare specifiers still resolve
- **Replacement**: `require('node:fs')`, `import path from 'node:path'`
- **Affected Files**: 7 — `dev.js:3-5`, `build.js:16-18,46`, `package.js:14-16`,
  `desktop/main.js:4-6,256`, `auralis-web/frontend/vite.config.mts:3-4`,
  `auralis-web/frontend/vitest.config.ts:5`, `auralis-web/frontend/scripts/memory-test-failsafe.js:22-25`
- **Evidence**:
  ```js
  // build.js:16-18
  const { spawn } = require('child_process');
  const path = require('path');
  const fs = require('fs');
  // build.js:46
  env: extraEnv ? { ...require('process').env, ...extraEnv } : undefined
  ```
  Repo-wide: 20 bare specifiers vs 1 already using the `node:` prefix — the migration was started and
  abandoned.
- **Migration Path**: Prefix all 20. Mechanical and low-risk in CommonJS and ESM alike.
- **Effort**: Small (20 call sites, 7 files)
- **Risk**: Low today. A bare `require('path')` is shadowable by a same-named package in
  `node_modules`; the `node:` prefix makes core-module resolution unambiguous and is required for
  some future Node module-resolution modes.

### DEP-13: Dead deprecated backward-compat shims in the frontend
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis-web/frontend/src/components/enhancement/EnhancedPlaybackControls.tsx:36-37,49`,
  `auralis-web/frontend/src/theme/themeConfig.ts:507`,
  `auralis-web/frontend/src/hooks/app/useKeyboardShortcuts.ts:125-127`
- **Status**: NEW
- **Deprecated API**: Three internal shims kept "for backward compatibility", all with zero production
  consumers
- **Deprecated Since**: Various ("Phase 3" wrapper, pre-theme-unification alias)
- **Removal Version**: n/a
- **Replacement**: Delete all three
- **Affected Files**: 3
- **Evidence**:
  1. `EnhancedPlaybackControls` — self-described "thin wrapper around EnhancementPane for backward
     compatibility". Its only reference outside its own file is the barrel re-export in
     `auralis-web/frontend/src/components/enhancement/index.ts:8-9`. It also carries a dead deprecated
     prop:
     ```ts
     // EnhancedPlaybackControls.tsx:36-37
     /** Show detailed status (DEPRECATED: Now always shown in InspectionLayer) */
     showStatus?: boolean;
     // :49  "Forward all props to EnhancementPane (showStatus is deprecated, ignored)"
     ```
     `grep -rn "showStatus"` finds nothing outside this one file — the prop is accepted and discarded.
  2. ```ts
     // theme/themeConfig.ts:507
     export { darkColors as colors }; // For backward compatibility
     ```
     Zero importers of `colors` from `themeConfig` — the only consumers
     (`contexts/ThemeContext.tsx:4`, `theme/__tests__/themeConfig.tokens.test.ts:15`) import
     `darkColors`/`lightColors` directly. Particularly worth removing now that `f2143dd7` has just
     unified the theme on a semantic contract.
  3. ```ts
     // hooks/app/useKeyboardShortcuts.ts:125-127
     /** Legacy alias for formatShortcut (for backward compatibility with tests) */
     export const getShortcutString = (shortcut: string): string => {
     ```
     Its only callers are in `hooks/app/__tests__/useKeyboardShortcuts.test.ts` — production code
     exists solely to satisfy a test. It is also a third copy of the DEP-5 `navigator.platform` logic.
- **Migration Path**: Delete `getShortcutString` and its test block; delete the `colors` re-export;
  delete `showStatus` from `EnhancedPlaybackControlsProps` and inline `EnhancedPlaybackControls` into
  `EnhancementPane` (or delete it and its barrel export).
- **Effort**: Small
- **Risk**: None functionally — this is the "No variants" project principle drifting. Each shim is one
  more thing a reader must prove is dead.

### DEP-14: `processor_factory.set_mastering_targets` — dead, self-documented-racy deprecated method
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis-web/backend/core/processor_factory.py:354-394`
- **Status**: NEW
- **Deprecated API**: `ProcessorFactory.set_mastering_targets()`
- **Deprecated Since**: #3720
- **Removal Version**: Not committed
- **Replacement**: Pass `mastering_targets` to `get_or_create(...)`; the cache key already hashes them
- **Affected Files**: 1
- **Evidence**:
  ```python
  # auralis-web/backend/core/processor_factory.py:362-376
  DEPRECATED (#3720): the cache key now includes a hash of `mastering_targets` ...
  this method mutates a cached processor in place, which races with
  any concurrent `process_chunk()` call on the same instance.
  Kept for backward compatibility; no in-tree callers as of #3720.
  ...
  # racy on purpose; the deprecation note above is the only fix.
  ```
  Verified: `grep -rn "set_mastering_targets"` returns exactly one hit — the definition itself. No
  callers in production, tests, or the frontend.
- **Migration Path**: Delete the method. Nothing references it, and its own docstring documents it as
  racy.
- **Effort**: Small (1 method, ~40 lines)
- **Risk**: A future caller reaches for the convenient-looking public method and introduces a data race
  against `process_chunk()` on a live processor — the code comment explicitly says the only mitigation
  is "don't call it".

### DEP-15: `LibraryManager` deprecated since v1.1.0, "removed in v2.0.0", still constructed at every backend startup
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/library/manager.py:44-95` (class + warning),
  `auralis-web/backend/config/startup.py:210` and `auralis/cli/fetch_artwork.py:148` (live callers)
- **Status**: NEW — related to **#4314** (CLOSED, which covered the unfulfilled migration-*timeline*
  promise). This finding is the live-caller side: the deprecated class is not merely un-removed, it is
  on the mandatory startup path.
- **Deprecated API**: `auralis.library.manager.LibraryManager`
- **Deprecated Since**: v1.1.0
- **Removal Version**: v2.0.0 (per its own warning text); current version is 1.5.1
- **Replacement**: `auralis.library.repositories.factory.RepositoryFactory`
- **Affected Files**: 2 production call sites
- **Evidence**:
  ```python
  # auralis/library/manager.py:89-94
  warnings.warn(
      "LibraryManager is deprecated. Use RepositoryFactory instead. "
      "See MIGRATION_GUIDE.md for migration instructions. "
      "This class will be removed in v2.0.0.",
      DeprecationWarning, stacklevel=2)
  ```
  ```python
  # auralis-web/backend/config/startup.py:210
  globals_dict['library_manager'] = LibraryManager()
  ```
  So every backend boot emits the DeprecationWarning that the class's own contract says precedes
  removal. `docs/guides/MIGRATION_GUIDE.md` exists, so the migration path is documented.
- **Migration Path**:
  1. Migrate `auralis-web/backend/config/startup.py:210` to construct a `RepositoryFactory` and store
     it in `globals_dict`, then fix the (few) consumers that expect the `library_manager` shape.
  2. Migrate `auralis/cli/fetch_artwork.py:148`.
  3. Once both are gone, `#4313`'s `require_library_manager` shim can also be deleted, closing that
     issue at the same time.
- **Effort**: Medium (2 construction sites, but a wide consumer surface behind `globals_dict['library_manager']`)
- **Risk**: Either the v2.0.0 removal promise is broken again (it has already slipped 4 minor versions)
  or v2.0.0 breaks the backend's own startup. The warning is invisible in tests because of DEP-7.

### DEP-16: Dead `get_track_by_path` / `get_by_filepath` backward-compat aliases
- **Severity**: LOW
- **Dimension**: Internal
- **Location**: `auralis/library/manager.py:378-380`,
  `auralis/library/repositories/track_repository.py:290-291`
- **Status**: NEW
- **Deprecated API**: `LibraryManager.get_track_by_path()`, `TrackRepository.get_by_filepath()`
- **Deprecated Since**: Unversioned; both are labelled backward-compat aliases
- **Removal Version**: n/a
- **Replacement**: `TrackRepository.get_by_path()`
- **Affected Files**: 2
- **Evidence**:
  ```python
  # auralis/library/repositories/track_repository.py:290-291
  def get_by_filepath(self, filepath: str) -> Track | None:
      """Alias for get_by_path for backward compatibility"""
      return self.get_by_path(filepath)
  ```
  `grep -rn "get_by_filepath"` → only the definition. `grep -rn "get_track_by_path"` → the definition
  at `auralis/library/manager.py:378` plus one test caller
  (`tests/auralis/library/test_library_manager.py:126`). Real production code already calls the
  canonical name (`auralis-web/backend/services/queue_service.py:270` uses
  `library_manager.tracks.get_by_path(fp)`).
- **Migration Path**: Delete `get_by_filepath` outright (zero callers). Delete `get_track_by_path` and
  update the single test to call `manager.tracks.get_by_path(...)`.
- **Effort**: Small (2 methods, 1 test line)
- **Risk**: None functional. Three names for one operation is a discoverability tax and an invitation
  to add a fourth.

### DEP-17: Deprecated browser APIs on Electron-only code paths
- **Severity**: LOW
- **Dimension**: React/Redux/MUI
- **Location**: `auralis-web/frontend/src/store/middleware/errorTrackingMiddleware.ts:128`;
  `auralis-web/frontend/src/hooks/enhancement/useEnhancedStreamStart.ts:116`,
  `auralis-web/frontend/src/hooks/enhancement/usePlayNormal.ts:203`,
  `auralis-web/frontend/src/types/window.d.ts:39`;
  `auralis-web/frontend/src/services/audio/BufferScheduler.ts:250-277`
- **Status**: NEW
- **Deprecated API**: (a) `String.prototype.substr`, (b) `window.webkitAudioContext`,
  (c) `AudioContext.createScriptProcessor` / `ScriptProcessorNode`
- **Deprecated Since**: (a) ECMAScript Annex B (legacy since ES2015); (b) prefixed API, unprefixed
  `AudioContext` since Chrome 35; (c) Web Audio API deprecated `ScriptProcessorNode` in 2014
- **Removal Version**: None announced for any of the three
- **Replacement**: (a) `.slice(2, 11)`; (b) drop the `|| window.webkitAudioContext` fallback and the
  `window.d.ts` declaration; (c) `AudioWorkletNode` — already the primary path
- **Affected Files**: 5
- **Evidence**:
  ```ts
  // store/middleware/errorTrackingMiddleware.ts:128
  return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  ```
  ```ts
  // hooks/enhancement/useEnhancedStreamStart.ts:116  (identical at usePlayNormal.ts:203)
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  ```
  For (c), `services/audio/BufferScheduler.ts` correctly prefers `AudioWorkletNode`
  (`BufferScheduler.ts:130-177`) and only falls back to `createScriptProcessor`
  (`BufferScheduler.ts:253-277`). The migration is *done*; the fallback is what remains.
- **Siblings**: `auralis-web/frontend/src/test/setup.ts:145-146` mocks `addListener`/`removeListener`
  on `matchMedia` — correct mock completeness for a deprecated-but-present API, not a finding.
- **Migration Path**:
  1. `.substr(2, 9)` → `.slice(2, 11)` (1 site).
  2. Delete the `webkitAudioContext` fallback and its `window.d.ts:39` declaration — CLAUDE.md
     establishes Auralis is Electron-only, and Electron 39's Chromium has had unprefixed
     `AudioContext` for a decade.
  3. Keep the `ScriptProcessorNode` fallback for now, or delete it on the same "guaranteed Chromium"
     reasoning — Electron 39 always provides `AudioWorklet`, so
     `BufferScheduler.ts:253-277` and its dedicated test coverage are exercising a branch that can
     never fire in production.
- **Effort**: Small for (a) and (b); Medium for (c) if the fallback and its tests are removed
- **Risk**: Minimal. All three still work. The cost is carrying (and testing) two audio-output code
  paths when only one is reachable.

### DEP-18: Legacy pytest `tmpdir` fixture and `item.fspath`; legacy `typing` generics in tests
- **Severity**: LOW
- **Dimension**: Python Stdlib / Config-CI
- **Location**: `tmpdir` in 11 test files (111 occurrences); `item.fspath` at `tests/conftest.py:55`;
  legacy `typing` generics in 14 test files (40 occurrences)
- **Status**: NEW
- **Deprecated API**: `tmpdir` / `tmpdir_factory` (`py.path.local`), `Item.fspath`,
  `typing.Optional`/`List`/`Dict`/`Tuple`/`Union`
- **Deprecated Since**: pytest 6 designates `tmpdir` legacy in favour of `tmp_path`; `fspath` legacy
  since pytest 7; PEP 585 (3.9) and PEP 604 (3.10) supersede the `typing` generics
- **Removal Version**: Not announced for `tmpdir`; `typing` generic aliases have no removal date
  (`typing.ByteString` was removed in 3.14 — **not used here**)
- **Replacement**: `tmp_path` (`pathlib.Path`), `item.path`, `X | None` / `list[X]` / `dict[K, V]`
- **Affected Files**: ~25 test files
- **Evidence**: `tmp_path` is already the majority convention — 60 test files use it vs 11 still on
  `tmpdir`, so this is a stalled migration rather than a greenfield one. Likewise, **production Python
  is 100 % migrated** to PEP 585/604: the only `from typing import` lines remaining under `auralis/`
  and `auralis-web/backend/` import `Any`, `cast`, `NamedTuple`, and `TYPE_CHECKING`; every residual
  `Dict[`/`List[` match in production is inside a docstring or is `collections.OrderedDict[...]`
  (which is correct). Only the test tree lags.
- **Migration Path**: Convert the remaining 11 `tmpdir` files to `tmp_path` (mechanical:
  `tmpdir.join(x)` → `tmp_path / x`, `str(tmpdir)` → `str(tmp_path)`). Fix `item.fspath.basename` →
  `item.path.name` as part of DEP-2. Modernise the 14 test files' type hints opportunistically.
- **Effort**: Medium (~25 files, all mechanical)
- **Risk**: Low. `tmpdir` returns `py.path.local`, a bundled third-party type pytest has wanted to shed
  for years; the inconsistency is a papercut for anyone writing new tests.

---

## Dependency Upgrade Roadmap

| Order | Package / Config | Current | Action | Blocked by |
|-------|-----------------|---------|--------|-----------|
| 1 | `vendor/auralis-dsp/Cargo.lock` | untracked | Track it (DEP-3) | — |
| 2 | `pytest` | floor `>=7.0.0`, working `9.0.1` | Migrate hook, then pin `>=9.0.1` (DEP-2) | — |
| 3 | `pyproject.toml` deps | 2021-era floors, SQLAlchemy missing | Regenerate from `requirements.txt` (DEP-1) | — |
| 4 | `pytest-asyncio` | `1.4.0` installed, 0.2x-era fixtures | Delete `event_loop` fixtures, set loop scope (DEP-4) | — |
| 5 | `uvicorn` | extras drift dev vs shipped | Unify on `[standard]` (DEP-8) | — |
| 6 | GH Actions | `checkout@v4`+`@v6`, `setup-node@v4`+`@v6`, `pnpm/action-setup@v4`+`@v6` | Normalise to newest across all 5 active workflows | — |
| 7 | `react-router-dom` | `6.30.2`, **test-only** | Move to `devDependencies` or delete — sole importer is `src/test/test-utils.tsx` | — |
| 8 | `uuid` / `@types/uuid` | `14.0.0` / `10.0.0` | Delete both — zero `uuid` imports in `src/`; `uuid` ≥ 7 ships its own types, so `@types/uuid` is an obsolete stub (and targets v10, not v14) | — |
| 9 | React | `18.3.1` | 19 upgrade — MUI 9 already declares React 19 peer support | Separate effort |
| 10 | Rust edition | 2021 | 2024 (stable since Rust 1.85) | Do after DEP-3 |
| 11 | `pyo3` / `numpy` (rust) | `0.23` | **HELD — known-blocked, do not bump** | numpy-rs / NumPy 2.3.x ABI runtime bug on 3.13 *and* 3.14 |

### Known-blocked, informational only — `pyo3` / `numpy-rs` 0.23

The `vendor/auralis-dsp` pins are **intentional and correct**, not stale. The working configuration is
`pyo3 = 0.23` + `numpy = 0.23` built with `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` against Python 3.14.
Bumping to 0.29 compiles but hits a `rust-numpy` / NumPy 2.3.x ABI runtime failure on both 3.13 and
3.14. This is documented in `vendor/auralis-dsp/UPGRADE_PLAN.md`, and the env var is correctly wired
into `build.js:176` and all three build jobs in `.github/workflows/build-release.yml` — no tribal
knowledge gap. **No action recommended.**

Two minor observations on that file, not filed as findings:
- The "Latest major available" column lists pyo3 `0.25 / 0.26` while the RUSTSEC-2026-0177 row in the
  same document states the fix requires `>= 0.29.0`. The table is one refresh behind its own body text.
- The two `cargo audit --ignore`s (RUSTSEC-2025-0020, RUSTSEC-2026-0177) are correctly justified —
  neither `PyString::from_object` nor `PyCFunction::new_closure` appears anywhere in
  `vendor/auralis-dsp/src/`, verified. The stated removal trigger ("the moment the pyo3 bump lands")
  is the right contract.

The Rust source itself is clean: `vendor/auralis-dsp/src/py_bindings.rs` uses current PyO3 0.23
idioms (`py.allow_threads`, `IntoPyArray`, `PyReadonlyArray1/2`) with no deprecated `*_bound` APIs, no
`#[pyfn]`, no `IntoPy`/`ToPyObject`, and correctly releases the GIL around every long compute (12 call
sites).

---

## Migration Effort Summary

| Finding | Severity | Effort | Call sites |
|---------|----------|--------|-----------|
| DEP-1 pyproject deps | HIGH | Small | 1 file |
| DEP-2 pytest hook + floor | HIGH | Small | 2 files |
| DEP-3 Cargo.lock untracked | HIGH | Small | 2 lines |
| DEP-4 pytest-asyncio fixtures | MEDIUM | Small | 3 files |
| DEP-5 navigator.platform | MEDIUM | Small | 3 |
| DEP-6 npm holdouts | MEDIUM | Small (exec) / Medium (docs) | 2 + ~40 docs |
| DEP-7 --disable-warnings | MEDIUM | Small | 1 file |
| DEP-8 uvicorn extras drift | MEDIUM | Small | 1 line |
| DEP-9 workflows.backup | MEDIUM | Small | 5 files |
| DEP-10 tsconfig.node include | LOW | Small | 1 line |
| DEP-11 dead jsconfig.json | LOW | Small | 1 file |
| DEP-12 node: prefix | LOW | Small | 20 |
| DEP-13 frontend dead shims | LOW | Small | 3 files |
| DEP-14 set_mastering_targets | LOW | Small | 1 method |
| DEP-15 LibraryManager callers | LOW | Medium | 2 + consumers |
| DEP-16 path alias methods | LOW | Small | 2 methods |
| DEP-17 deprecated browser APIs | LOW | Small / Medium | 5 files |
| DEP-18 tmpdir / fspath / typing | LOW | Medium | ~25 files |

---

## Clean Results (explicit negatives)

Verified present-and-absent. Each was grepped across the full tree with false positives eliminated by
reading the surrounding code.

### Python stdlib & language — all clean
`datetime.utcnow()` / `utcfromtimestamp()` (**0**) · `pkg_resources` (0) · `distutils` (0) · `imp` (0) ·
PEP 594 removed modules, incl. the audio-relevant `audioop` / `aifc` / `sunau` / `sndhdr` (0) ·
`sre_constants` / `sre_compile` / `sre_parse` (0) · `pkgutil.find_loader` / `get_loader` (0) ·
`typing.ByteString` / `typing.Text` / `typing.io` / `typing.re` (0) · `assertEquals` /
`assertNotEquals` / `assertRaisesRegexp` / `failUnless` / `makeSuite` / `findTestCases` (0) · ABCs
imported from `collections` instead of `collections.abc` (0) · `Thread.setDaemon()` / `isAlive()` /
`getName()` / `setName()` (0) · `.daemon =` set after `.start()` (0) · `ssl.PROTOCOL_TLS` /
`ssl.wrap_socket` (0) · `locale.getdefaultlocale()` (0) · `configparser.readfp` / `has_key` (0) ·
`@asyncio.coroutine` (0) · `multiprocessing.set_start_method` / `get_context` — no reliance on
fork semantics ahead of the 3.14 default change (0). Production `typing` is fully PEP 585/604.

### NumPy / SciPy / audio libraries — all clean (numpy 2.3.5, scipy 1.16.3, librosa 0.11.0, soundfile 0.13.1)
Removed 1.24 aliases `np.bool` / `np.int` / `np.float` / `np.complex` / `np.object` / `np.str` /
`np.long` / `np.unicode` (**0**) · NumPy 2.0 removals `np.product` / `cumproduct` / `sometrue` /
`alltrue` / `round_` / `in1d` / `row_stack` / `msort` / `NaN` / `Inf` / `NAN` / `infty` / `float_` /
`complex_` / `unicode_` / `string_` / `NINF` / `PINF` / `PZERO` / `NZERO` / `issctype` / `obj2sctype` /
`safe_eval` / `trapz` / `AxisError` / `set_string_function` / `newbyteorder` / `get_array_wrap` (0) ·
`np.core` / `numpy.core` / `np.compat` / `np.math` (0) · `scipy.fftpack` (0) · `scipy.misc` (0) ·
`scipy.interpolate.interp2d` (0) · `scipy.linalg.pinv2` (0) · top-level `scipy.signal` window
functions removed in 1.13 (0) · `cwt` / `morlet` / `ricker` / `daub` / `qmf` removed in 1.15 (0) ·
`simps` / `cumtrapz` (0). No `librosa.output` or removed-kwarg usage.

### FastAPI / Pydantic / SQLAlchemy — all clean (fastapi 0.122.0, pydantic 2.12.4, SQLAlchemy 2.0.44)
Pydantic V1: `class Config:` inside a model, `.dict()`, `.json()`, `@validator`, `@root_validator`,
`schema_extra`, `orm_mode`, `parse_obj`, `parse_raw`, `update_forward_refs`, `__fields__`,
`allow_population_by_field_name`, `const=`, `min_items`/`max_items`, `allow_mutation` — **all 0**.
Every model uses `model_config = ConfigDict(...)` (18 sites) or a dict literal. The one
`class Config:` hit (`auralis/core/config.py:56`) is a plain non-Pydantic class, verified by reading it.
FastAPI: `@app.on_event` (0) — startup/shutdown use the lifespan context manager
(`auralis-web/backend/main.py:131-135`, `auralis-web/backend/config/startup.py`). Deprecated `regex=`
and `example=` parameters on `Query`/`Path`/`Body`/`Field` (0).
SQLAlchemy 1.x in production: `session.query()` (**0**), `engine.execute()` (0), `autocommit` (0),
`declarative_base()` (0). `auralis/library/models/base.py:20` uses `DeclarativeBase`; all models use
`Mapped[]` + `mapped_column`; all 16 `relationship()` declarations carry `Mapped[]` annotations. The
`Column()` calls in `models/base.py` are inside `Table()` definitions, which is the correct 2.0 API.
(Test-tree `Session.query()` is tracked separately as **#4333**.)

### React / Redux / MUI — all clean (React 18.3.1, MUI 9.0.1, RTK 2.11, react-redux 9.2)
`ReactDOM.render` / `hydrate` / `unmountComponentAtNode` (**0**) · `componentWillMount` /
`componentWillReceiveProps` / `componentWillUpdate` / any `UNSAFE_` lifecycle (0) · `findDOMNode` (0) ·
`defaultProps` on a function component (0 — the only matches are local test variables) ·
`React.FC` / `React.FunctionComponent` in production (0; 1 test-local occurrence) · string refs (0) ·
`contextTypes` / `childContextTypes` (0) · `PropTypes` (0) · `connect()` HOC (0) · Redux `createStore`
(0 — the matches are local test helpers named `createStore`) · `makeStyles` / `withStyles` /
`@mui/styles` / `createMuiTheme` / `adaptV4Theme` / `@material-ui/*` (0) · MUI Grid v1 `item`/`xs` API
(0) · `<ListItem button>` (0) · deprecated MUI slot props `componentsProps` / `TransitionComponent`
(0) · `tsconfig.json` uses `moduleResolution: "bundler"` (not the legacy `"node"`).

### Node / npm / build — mostly clean
Deprecated Node APIs `fs.exists` / `url.parse` / `new Buffer()` / `util.isArray` / `util.inherits` /
`process.binding` / `domain` (**0**) · Electron: `nodeIntegration: false` + `contextIsolation: true` +
`webSecurity: true` (`desktop/main.js:309-314`), `app.whenReady()` not `app.on('ready')`
(`desktop/main.js:594`), `setWindowOpenHandler` not the deprecated `new-window` event
(`desktop/main.js:331`, `:640`), no `@electron/remote` / `enableRemoteModule` (0) · **no installed npm
package carries a `deprecated` field** (scanned all 216 top-level entries in
`auralis-web/frontend/node_modules`) · no stray *package-lock.json* or *yarn.lock* anywhere · Vitest 4
config is correctly migrated (`vitest.config.ts` documents the v4 `poolOptions` → top-level
`maxWorkers`, `coverage.all` removal, and `snapshotFormat` changes under #3488) · *.eslintrc.\** legacy
format (0 — but note there is **no ESLint config at all** in the repo; that is a tech-debt gap, not a
deprecation).

### Config / CI — mostly clean
No *setup.py* or *setup.cfg* (correctly consolidated into `pyproject.toml`) · version is consistent at
`1.5.1` across `auralis/version.py`, `pyproject.toml`, and all three `package.json` files — no drift
(`sync_version.py` is doing its job) · root and shipped `requirements.txt` are otherwise byte-identical
in their pins (only the DEP-8 `uvicorn` extras differ) · active workflows target Python 3.14 and Node
24 consistently (8 sites) · no Docker base images in play.

### Rust / PyO3 — clean apart from DEP-3
No deprecated Rust std APIs (`std::mem::uninitialized`, `trim_left`/`trim_right`, `try!`,
`ONCE_INIT`) · no `#![feature(...)]` nightly gates · no deprecated PyO3 patterns (`*_bound` APIs,
`#[pyfn]`, `IntoPy`, `ToPyObject`) · no deprecated `Cargo.toml` keys · GIL correctly released around
all 12 long-compute call sites via `py.allow_threads`.

---

## Next Step

```
/audit-publish docs/audits/AUDIT_DEPRECATION_2026-07-25.md
```
