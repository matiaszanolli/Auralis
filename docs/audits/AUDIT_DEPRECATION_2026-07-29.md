# Deprecation Audit — 2026-07-29

**Scope**: Full codebase — Python stdlib/language, NumPy/SciPy/audio libraries, FastAPI/Pydantic/SQLAlchemy,
React/Redux/MUI/TypeScript, Node/npm/Electron/build tooling, Rust/PyO3/Cargo, internal self-declared
deprecations, and configuration/CI.

**Method**: Eight parallel dimension agents, each required to verify every claim against the **actually installed
version** rather than from memory of release notes, and to persist findings incrementally. Negative results were
recorded explicitly so future audits do not re-derive them.

> **STATUS: IN PROGRESS.** Dimensions 6 (Rust/PyO3) and 7 (Internal deprecations) were still running when this
> version was written. See *Dimensions not covered* at the end. This banner is removed when they land.

---

## Environment this audit was verified against

Every finding below was checked against these, not against remembered changelogs.

| Component | Version | How verified |
|---|---|---|
| Python | **3.14.0** | `.venv/bin/python -V` |
| numpy / scipy | **2.4.6** / **1.18.0** | `pip list` + running the promotion cases |
| librosa / soundfile / numba | **0.11.0** / **0.14.0** / **0.66.0** | `pip list` + installed source |
| fastapi / starlette / pydantic | **0.140.13** / **1.3.1** / **2.13.4** | `pip list` + `importlib.metadata` |
| SQLAlchemy / uvicorn | **2.0.44** / **0.51.0** | `pip list` |
| pytest / pytest-asyncio | **9.0.3** / **1.4.0** | `pip list` + live `--collect-only` header |
| mypy / black / isort / pylint | **2.3.0** / **26.5.1** / **8.0.1** / **4.0.6** | `pip list` |
| react / react-dom | **18.3.1** | `node_modules/<pkg>/package.json` |
| @reduxjs/toolkit / react-redux | **2.11.2** / **9.2.0** | ditto |
| @mui/material | **9.0.1** | ditto |
| typescript / vite / vitest | **5.9.3** / **7.3.2** / **4.1.7** | ditto |
| electron | **39.8.5** | `desktop/node_modules/electron/package.json` |
| eslint | **absent** | no config, no manifest entry, no lockfile entry |
| rustc / cargo | **1.96.0** (ac68faa20 / 30a34c682, 2026-05-25) | `rustc --version`, `cargo --version` |
| pyo3 / numpy-rs (Rust) | **0.23** (resolved 0.23.5) | `vendor/auralis-dsp/Cargo.toml:12-13` + cargo-registry sources |
| ndarray (Rust) | **0.16** | `vendor/auralis-dsp/Cargo.toml` |
| maturin | **1.14.1** | reported by the toolchain; no `[tool.maturin]` config exists to audit |
| Cargo edition / MSRV | **2021** / **none declared** | full read of `vendor/auralis-dsp/Cargo.toml` |

**Deliberate pins that are NOT findings** (documented in-repo, re-confirmed here):
`numpy<2.5` (numba 0.66 requires it), `pyo3`/`numpy-rs` 0.23 + `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1`
(numpy-rs 0.29 has a known ABI runtime failure), `ScriptProcessorNode` (annotated under #4623).

---

## Executive Summary

**The application source code is in excellent shape. The dependency *pinning* is not.**

Three dimensions produced empirical proof of cleanliness rather than grep results:

- All **299 `auralis.*` modules** and **109 backend modules** import on Python 3.14.0 with **zero**
  `DeprecationWarning`/`PendingDeprecationWarning`/`FutureWarning`, and a real `HybridProcessor.process()` run on
  synthetic stereo emitted none either.
- The entire backend imports and generates its full **85-path OpenAPI schema** under
  `-W error::DeprecationWarning -W error::UserWarning` with zero warnings. (`UserWarning` escalation matters:
  both `StarletteDeprecationWarning` and `FastAPIDeprecationWarning` subclass `UserWarning`, not
  `DeprecationWarning`.)
- The frontend has **zero** React-18-removed APIs, **zero** React-19 removal-path APIs, **zero** legacy Redux,
  **zero** used MUI-9 deprecated props, and `moduleResolution` is already `"bundler"`.

What the audit actually found is a cluster of **release-integrity** problems: the environment that every
developer, every audit, and every local test run verifies against is **not** the environment that CI installs or
that ships to users — and one major dependency (Starlette) is pinned nowhere at all.

### Findings by severity (final — 8 dimensions + 1 gap-coverage pass)

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 16 |
| LOW | 26 |
| **Total** | **45** |

D6 (Rust/PyO3) contributed 1 MEDIUM + 5 LOW new findings (D6-3/D6-4 were already merged earlier as DEP-24/DEP-25). D7 (Internal deprecations) contributed 4 MEDIUM + 5 LOW. D7B — a follow-up pass launched specifically to cover D7's missing coverage statement — contributed a further 2 MEDIUM + 3 LOW from areas D7 never named, including a genre-adaptive DSP parameter (`detection_mode`) that is computed and then silently discarded on every compression pass.

### Key upgrade blockers

1. **Nothing blocks a Python or library upgrade at the source level.** The 3.14 migration is complete and clean.
2. The **numpy `<2.5` ceiling** is real and load-bearing until numba supports numpy 2.5.
3. The **pyo3/numpy-rs 0.23 pin** remains blocked upstream — correctly, deliberately, and documented.

### Recommended remediation order

1. **DEP-1** — reconcile the pins. Everything else in this report was verified against a stack that does not
   ship; fixing this makes every other conclusion transferable.
2. **DEP-2** — stop the release build from shelling out to `npm`. It currently builds shipped installers from a
   dependency graph the committed lockfiles do not describe.
3. **DEP-3** — bump Electron off an EOL major.
4. **DEP-4** — bump the six CI workflows off node20-runtime actions before GitHub removes it.
5. Everything else opportunistically.

---

## Corrections to prior audits and to the audit tooling

These were flagged to this audit as live problems and are **verified fixed**. They must not be carried forward.

| Prior finding | Status | Evidence |
|---|---|---|
| **DEP-2 (HIGH, 2026-07-25)** — legacy `pytest_ignore_collect(path, config)` hook pinning the suite below pytest 9.1 | **FIXED (#4529)** | The hook, its `_SKIP_BENCHMARK_TESTS` set and two shadowed duplicate hooks were deleted; only an explanatory comment remains at `tests/conftest.py:26-42`. The `<9.1` ceiling was lifted from `pyproject.toml`; the four markers 9.1 rejects under `--strict-markers` are now registered in `pytest.ini`. `pytest.ini` `minversion = 9.0.1` mirrors `pytest>=9.0.1`. **There is no pytest version-ceiling problem.** |
| **DEP-1 (HIGH, 2026-07-25)** — `pyproject.toml` `[project.dependencies]` drift | **FIXED (#4528)** | Regenerated from `requirements.txt`; every entry carries a justification comment; `.github/workflows/requirements-pin-guard.yml` now diffs the name set on every PR. |
| **DEP-7 (MEDIUM)** — `--disable-warnings` in `addopts` | **FIXED (#4559)** | Removed, with a block comment forbidding reintroduction; `filterwarnings` now scopes `ignore::` to third-party noise only and deliberately leaves first-party warnings visible. |
| **DEP-9 (MEDIUM)** — tracked `.github/workflows.backup/` | **FIXED** | Directory does not exist; nothing tracked under it. |
| **DEP-6 (MEDIUM)** — npm/yarn holdouts | **PARTIALLY fixed** | Manifests, CI and lockfiles are fully converted (`lockfile-guard.yml` enforces it). The **build orchestrators were not** — see DEP-2 below. |
| **#4287** — version drift | **FIXED** | `auralis/version.py` = 1.5.1; all three `package.json` files and `pyproject.toml` agree. |
| `.python-version` vs `requires-python` gap | **FIXED** | Both are 3.14. |
| **#4593** — frontend `@deprecated` shims | **Partially stale** | `grep -rn "@deprecated" src/` now returns **0 across all 776 files**; `showStatus` is gone entirely. |
| **#4333** — legacy `Session.query()` in tests | **Count correction** | 14 test files, not "~13". Also verified `session.query().filter_by()` emits **nothing** on SQLAlchemy 2.0.44 — legacy but silent, so LOW is correct. |
| **#4591** — bare Node builtin imports | **Drifting, not stale** | Now **23 sites across 8 files** (issue records 21/7). |

---

## Findings

### HIGH

### DEP-1: The pinned manifests do not describe the environment anything is verified against, and Starlette is pinned nowhere

- **Severity**: HIGH
- **Dimension**: Config/CI + FastAPI/Pydantic + NumPy/SciPy (found independently by three dimensions)
- **Location**: `requirements.txt`, `auralis-web/backend/requirements.txt`, `pyproject.toml`,
  `.github/workflows/backend-tests.yml:71`, `.github/workflows/build-release.yml:106`
- **Status**: NEW (distinct from #4355, which is about floor-vs-exact pinning *style* between the two files)
- **Deprecated API**: n/a — a dependency-integrity failure that invalidates deprecation testing generally
- **Verified Against**: `.venv/bin/pip list --format=freeze` and `importlib.metadata.version()` diffed against the
  `==` pins, both read 2026-07-29:

  | Package | `requirements.txt` pin | Installed in `.venv` |
  |---|---|---|
  | numpy | `==2.3.5` | **2.4.6** |
  | scipy | `==1.16.3` | **1.18.0** |
  | soundfile | `==0.13.1` | **0.14.0** |
  | fastapi | `==0.122.0` | **0.140.13** |
  | pydantic | `==2.12.4` | **2.13.4** |
  | uvicorn[standard] | `==0.38.0` | **0.51.0** |
  | python-multipart | `==0.0.31` | **0.0.27** *(installed is OLDER than the pin)* |
  | **starlette** | **not pinned anywhere** | **1.3.1** *(a major release)* |
  | SQLAlchemy / httpx / pydantic-settings | 2.0.44 / 0.28.1 / 2.12.0 | match |

- **Replacement**: reconcile the pins to the stack actually being developed against, and add an explicit
  `starlette==` pin to both manifests.
- **Affected Files**: 3 manifests + 2 workflows. Zero source files.
- **Evidence**:
  - `grep -rn "starlette" requirements.txt auralis-web/backend/requirements.txt pyproject.toml` → **no pin
    anywhere**. FastAPI 0.140.13's own metadata declares `starlette>=0.46.0` with **no upper bound**
    (`importlib.metadata.requires('fastapi')`), so a fresh resolve takes whatever the newest Starlette is —
    currently the **1.x major line**.
  - Both `.github/workflows/backend-tests.yml:71` and `build-release.yml:106` run
    `pip install -r requirements.txt`, so CI and the shipped desktop build get the pinned stack while every
    local verification happens on the drifted one.
  - `python-multipart` is the inverse case — the venv is *older* than the pin, proving the venv was not last
    provisioned from `requirements.txt`. It is a security-sensitive parser backing `UploadFile`/`Form` in
    `auralis-web/backend/routers/files.py`, and it is exactly the class of package
    `requirements-pin-guard.yml` exists to protect. The guard checks the **file**, never the **installed**
    version, which is why this passed.
  - The 2026-07-25 audit verified the NumPy/SciPy dimension against 2.3.5/1.16.3/0.13.1 — matching the pins at
    that time. The drift opened *since* then.
- **Migration Path**:
  1. Decide which stack is authoritative. The dev/audit environment (0.140.13 / 1.3.1 / 2.13.4 / 2.4.6) is the
     one with actual evidence behind it — promote it.
  2. Add `starlette==1.3.1` to `requirements.txt` and mirror it into `auralis-web/backend/requirements.txt`.
  3. Reinstall `.venv` from `requirements.txt` so `python-multipart` stops disagreeing with its own pin.
  4. Raise the `pyproject.toml` floors to match, and add a `starlette>=1.3` floor. Keep the `numpy<2.5` ceiling.
  5. Extend `requirements-pin-guard.yml` to assert `pip freeze` agrees with `requirements.txt`, and to diff the
     **full** pin set between the two manifests rather than only the sensitive-parser allowlist. Both holes are
     demonstrated by this finding and by DEP-16.
- **Effort**: Small to change (5 files); Medium to re-validate CI on the newer stack.
- **Risk**: Two compounding failures. First, **every** deprecation, DSP dtype, and compatibility conclusion in
  this report — and in the 2026-07-25 report — was drawn from an environment that neither CI nor users run.
  Second, because Starlette is unpinned, **two builds of the same commit can ship different Starlette
  majors**; a release that resolves fastapi 0.122.0 alongside starlette 1.3.1 is a combination nobody has ever
  tested.

### DEP-2: All three root build orchestrators shell out to `npm` — the release path installs outside the committed pnpm lockfiles

- **Severity**: HIGH
- **Dimension**: Node/npm/Build
- **Location** (live invocation sites): `build.js:148,152`; `package.js:78,97`; `dev.js:44,161,216`;
  `auralis-web/frontend/scripts/memory-test-failsafe.js:112`; `auralis-web/start-dev.sh:34,37`;
  `auralis-web/start-dev.bat:21,24`. Text-only: `auralis-web/frontend/scripts/diagnose-memory-linux.sh` (14
  echoed lines), `auralis-web/frontend/scripts/diagnose-memory-windows.bat` (8),
  `docs/development/DEVELOPMENT_SETUP_FRONTEND.md:389`.
- **Status**: Carryover of **DEP-6** (2026-07-25) — the manifest/CI/lockfile half was fixed; the build
  orchestrators were never touched. The sites below are materially more severe than what DEP-6 described.
- **Deprecated API**: `npm` invocation under the pnpm-only policy (#4357)
- **Verified Against**: confirmed the inverse holds — `find` for lockfiles returns exactly three
  `pnpm-lock.yaml` (root, `auralis-web/frontend/`, `desktop/`) and **no** `package-lock.json` or `yarn.lock`
  anywhere. All three `package.json` files carry `"packageManager": "pnpm@10.20.0"`. So the lockfile side of the
  policy is clean; only the invocations drift. Call sites re-verified directly:
  ```
  build.js:148:   await this.runCommand('npm', ['install'], this.frontendDir, …)
  build.js:152:   await this.runCommand('npm', ['run', 'build'], this.frontendDir, …)
  package.js:78:  await this.runCommand('npm', ['install'], this.desktopDir, …)
  dev.js:44:      await this.runCommand('npm', ['install'], '../desktop');
  dev.js:161:     const frontendProcess = spawn('npm', ['run', 'dev'], {…})
  ```
- **Replacement**: `pnpm`
- **Affected Files**: 9 (12 live invocation sites + ~25 text-only). Zero in application runtime code.
- **Evidence**: root `package.json:8-13` wires these three files in as the project's **only** build/dev/package
  entry points (`"dev": "node dev.js"`, `"build": "node build.js"`, `"package": "node package.js"`).
  `build.js` is visibly half-migrated: its printed instructions at `:320-322` correctly say
  `cd desktop && pnpm run build:linux`, while the code a few lines away runs `npm`. Likewise
  `memory-test-failsafe.js:15-19` documents itself as `pnpm run test:memory:failsafe` and then spawns `npm` at
  `:112`. The orchestrators use `shell: true` (`build.js:44`, `package.js:36`), so they resolve `npm` from PATH.
- **Migration Path**: replace `npm` with `pnpm` at the 12 live sites (argument vectors are identical), fix the
  echoed help text, and delete or rewrite `auralis-web/start-dev.{sh,bat}` — those also advertise the backend on
  `http://localhost:8000` when the real port is **8765**, so they are stale beyond the package manager.
- **Effort**: Medium (12 live sites across 9 files)
- **Risk**: `pnpm run build` and `pnpm run package` — the paths that produce the shipped Electron installers —
  internally run `npm install` in `auralis-web/frontend/` and `desktop/`. That either fails outright on a
  pnpm-only machine, or succeeds and resolves a flat `node_modules` **independently of the committed
  `pnpm-lock.yaml`**, meaning the released binary is built from an un-audited dependency graph.
  `lockfile-guard.yml` would catch the stray `package-lock.json` on the *next push* — it detects the symptom
  after the fact and prevents nothing.
- **Side observation (not a deprecation, worth filing separately)**:
  `auralis-web/frontend/scripts/memory-test-failsafe.js:112-116` does
  `const process = spawn('npm', viteArgs, { cwd: process.cwd(), … })`. The `const process` binding shadows the
  global, and the options object is evaluated before the binding initialises, so `process.cwd()` hits the
  temporal dead zone and throws `ReferenceError: Cannot access 'process' before initialization`. **This script
  cannot run at all.**

### DEP-3: Electron 39 is past end-of-life — the shipped desktop binary receives no Chromium security backports

- **Severity**: HIGH
- **Dimension**: Node/npm/Build (Electron runtime)
- **Location**: `desktop/package.json:28` (`"electron": "^39.8.5"`), resolved in `desktop/pnpm-lock.yaml:18-20`
- **Status**: NEW
- **Deprecated API**: the entire Electron 39 major (a runtime, not an API)
- **Deprecated Since**: superseded by Electron 40 (Jan 2026)
- **Removal Version**: **EOL 2026-05-05** — roughly three months before this audit
- **Verified Against**: `desktop/node_modules/electron/package.json` → `"version": "39.8.5"` (confirmed
  independently). Support policy and dates fetched live from the official Electron release schedule, not from
  memory: "the latest three stable major versions are supported"; Electron 39 EOL May 5 2026; newest stable
  major in the July 2026 window is 43. Electron 39 is two-plus majors outside the support window.
- **Replacement**: Electron 42 or 43.
- **Affected Files**: 1 manifest + 1 lockfile. **The Electron source needs no changes** — see the clean result
  below.
- **Evidence**: `desktop/main.js` (644 lines) and `desktop/preload.js` (50 lines) contain none of the
  deprecated/removed Electron patterns: `webPreferences` at `main.js:309-314` is
  `nodeIntegration: false, contextIsolation: true, webSecurity: true` with a preload; no `remote` /
  `@electron/remote`; `contextBridge` + `ipcRenderer.invoke` used correctly; window-open interception already
  migrated to `contents.setWindowOpenHandler()` (`main.js:331-334, 639-643`).
- **Migration Path**: bump `desktop/package.json` to `^43` (or `^42` for one less Chromium jump), `pnpm install`
  in `desktop/`, and re-run all five packaging targets from `build-release.yml`. `electron-builder ^26` supports
  these majors. Note `flatpak.runtimeVersion: "25.08"` (`desktop/package.json:138`) may need to move in step.
- **Effort**: Small (one dependency bump); the real cost is re-verifying five packaging targets.
- **Risk**: An EOL Electron gets no Chromium security patches. **Mitigating factor** (per the project severity
  rule on desktop-only mitigation): the renderer only loads `http://localhost:3000` / `http://localhost:8765`
  (`desktop/main.js:322,325`), so the attack surface is local content, which lowers exploitability
  considerably. It stays HIGH because any Chromium CVE fixed after 2026-05-05 is simply unpatched in a binary
  users install, and the gap widens every month.

### DEP-24: `rust-audit.yml` audits a gitignored lockfile — the gate has failed 100% of its runs since it was created and has never once scanned the crate

- **Severity**: HIGH
- **Dimension**: Cargo/CI (Rust/PyO3)
- **Location**: `.github/workflows/rust-audit.yml:16-24` (path triggers) and `:54-57` (the audit command)
- **Status**: NEW — a consequence of, but distinct from, **Existing #4531**. #4531 is about the lockfile being
  untracked; this is about the security gate that silently depends on it and is dead as a result. See DEP-25.
- **Deprecated API**: n/a — a CI-integrity failure on the Rust trust boundary
- **Verified Against**: live CI history via `gh run list --workflow=rust-audit.yml` and
  `gh run view 30255593758 --log-failed` (read-only), plus `git ls-files` / `git check-ignore`.
- **Evidence**:
  - `git ls-files vendor/auralis-dsp/Cargo.lock` → **empty** (not tracked).
  - `git check-ignore -v vendor/auralis-dsp/Cargo.lock` → `.gitignore:185:vendor/**/Cargo.lock`.
  - The workflow runs `cargo audit --file vendor/auralis-dsp/Cargo.lock` after a bare `actions/checkout@v4` with
    no `cargo generate-lockfile` / `cargo build` step in between — so the path it points at is absent on the
    runner.
  - Every run since the gate was added has failed, including the very commit that introduced it:
    ```
    completed  failure  Rust Security Audit   master  schedule  30255593758  15s  2026-07-27
    completed  failure  Rust Security Audit   master  schedule  29729573151  14s  2026-07-20
    completed  failure  ci(rust): add cargo audit gate ... (#4360)  push  29689224637  18s  2026-07-19
    ```
    3 runs, 3 failures, 0 successes. The exact cause:
    ```
    Loaded 1169 security advisories (from /home/runner/.cargo/advisory-db)
    Updating crates.io index
    error: not found: Couldn't load vendor/auralis-dsp/Cargo.lock
    Caused by:
      -> I/O operation failed: I/O operation failed: entity not found
    ##[error]Process completed with exit code 2.
    ```
    The advisory DB loads fine — it dies on the missing lockfile, before scanning a single crate.
  - Both `push:` and `pull_request:` triggers list `vendor/auralis-dsp/Cargo.lock` among `paths:`. A gitignored
    file can never appear in a diff, so that trigger entry is permanently dead; only `Cargo.toml` and the
    workflow file itself can fire it.
- **Replacement**: either commit `Cargo.lock` (what #4531 already asks for — correct for a cdylib that ships in
  an installer), or add `cargo generate-lockfile --manifest-path vendor/auralis-dsp/Cargo.toml` before the audit
  and drop the dead `Cargo.lock` path trigger. The first also makes the weekly cron meaningful, since a
  regenerated lockfile audits whatever resolved *today*, not what shipped.
- **Affected Files**: 1 workflow. No production code.
- **Effort**: Small
- **Risk**: The one security gate protecting the PyO3 trust boundary has **never scanned anything**, and its
  failure is indistinguishable at a glance from a genuine advisory hit — a red weekly cron everyone has learned
  to ignore. `vendor/auralis-dsp/UPGRADE_PLAN.md:42-54` names "the `cargo audit` gate flags an advisory" as
  re-evaluation trigger #1 for the pinned pyo3, and `:26-40` leans on that gate as "the safety net" justifying
  two `--ignore`d RUSTSEC advisories. The deliberate 0.23 pin's entire documented safety justification therefore
  rests on a gate that has never run to completion. The dimension raised this from MEDIUM to HIGH only after the
  CI history confirmed it is not merely at risk but already 100% broken.

### DEP-25: `Cargo.lock` is gitignored and no `rust-toolchain` pin exists — re-verified still present

- **Severity**: HIGH (as filed)
- **Dimension**: Cargo (Rust/PyO3)
- **Location**: `.gitignore:185` (`vendor/**/Cargo.lock`); no `rust-toolchain*` file anywhere in the repo
- **Status**: **Existing — #4531**, re-verified 2026-07-29. Recorded here without a full write-up per the dedup
  rule; the audit found two things #4531 does not cover — DEP-24 (the dead security gate that depends on it) and
  DEP-28 (the missing `rust-version` manifest key).
- **Verified Against**: `git ls-files` returns nothing for `vendor/auralis-dsp/Cargo.lock`;
  `git check-ignore -v` resolves it to `.gitignore:185`; `find . -maxdepth 3 -name 'rust-toolchain*'` → 0 hits.
- **Effort**: Small
- **Risk**: Combined with the floating `dtolnay/rust-toolchain@stable` in all three release jobs, no shipped
  wheel's compiler version or dependency graph can be reconstructed. See DEP-28.

---

### MEDIUM

### DEP-4: Six of seven CI workflows pin GitHub Actions to node20-runtime majors

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `.github/workflows/frontend-test.yml:40,48,50,73`; `frontend-typecheck.yml:34,39,41`;
  `backend-tests.yml:53,63,94`; `requirements-pin-guard.yml:36,76,113,115,125`; `lockfile-guard.yml:21`;
  `rust-audit.yml:37` — 15-16 `uses:` pins total.
- **Status**: NEW
- **Deprecated API**: JavaScript actions declaring `runs.using: node20`
- **Deprecated Since**: announced 2025-09-19; runners began defaulting to Node 24 on **2026-06-16** (already past)
- **Removal Version**: Node 20 removed from runners **fall 2026**;
  `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true` is the only escape hatch and expires with it.
- **Verified Against**: pins read from the workflow files; latest majors queried live via
  `gh api repos/<action>/releases/latest` (checkout **v7.0.1**, setup-python **v7.0.0**, setup-node **v7.0.0**,
  upload-artifact **v7.0.1**, download-artifact **v8.0.1**, pnpm/action-setup **v6.0.9**); runtime confirmed by
  decoding each tag's `action.yml` — `@v4` → `using: node20`, `@v6` → `using: node24`.
- **Replacement**: the majors `build-release.yml` **already uses** — `checkout@v6`, `setup-python@v6`,
  `setup-node@v6`, `upload-artifact@v7`, `download-artifact@v8`, `pnpm/action-setup@v6`.
- **Affected Files**: 6 workflows. No production code.
- **Evidence**: the same repo pins the *same action* at two majors — `setup-node@v4` (`frontend-test.yml:50`)
  vs `@v6` (`build-release.yml:71`); `upload-artifact@v4` (`backend-tests.yml:94`) vs `@v7`
  (`build-release.yml:159`). Someone migrated the release workflow and stopped.
- **Migration Path**: mechanical bump of the 15-16 pins. Do `upload-artifact@v4 → v7` last and verify any
  consumer still pairs correctly. Optionally set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` on a branch to
  smoke-test first.
- **Effort**: Small
- **Risk**: The six affected workflows are **every** quality gate the project has — frontend-test,
  frontend-typecheck, backend-tests, lockfile-guard, requirements-pin-guard, rust-audit. When node20 is removed
  they all hard-fail at once while `build-release.yml` keeps working, so the failure mode is "all gates go dark
  while releases keep shipping".

### DEP-5: `librosa.load()` on m4a/aac/wma silently routes through the audioread backend that librosa 1.0 removes

- **Severity**: MEDIUM
- **Dimension**: NumPy/SciPy/audio
- **Location**: `auralis/analysis/fingerprint/windowed_compute.py:155-158`, `:166-169`;
  `auralis/analysis/mastering_fingerprint.py:102`
- **Status**: NEW
- **Deprecated API**: librosa's audioread decode fallback (`librosa/core/audio.py::__audioread_load`)
- **Deprecated Since**: librosa **0.10.0**
- **Removal Version**: librosa **1.0** — explicit in the installed source
- **Verified Against**: librosa **0.11.0** and soundfile **0.14.0**, by reading the installed source and by
  querying `soundfile.available_formats()`.
- **Replacement**: route these paths through `auralis.io.unified_loader.load_audio()`, which already sends
  `FFMPEG_FORMATS` through FFmpeg.
- **Affected Files**: 2 production files, 3 call sites. Zero test files.
- **Evidence**: the installed librosa marks the fallback with a hard removal version —
  ```
  librosa/core/audio.py:227: @deprecated(version="0.10.0", version_removed="1.0")
  librosa/core/audio.py:228: def __audioread_load(path, offset, duration, dtype): …
  ```
  and `librosa.load` reaches it whenever soundfile raises (`librosa/core/audio.py:178-184`). Auralis declares
  `.m4a/.aac/.wma/.opus` ingestible (`auralis/io/formats.py:24-31`), but
  `sorted(soundfile.available_formats())` on 0.14.0 contains **no M4A, AAC, or WMA** (MP3 and OGG *are*
  covered, so only that subset is affected). The three fingerprint call sites pass the **raw library path**
  straight to `librosa.load`, bypassing `unified_loader`'s FFmpeg routing.
- **Migration Path**: branch on `Path(p).suffix.lower() in auralis.io.formats.FFMPEG_FORMATS` and decode via
  `unified_loader.load_audio()`, then hand the array to `librosa.resample(...)` — already the pattern used on
  the pre-loaded-audio branch at `windowed_compute.py:189-196`.
- **Effort**: Small (3 sites)
- **Risk**: Today — slower decode, a `UserWarning` per affected track, and 16-bit precision truncation
  (documented at `librosa/core/audio.py:121`) that subtly changes fingerprints versus the FFmpeg path, i.e. two
  different fingerprints for the same audio depending on container. On a librosa 1.0 bump, m4a/aac/wma
  fingerprinting breaks — loudly in `mastering_fingerprint.py`, and **silently** at `windowed_compute.py:166`,
  which wraps the load in a bare `except Exception: pass`.

### DEP-6: Both NEP-50 comments in the DSP code state the promotion rule backwards

- **Severity**: MEDIUM
- **Dimension**: NumPy/SciPy/audio
- **Location**: `auralis/dsp/basic.py:33-40`, `auralis/core/dsp/parallel_eq.py:112-116`
- **Status**: NEW
- **Deprecated API**: NEP 50 promotion semantics — a *misdocumented* migration workaround, not a deprecated symbol
- **Verified Against**: numpy **2.4.6**, by running the promotion cases directly:
  ```
  float32 * python float  -> float32     <-- NOT float64
  float32 * np.float64    -> float64     <-- this is what NEP 50 actually changed
  python float / float32  -> float32
  ```
  `np._get_promotion_state` no longer exists — NEP 50 is unconditional, there is no legacy mode.
- **Replacement**: correct the comments. The real float64 source is `scipy.signal.sosfiltfilt`.
- **Affected Files**: 2 production files, 0 test files.
- **Evidence**: `basic.py:33-40` claims *"Under NumPy < 2.0, multiplying float32 by a Python float silently
  promotes to float64"* — false in both directions; NumPy 1.x value-based casting also kept float32, and NEP 50
  makes Python scalars explicitly **weak**, which again keeps float32. There is no NumPy version where
  `float32_array * python_float` yields float64, so the `np.asarray(scaled, dtype=audio.dtype)` is a no-op.
  `parallel_eq.py:112-116` claims *"in NumPy >= 2.0 (NEP-50) Python float scalars are treated as float64"* —
  the exact inverse of NEP 50; verified `band.astype(f32) * boost_diff → float32`, so the trailing
  `.astype(audio.dtype)` is a redundant full-array copy per call. The cast that **is** load-bearing sits 15
  lines earlier and is correctly attributed to #2158: `sosfiltfilt(float32) → float64`, verified on scipy 1.18.0.
- **Migration Path**: rewrite both comments to state that Python scalars are weak under NEP 50 and never
  promote, and that the float64 originates in `sosfiltfilt`/`filtfilt` — which is precisely why the cast sits
  immediately after the filter call. Optionally drop the two provable no-op casts (low priority; harmless, just
  an extra hot-path allocation).
- **Effort**: Small (2 sites)
- **Risk**: Not a runtime bug — the code produces correct dtypes today. The risk is maintenance: a future reader
  trusting these comments concludes scalar multiplication is the promotion source, and may delete the **correct**
  post-`sosfiltfilt` cast while keeping the useless ones. That is plausibly the mechanism behind #2158 recurring.

### DEP-7: `starlette.testclient` emits a visible deprecation on every backend test file (httpx vs httpx2)

- **Severity**: MEDIUM (test-only, but it is the largest single source of new warning noise from the Starlette
  1.x jump and signals a required dependency swap)
- **Dimension**: FastAPI/Starlette
- **Location**: 25 test files. Representative: `tests/backend/conftest.py`, `tests/backend/test_main_api.py`,
  `tests/integration/test_api_integration.py`, `tests/security/test_trusted_host.py`
- **Status**: NEW
- **Deprecated API**: using `TestClient` while `httpx` (not `httpx2`) is the installed HTTP client
- **Deprecated Since**: Starlette 1.x — the warning at `starlette/testclient.py:47-51` is unconditional, gated
  only on which of `httpx2`/`httpx` imports
- **Removal Version**: not scheduled — but `starlette/testclient.py:35-45` shows that if **neither** imports it
  raises `RuntimeError("…requires the httpx2 package…")`, i.e. `httpx2` is now the intended dependency
- **Verified Against**: starlette **1.3.1** and httpx **0.28.1**, by reading
  `.venv/lib/python3.14/site-packages/starlette/testclient.py:33-51` and by executing the import.
- **Replacement**: add `httpx2` to the dev/test dependency set, or add a scoped `filterwarnings` entry.
- **Affected Files**: 25 test files; **0 production** (the only production mention is a comment at
  `auralis-web/backend/config/middleware.py:274` explaining `Host: testserver`).
- **Migration Path**: two dependency lines, zero source changes.
- **Effort**: Small
- **Risk**: Today, warning noise on every backend test run. If the httpx fallback is ever dropped upstream, all
  25 files fail at import with `RuntimeError`. Note this warning only exists *because* the venv has Starlette
  1.3.1 while CI installs whatever resolves — see DEP-1.

### DEP-8: `pytest.ini` declares `timeout = 300`, but pytest-timeout is neither installed nor declared — the option is inert

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `pytest.ini` (`# Test timeout (in seconds)` / `timeout = 300`)
- **Status**: NEW
- **Verified Against**: pytest **9.0.3**. A live `--collect-only` run printed:
  ```
  PytestConfigWarning: Unknown config option: timeout
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  ```
  `grep -i timeout` over the pip freeze → no `pytest-timeout`.
  `grep -rn "pytest-timeout" pyproject.toml requirements*.txt .github/workflows/*.yml` → no declaration anywhere.
- **Replacement**: add `pytest-timeout>=2.3` to the `dev` extra and to `requirements.txt`.
- **Affected Files**: 1 config; blast radius is the whole suite.
- **Evidence**: `addopts` includes `--strict-config`, which is meant to turn `PytestConfigWarning` into a hard
  error — here it only warns, so the dead key survives the very gate designed to catch it.
- **Migration Path**: declare the plugin (preferred over deleting the key — see Risk), then confirm the warning
  disappears.
- **Effort**: Small
- **Risk**: There is currently **no timeout enforcement on any test**, despite the config claiming 300 s. This
  is not hypothetical here: `tests/backend/test_system_api.py` and `tests/concurrency/test_thread_safety.py` are
  documented to hang indefinitely when run as whole files, and an untargeted `-m "not slow"` run has taken ~75
  minutes. A working `timeout = 300` would turn those hangs into identifiable failures instead of a wedged job.

### DEP-9: `asyncio_default_fixture_loop_scope` is unset — pytest-asyncio warns, and the coming default change alters event-loop sharing

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `pytest.ini` (`asyncio_mode = auto`, with no `asyncio_default_fixture_loop_scope`)
- **Status**: NEW (distinct from #4332, which covers custom `event_loop` fixtures in test files)
- **Deprecated API**: leaving `asyncio_default_fixture_loop_scope` unset
- **Deprecated Since**: pytest-asyncio 0.24
- **Removal Version**: not a removal — a **default change**: async fixtures move from `fixture` caching scope to
  `function` scope
- **Verified Against**: pytest-asyncio **1.4.0**, by reading
  `.venv/lib/python3.14/site-packages/pytest_asyncio/plugin.py:274-299`:
  ```python
  def pytest_configure(config):
      default_fixture_loop_scope = config.getini("asyncio_default_fixture_loop_scope")
      …
      if not default_fixture_loop_scope:
          warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
  ```
  A live run confirms it is unset — pytest's header prints
  `asyncio: mode=Mode.AUTO, …, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function`.
- **Replacement**: set `asyncio_default_fixture_loop_scope = function`, matching the announced future default.
- **Affected Files**: 1 config; affects every async fixture.
- **Migration Path**: set the option, then run the async-heavy directories **scoped** (never whole-file, per the
  known-hang list) and look for fixtures that were relying on a shared loop.
- **Effort**: Small to set; Medium to validate, because the change is behavioral.
- **Risk**: On the next pytest-asyncio minor, async fixtures silently stop sharing an event loop. Any fixture
  holding a loop-bound resource across tests (a WebSocket client, an aiohttp session, a background task) starts
  failing with `attached to a different loop`, which reads as flakiness rather than a config change. The warning
  that would forewarn this is emitted during `pytest_configure`, **before** warning capture, so it never reaches
  the warnings summary — it is invisible in normal runs despite `filterwarnings` being correctly configured.

### DEP-10: `Dockerfile` is stale on every axis — Python 3.11 base against a `>=3.14` project, with a `CMD` naming a script that does not exist

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `Dockerfile:2` (`FROM python:3.11-slim`), `Dockerfile:33` (`CMD [..., "build_auralis.py", ...]`)
- **Status**: NEW
- **Verified Against**: `pyproject.toml` declares `requires-python = ">=3.14"`; `.python-version` pins 3.14; the
  live interpreter is 3.14.0. `ls build_auralis.py` → No such file or directory; `git ls-files` → no match.
  (`requirements-desktop.txt`, referenced at `Dockerfile:21`, **does** exist — that reference is fine.)
- **Replacement**: `python:3.14-slim` and a `CMD` pointing at a real entry point.
- **Affected Files**: 1
- **Evidence**: `pip install -r requirements-desktop.txt` under python:3.11 cannot satisfy a `>=3.14` project,
  and the pinned numba 0.66 / numpy 2.x wheels are selected for cp314. The image fails before it ever reaches
  the missing `build_auralis.py`.
- **Migration Path**: decide whether this file is still wanted. Auralis is a desktop-only Electron app with no
  container deployment story and CI builds all four targets without it — deletion is the honest option.
- **Effort**: Small
- **Risk**: Low operationally (nothing in CI invokes it), high as a trap: it is the only container recipe in the
  repo and it is guaranteed to fail, so anyone who tries it concludes the project is broken.

### DEP-11: `.pre-commit-config.yaml` pins a 2023 toolchain, including a Python 3.9 interpreter that does not exist

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `.pre-commit-config.yaml` — `psf/black rev v23.3.0` with `language_version: python3.9`;
  `pycqa/isort rev 5.12.0`; `pre-commit/mirrors-mypy rev v1.3.0` with `additional_dependencies: [types-all]`;
  `pycqa/pylint rev v3.0.0a6`; `pre-commit/pre-commit-hooks rev v4.4.0`
- **Status**: NEW
- **Verified Against**: installed tools are black **26.5.1**, isort **8.0.1**, mypy **2.3.0**, pylint **4.0.6**,
  pre-commit **4.6.1**. `which python3.9` → not found. `pip index versions types-all` → only `1.0.0`, a
  long-unmaintained meta-package. `grep -n "tool.pylint" pyproject.toml` → **no `[tool.pylint]` section**, yet
  the hook passes `--rcfile=pyproject.toml`.
- **Replacement**: `pre-commit autoupdate`; drop `language_version: python3.9`; replace `types-all` with the
  specific `types-*` stubs needed; add a `[tool.pylint]` section or drop the `--rcfile` argument.
- **Affected Files**: 1 config, 5 hook definitions.
- **Evidence**: black 23.3.0 formats to a 2023 style while `pyproject.toml` sets
  `[tool.black] target-version = ["py314"]` and the installed black is 26.5.1 — hook and config disagree about
  which black is authoritative. The mypy mirror is a full major behind installed mypy. `pylint v3.0.0a6` is an
  **alpha** tag.
- **Migration Path**: as above; verify with `pre-commit run --all-files` **on a scratch clone**, not the working
  tree (it rewrites files).
- **Effort**: Small
- **Risk**: `pre-commit install` followed by any commit fails at hook-environment build time because
  `language_version: python3.9` cannot be satisfied. In practice the hooks are not running for anyone — the
  config is decorative, and the standards it claims to enforce are unenforced outside CI.

### DEP-12: ESLint is absent entirely, and the frontend setup doc contradicts itself about it

- **Severity**: MEDIUM
- **Dimension**: Node/npm/Build
- **Location**: repo-wide absence; documented at `docs/development/DEVELOPMENT_SETUP_FRONTEND.md:389`,
  contradicted at `:614-627`
- **Status**: NEW (as a doc-contradiction / gate-gap finding — the removal itself was deliberate)
- **Deprecated API**: n/a — the "legacy `.eslintrc` vs flat `eslint.config.js`" check resolves to *neither exists*
- **Verified Against**: `find` for `.eslintrc*` / `eslint.config.*` / `.eslintignore` outside `node_modules`
  returns **nothing**; `grep -rn "eslint"` across all JSON/YAML manifests, lockfiles and workflows returns
  **nothing**.
- **Affected Files**: 1 doc with an internal contradiction.
- **Evidence**: `:389` states *"neither ESLint nor Prettier are in devDependencies — this tooling has been
  removed from the project"*, while `:614-627` of the **same file** still instructs installing the ESLint editor
  extension and setting `"source.fixAll.eslint": true`.
- **Migration Path**: delete the stale VS Code block at `:614-627`, and fix the `npm run type-check` reference
  at `:389` → `pnpm` (see DEP-2). The flat-config migration is **moot** — this is explicitly *not* a "you have a
  legacy `.eslintrc`" finding. If ESLint is ever reintroduced it must be flat-config from day one.
- **Effort**: Small (doc edit)
- **Risk**: Low as a deprecation. The doc contradiction wastes onboarding time. The substantive gap is that the
  only static gates are `tsc --noEmit` and vitest — nothing checks unused vars, exhaustive-deps, or
  no-floating-promises.

---

### LOW

### DEP-13: Python 3.14 changed the Linux multiprocessing default to `forkserver`; the production parallel modules were never audited for it

- **Severity**: LOW (production); MEDIUM if `use_multiprocessing=True` is ever enabled
- **Dimension**: Python stdlib (a 3.14 behavior change, not a deprecation)
- **Location**: `auralis/optimization/parallel/config.py:20`, `audio_processor.py:74-95`,
  `band_processor.py:64-105`, `fft_processor.py:154-160`, `decorators.py:18-22`
- **Status**: NEW
- **Verified Against**: live 3.14.0 interpreter — `mp.get_start_method()` → `'forkserver'`;
  `mp.get_all_start_methods()` → `['forkserver', 'fork', 'spawn']`.
- **Affected Files**: 5 production files; 3 test files **already** adapted.
- **Evidence**:
  1. Production impact is **dormant**: `ParallelConfig.use_multiprocessing` defaults to `False`
     (`config.py:20`) and no production call site sets it `True` — only three test files do. Every
     `ProcessPoolExecutor` branch is unreached in the shipped app.
  2. The process path **still works** under forkserver — verified by running the real production classes;
     `ParallelAudioProcessor(ParallelConfig(use_multiprocessing=True)).process_batch(...)` returns correct
     results. `band_processor.py:71-82` already pre-validates picklability and downgrades to threading (#3699),
     and `decorators.py:18` already uses a module-level helper (#3304), so forkserver's picklability
     requirement is satisfied by design.
  3. The real cost is pool startup, ~20x: measured `fork 0.006s` vs `forkserver 0.121s` vs `spawn 0.117s` on an
     identical 2-worker pool. Every pool is created inside a per-call `with` block
     (`audio_processor.py:81`, `band_processor.py:85`, `fft_processor.py:156`), so it is paid on **every batch**.
  4. The test tree was already migrated — `tests/test_migrations.py:31,418-421` and
     `tests/concurrency/test_migration_lock_identity_4523.py:174,202` use `get_context("spawn")` with explicit
     3.14 comments. The migration was done for tests and stopped there.
- **Migration Path**: (a) document the forkserver startup cost in `ParallelConfig`; (b) if the process path is
  ever enabled, hoist the executor out of the per-call `with` block; (c) consider deleting the
  `ProcessPoolExecutor` branches if they stay permanently off — roughly 60 lines of unreachable code across 3
  files.
- **Effort**: Small
- **Risk**: No current breakage. The risk is a silent ~20x per-batch startup regression the day someone flips
  `use_multiprocessing=True`, plus dead-code drift meanwhile.

### DEP-14: The shared test render wrapper triggers two react-router v7 Future Flag deprecation warnings on every component test

- **Severity**: LOW
- **Dimension**: React/Redux/MUI
- **Location**: `auralis-web/frontend/src/test/test-utils.tsx:15`
- **Status**: NEW (the 2026-07-25 report noted react-router-dom is test-only as an informational row; it did not
  identify that the installed version emits warnings on every render)
- **Deprecated API**: `<BrowserRouter>` without a `future` prop
- **Verified Against**: react-router-dom **6.30.2**, by reading the shipped
  `node_modules/react-router/dist/index.js:938-944`:
  ```js
  if (renderFuture?.v7_startTransition === undefined) { logDeprecation("v7_startTransition", …); }
  if (renderFuture?.v7_relativeSplatPath === undefined && …) { logDeprecation("v7_relativeSplatPath", …); }
  ```
- **Replacement**: **delete the router from the test wrapper.** `src/App.tsx` has no router at all, so the fix
  is removal, not a `future` prop.
- **Affected Files**: 1 — but it is the repo-wide `render` helper, so every component test is affected.
- **Effort**: Small
- **Risk**: Warning noise only. Also see DEP-19: `react-router-dom` is a production `dependencies` entry with
  zero production importers.

### DEP-15: `.flake8` configures a tool that is not installed, not declared, and not run; `.ruff_cache` implies a second phantom linter

- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `.flake8`; `.ruff_cache/` at the repo root
- **Status**: NEW
- **Verified Against**: neither flake8 nor ruff appears in the pip freeze;
  `grep -rn "flake8\|ruff" pyproject.toml requirements*.txt Makefile .github/workflows/*.yml` → **zero matches**.
  `.pre-commit-config.yaml` runs black/isort/mypy/pylint, not flake8 or ruff.
- **Evidence**: `.flake8` sets `max-line-length = 120` while `[tool.black]` sets `line-length = 88`. Two
  line-length standards coexist and neither is enforced by anything that runs.
- **Migration Path**: delete `.flake8` and gitignore `.ruff_cache/`, or formally adopt ruff with a `[tool.ruff]`
  section and a `dev` extra entry.
- **Effort**: Small
- **Risk**: None at runtime. The cost is that four style configurations (black 88, flake8 120, an unconfigured
  ruff, pylint with a missing rcfile section) each claim authority and none is authoritative.

### DEP-16: `python-dotenv` pin diverges between the two manifests documented to mirror each other

- **Severity**: LOW
- **Dimension**: Config/CI
- **Location**: `requirements.txt` (`python-dotenv==1.2.2`) vs `auralis-web/backend/requirements.txt`
  (`python-dotenv==1.2.1`)
- **Status**: NEW
- **Verified Against**: a full diff of the two manifests' package lines — **exactly one** difference, this one.
- **Evidence**: the backend file's own header states *"It MUST mirror the root requirements.txt (the single
  source of truth)"*, and it is the manifest that actually **ships** (CI rsyncs it into
  `desktop/resources/backend/`).
- **Migration Path**: sync to 1.2.2, then extend `requirements-pin-guard.yml` to diff the **full** pin set
  rather than only the sensitive-parser allowlist — the guard exists for exactly this and did not catch it.
- **Effort**: Small
- **Risk**: Minimal for this package; it demonstrates the guard has a hole any non-allowlisted package can fall
  through. Same root cause as DEP-1.

### DEP-17: `docs/development/PYTHON_3_13_vs_3_14_COMPATIBILITY.md` states the 3.14 migration is blocked — it shipped on 2026-07-28

- **Severity**: LOW
- **Dimension**: Config/CI (documentation)
- **Location**: `docs/development/PYTHON_3_13_vs_3_14_COMPATIBILITY.md:219`
- **Status**: NEW
- **Verified Against**: the live interpreter is 3.14.0; `.python-version` pins 3.14; `requires-python = ">=3.14"`;
  `build-release.yml` sets `PYO3_USE_ABI3_FORWARD_COMPATIBILITY: 1` at three build sites and targets 3.14.
- **Evidence**: the doc's 2026-07-16 update concludes *"The 3.14 migration (and any pyo3 bump) stays blocked
  until that's resolved upstream…"*. The actual resolution was not a pyo3 bump — staying on 0.23 with the
  forward-compat flag works, and that is what shipped.
- **Migration Path**: append a dated resolution note, or move the file to `docs/archive/development-history/`
  alongside the already-archived `PYTHON_3_13_9_FINAL_DECISION.md`.
- **Effort**: Small
- **Risk**: This is the repo's most detailed 3.14 document and it sits in the **live** docs tree. It tells a
  reader the opposite of the current state and specifically mislabels the working pin (0.23) as the blocker —
  which invites someone to "fix" it by bumping to the 0.29 that is known to break.

### DEP-18: `engines` is declared only at the repo root; the frontend and desktop packages have none

- **Severity**: LOW
- **Dimension**: Node/npm/Build
- **Location**: `auralis-web/frontend/package.json`, `desktop/package.json` (no `engines` key in either)
- **Status**: NEW
- **Verified Against**: all three manifests read in full. Root declares
  `"engines": {"node": ">=24.0.0", "python": ">=3.14.0"}`; the other two declare none. All three correctly set
  `"packageManager": "pnpm@10.20.0"`.
- **Evidence**: the three packages are **not** a pnpm workspace — no `pnpm-workspace.yaml` exists anywhere, and
  each of `auralis-web/frontend/` and `desktop/` carries its own `pnpm-lock.yaml` and is installed separately
  (`package.json:16-18`). Because they are standalone installs, the root `engines` block does **not** apply to
  them: `pnpm install` inside `auralis-web/frontend/` on Node 22 gets no engine check at all. CI independently
  pins `node-version: '24'` in all five setup-node steps, confirming 24 is the real floor.
- **Migration Path**: add `"engines": {"node": ">=24.0.0"}` to both; optionally add `engine-strict=true` via
  `.npmrc` (none exists today) so it fails rather than warns.
- **Effort**: Small
- **Risk**: A contributor on Node 20/22 installs cleanly, then hits confusing failures — `@types/node@^24`,
  `vite@7` and `vitest@4` all assume modern Node — instead of a clear engine error.

### DEP-19: `react-router-dom` is a production dependency with zero production importers

- **Severity**: LOW
- **Dimension**: React/Redux/MUI
- **Location**: `auralis-web/frontend/package.json` (`dependencies`)
- **Status**: Existing — informational row in the 2026-07-25 report; **re-verified still present** 2026-07-29
- **Evidence**: `src/App.tsx` has no router; the only importer is the test wrapper at
  `src/test/test-utils.tsx:15` (see DEP-14).
- **Migration Path**: remove the router from the test wrapper, then drop the dependency.
- **Effort**: Small
- **Risk**: Dead production install weight; it also creates the warning noise in DEP-14.

### DEP-20: `@types/uuid@10` is an obsolete DefinitelyTyped stub for `uuid@14`, which ships its own types — and neither package is used

- **Severity**: LOW
- **Dimension**: Node/npm/Build + React
- **Location**: `auralis-web/frontend/package.json` (`"@types/uuid": "^10.0.0"`, `"uuid": "^14.0.0"`)
- **Status**: Existing — informational row in the 2026-07-25 report; **re-verified still present**
- **Verified Against**: read `node_modules/uuid/package.json` — it declares its own types, making the
  DefinitelyTyped stub redundant. A repo-wide grep found no importer of either package.
- **Migration Path**: drop both entries and `pnpm install`.
- **Effort**: Small
- **Risk**: None; dead install weight and a misleading signal that UUIDs are generated client-side.

### DEP-21: `asyncio.iscoroutinefunction` is deprecated in 3.14 (test-only)

- **Severity**: LOW
- **Dimension**: Python stdlib
- **Location**: `tests/backend/test_no_nested_event_loop.py:50`, `tests/concurrency/test_async_operations.py:530`
- **Status**: NEW (distinct from #4332, which covers only the `get_event_loop_policy()` fixtures)
- **Deprecated Since**: 3.14 · **Removal Version**: 3.16
- **Replacement**: `inspect.iscoroutinefunction`
- **Affected Files**: 2 test files; **zero production hits**.
- **Effort**: Small
- **Risk**: Breaks on Python 3.16. No production exposure.

### DEP-22: Legacy PEP 585/604 typing generics remain in `scripts/`

- **Severity**: LOW
- **Dimension**: Python stdlib
- **Location**: 11 files under `scripts/`
- **Status**: NEW as scoped — an extension of **Existing: #4624**, which covers only `tests/`
- **Verified Against**: `auralis/` and `auralis-web/backend/` are **100% migrated** to `list`/`dict`/`X | None`.
  Only `scripts/` and `tests/` still use `List`/`Dict`/`Optional`.
- **Effort**: Small
- **Risk**: None functional — `typing.List` et al. are soft-deprecated, not scheduled for removal. Consistency only.

### DEP-23: `populate_by_name` in `ConfigDict` is superseded by `validate_by_name`/`validate_by_alias`

- **Severity**: LOW
- **Dimension**: FastAPI/Pydantic
- **Location**: `auralis-web/backend/routers/metadata.py:53`
- **Status**: NEW
- **Deprecated Since**: pydantic 2.11
- **Verified Against**: pydantic **2.13.4** — confirmed **by execution** that it currently emits **no** warning.
- **Replacement**: `validate_by_name=True` (+ `validate_by_alias=True` if alias input is also wanted)
- **Affected Files**: 1, one line.
- **Effort**: Small
- **Risk**: None today. Housekeeping ahead of a future pydantic major.

---

## Verified clean — negative results recorded so they are not re-derived

These are not findings. They are recorded because each cost real verification effort and a future audit should
not repeat it.

**Python stdlib (D1)** — all 299 `auralis.*` modules and 109 backend modules walk-imported under
`warnings.simplefilter("always")` on 3.14.0: **0 import failures, 0 warnings**. Backend `import main` under
`-X dev` is clean. A real `HybridProcessor.process()` run emitted 0 deprecation warnings. Zero hits for
`datetime.utcnow`, every module removed in 3.12/3.13 (**including the audio ones** — `audioop`, `aifc`, `sunau`,
`chunk`, `sndhdr`), `pkg_resources`, `collections` ABCs, `locale.getdefaultlocale()`, unittest legacy aliases,
threading legacy aliases, ssl deprecations, `typing.ByteString`/`Text`, legacy `importlib.resources`, `array`
`'u'`, `ast.Str`/`Num`/`Bytes`. **PEP 649 is a verified non-issue**: SQLAlchemy `configure_mappers()` succeeds
over models combining `from __future__ import annotations` with `Mapped[...]`; all 21 Pydantic schema models
`model_rebuild(force=True)` cleanly; the one generic model with the future import
(`auralis-web/backend/routers/pagination.py`) parameterizes and round-trips fine.
*Deliberately not filed*: `os.path` vs `pathlib` — 4 incidental single-line uses against 67 pathlib files, and
`os.path` is not deprecated. That would have been inflation.

**NumPy/SciPy (D2)** — 199 modules import with zero `DeprecationWarning`/`FutureWarning` under `-W error`.
Every removed NumPy 1.24/2.0 alias, every legacy SciPy API, and every librosa deprecated symbol returned **0
hits**.

**FastAPI/Pydantic/SQLAlchemy (D3)** — the deprecation lists were built from the **installed package source**,
not memory: all 8 `pydantic/deprecated/` modules plus every `PydanticDeprecatedSince2*` site, every
`StarletteDeprecationWarning` and `FastAPIDeprecationWarning` site, the `sqlalchemy/exc.py` warning hierarchy,
and uvicorn's three deprecations — then each was grepped against the codebase. Zero hits for `class Config:` in
a model, `.dict()`/`.parse_obj()`/`.construct()`/`__fields__`, `@validator`/`@root_validator`,
`orm_mode`/`schema_extra`/`min_items`/`regex=`/`const=`, `@app.on_event`, `ORJSONResponse`/`UJSONResponse`,
deprecated `starlette.status` constants, `starlette.middleware.wsgi`, `run_in_threadpool`, `TemplateResponse`.
SQLAlchemy production code is fully 2.0-style (`DeclarativeBase` + `Mapped[]` + `mapped_column`, zero
`session.query()`, zero string-`execute()`); the surviving `Column()` calls are association `Table()`s, which is
correct 2.0 idiom, and the bare `cursor.execute("PRAGMA …")` calls are raw sqlite3 DBAPI, correctly outside the
repository rule. `pydantic-settings` is installed but `BaseSettings` is never imported — zero exposure.

**React/Redux/MUI (D4)** — zero React 18 removed APIs; zero on the entire React 19 removal path (`propTypes`,
string refs, `findDOMNode`, `createFactory`, legacy context, `UNSAFE_*`); zero `React.FC`; all 40+ `act` imports
come from `@testing-library/react`, the correct 18.3 path; every RTK 2 breaking change absent; only 5
`@deprecated` markers exist across `@mui/material/**/*.d.ts` and **none is used** (`Grid2` is a stale local
alias for MUI 9's modern `Grid`); every TS-5.0 option that TS 6.0 will hard-error on is absent and
`moduleResolution` is already `"bundler"` in both configs; Vitest 4 config is already migrated with
provenance comments; `@tanstack/react-query` v5 clean.
**Three inflation traps caught and cleared**: ~80 `.defaultProps` grep hits were **all** false positives
(test-local objects named `defaultProps` spread into JSX — the anchored grep
`^\s*[A-Z]\w*\.defaultProps\s*=` returns zero); ~60 `createStore`/`connect(` hits were all WebSocket/AudioNode/
IntersectionObserver `connect()` or RTK-backed test helpers; `waitForElement` hits are locally-defined helpers
of the same name, not the removed DTL API.

**Electron main/preload (D5)** — see DEP-3 evidence. Also, a targeted grep for deprecated Node core APIs
(`fs.exists(`, `url.parse`, `url.resolve`, `new Buffer(`, `querystring`, `util.isArray`, `util._extend`,
`process.binding`, `require.extensions`, `crypto.createCipher(`, `fs.rmdir(`, `os.tmpDir`, `punycode`,
`assert.equal`) across `build.js`, `dev.js`, `package.js`, `desktop/main.js`, `desktop/preload.js` and
`auralis-web/frontend/scripts/*` returned **zero hits**. `punycode@2.3.1` in both lockfiles is the **userland
package** (via `tr46` → jsdom's `whatwg-url`), which is the officially recommended replacement for Node's
deprecated built-in — explicitly cleared, not a finding. Vite 7 / Vitest 4 config keys are clean.

**Config/CI (D8)** — no `actions/upload-artifact@v3` or `download-artifact@v3` (hard-disabled by GitHub in Jan
2025), no `set-output`/`save-state`, no node12/node16 runtimes, no retired runners (`ubuntu-latest`,
`ubuntu-24.04`, `windows-2025`, `macos-15` are all current). `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` is set at all
three Rust build sites in `build-release.yml`. `pyproject.toml` has **no** `[tool.pytest.ini_options]` section —
no silent-precedence trap with `pytest.ini`. Neither `setup.py` nor `setup.cfg` exists; the build backend is
hatchling. pyenv references survive only in `docs/archive/development-history/` and in prose stating uv
*replaces* pyenv — the sole live-tree exception is DEP-17.

---

## Dependency Upgrade Roadmap

| # | Change | Blocks / Depends on | Breaks |
|---|---|---|---|
| 1 | Pin `starlette==`; reconcile numpy/scipy/soundfile/fastapi/pydantic/uvicorn/python-multipart pins with the venv (**DEP-1**) | Nothing — do first | Nothing expected; re-run backend + DSP tests scoped |
| 2 | `npm` → `pnpm` in `build.js`/`dev.js`/`package.js` + scripts (**DEP-2**) | Independent | Nothing; argument vectors identical |
| 3 | Electron 39 → 42/43 (**DEP-3**) | After #2, so packaging runs under pnpm | Packaging/Chromium regressions only; no source changes needed |
| 4 | GitHub Actions node20 → node24 majors (**DEP-4**) | Independent | Verify `upload-artifact@v4→v7` consumers |
| 5 | Add `pytest-timeout`, set `asyncio_default_fixture_loop_scope` (**DEP-8**, **DEP-9**) | Independent | DEP-9 is behavioral — validate async fixtures scoped |
| 6 | Add `httpx2` for `TestClient` (**DEP-7**) | After #1 (Starlette pin decides whether this is needed) | Test-only |
| 7 | Route m4a/aac/wma through `unified_loader` (**DEP-5**) | Independent | Changes fingerprints for those containers — expect a re-fingerprint |
| 8 | `pre-commit autoupdate` + drop `python3.9` (**DEP-11**) | Independent | Reformatting churn on first run |
| 9 | numpy 2.5 / librosa 1.0 | **Blocked** on numba supporting numpy ≥2.5 | Would break DEP-5's audioread path — fix DEP-5 first |
| 10 | pyo3 / numpy-rs 0.23 → newer | **Blocked upstream** (numpy-rs 0.29 ABI failure) | Do not attempt; see DEP-17 |

## Migration Effort Summary

**Small (< 10 call sites)** — DEP-1, DEP-3, DEP-4, DEP-5, DEP-6, DEP-7, DEP-8, DEP-9, DEP-10, DEP-11, DEP-12,
DEP-13, DEP-14, DEP-15, DEP-16, DEP-17, DEP-18, DEP-19, DEP-20, DEP-21, DEP-22, DEP-23
**Medium (10-50)** — DEP-2 (12 live invocation sites across 9 files)
**Large (50+)** — none.


---

## Findings — Dimension 6 (Rust / PyO3 / Cargo / maturin)

> Merged mechanically from `D6-rust-pyo3.md` after the audit coordinator crashed (API 500) mid-merge.
> D6-3 and D6-4 were already merged above as DEP-24 and DEP-25 and are not repeated here.
> Findings below retain their original `D6-n` identifiers rather than being renumbered into the `DEP-n` sequence.

### D6-1: `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` silently compiles the crate against the **limited API** with no `abi3-pyXY` floor declared

- **Severity**: MEDIUM
- **Dimension**: Rust / PyO3
- **Location**: `vendor/auralis-dsp/Cargo.toml:12`, `vendor/auralis-dsp/.cargo/config.toml:21-22`
- **Status**: NEW
- **Deprecated API**: n/a — this is a *build-configuration correctness* finding surfaced while assessing the pinned-pyo3 workaround, not a deprecated symbol.
- **Verified Against**: pyo3 0.23.5 / pyo3-ffi 0.23.5 / pyo3-build-config 0.23.5 sources in `~/.cargo/registry/src/index.crates.io-*/`, plus the crate's **own real build output** in `vendor/auralis-dsp/target/`.
- **Evidence**:

  1. The flag does not merely "suppress a check" (which is what the in-repo comment claims). In `pyo3-build-config-0.23.5/src/impl_.rs:846-849`:
     ```rust
     fn is_abi3() -> bool {
         cargo_env_var("CARGO_FEATURE_ABI3").is_some()
             || env_var("PYO3_USE_ABI3_FORWARD_COMPATIBILITY").map_or(false, |os_str| os_str == "1")
     }
     ```
     Setting the env var makes `is_abi3()` return `true` **as if the `abi3` cargo feature had been enabled**, which at `impl_.rs:191-195` emits:
     ```rust
     if self.abi3 && !self.is_free_threaded() {
         out.push("cargo:rustc-cfg=Py_LIMITED_API".to_owned());
     }
     ```

  2. This is not theoretical — it is what actually happened. The two Python-3.14 build-script outputs in the crate's own `target/` contain `Py_LIMITED_API`; the Python-3.13 ones do not:
     ```
     target/release/build/pyo3-ffi-d4b55c2c5a208ac1/output:
       cargo:rustc-cfg=Py_3_14
       cargo:rustc-cfg=Py_LIMITED_API          <-- limited API ON
     target/release/build/pyo3-ffi-8bdeeb2ac907f8a9/output:
       cargo:rustc-cfg=Py_3_13
       (no Py_LIMITED_API)                      <-- full API
     ```
     So the **same source builds against two different CPython ABIs depending only on which interpreter is on PATH.**

  3. Because `Cargo.toml:12` declares no `abi3-pyXY` feature, `get_abi3_version()` (`impl_.rs:854-858`) returns `None`, so `fixup_for_abi3_version` (`impl_.rs:713-736`) never lowers the target version and **no minimum Python is pinned into the limited-API build**. Note also that pyo3 0.23's `ABI3_MAX_MINOR` is `12` (`impl_.rs:43`) — even if a floor were wanted, `abi3-py314` does not exist at this pin.

  4. maturin decides the wheel tag from the *Cargo.toml features*, not from the env var, so the produced artifact is tagged version-specific despite being an actual limited-API binary. Confirmed by the two wheels sitting in `vendor/auralis-dsp/target/wheels/`:
     ```
     auralis_dsp-0.1.0-cp313-cp313-linux_x86_64.whl   (built full-API)
     auralis_dsp-0.1.0-cp314-cp314-linux_x86_64.whl   (built limited-API, still tagged cp314-cp314)
     ```

- **Impact**: The 3.14 desktop wheel that ships in the installer is a `Py_LIMITED_API` binary that nobody documented as such. Consequences: (a) any pyo3 API that is `#[cfg(not(Py_LIMITED_API))]` silently disappears from the 3.14 build but is present on 3.13, so a Rust change can compile locally on 3.13 and fail only in the release job; (b) the crate loses the one benefit it is actually paying for — an ABI-stable wheel — because the tag is version-specific; (c) any future perf comparison between the 3.13 and 3.14 builds is apples-to-oranges (limited API goes through function calls where the full API uses macros).
- **Replacement / Migration Path**: no version bump required, and none is recommended. Either (1) accept and *document* the limited-API mode in `.cargo/config.toml`'s comment block (it currently says only "This flag tells it to proceed"), and add a CI assertion that `Py_LIMITED_API` is present in the release build so the ABI can't flip silently; or (2) if a portable wheel is wanted, that requires the pyo3 bump that `UPGRADE_PLAN.md` already documents as blocked — so (1) is the only action available today.
- **Affected Files**: 2 production build-config files (`Cargo.toml`, `.cargo/config.toml`). No test files.
- **Effort**: Small (<10 sites) — comment/doc + one CI assertion.
- **Risk**: Silent ABI divergence between a contributor's 3.13 box and the 3.14 release build; a limited-API-incompatible pyo3 call added to `py_bindings.rs` would pass local checks and break only at release.

---

### D6-2: Free-threaded CPython 3.14 (`python3.14t`) is an **unsuppressible** hard build failure for this crate

- **Severity**: LOW (forward-looking; no free-threaded interpreter is in use today)
- **Dimension**: Rust / PyO3
- **Location**: `vendor/auralis-dsp/Cargo.toml:12` (pyo3 0.23 pin), `pyproject.toml:10` (`requires-python = ">=3.14"`)
- **Status**: NEW
- **Verified Against**: pyo3-ffi 0.23.5 `build.rs:56-72`, read from the cargo registry.
- **Evidence**: `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` is checked only *after* a free-threaded guard that cannot be bypassed:
  ```rust
  if interpreter_config.version > versions.max {
      ensure!(!interpreter_config.is_free_threaded(),
          "The configured Python interpreter version ({}) is newer than PyO3's maximum supported version ({})\n\
           = help: The free-threaded build of CPython does not support the limited API so this check cannot be suppressed.");
      ensure!(env_var("PYO3_USE_ABI3_FORWARD_COMPATIBILITY").map_or(false, |os_str| os_str == "1"), ...);
  }
  ```
  Because the whole 3.14 story here rests on the forward-compat flag, and that flag is explicitly unavailable on free-threaded builds, `maturin develop` under `python3.14t` fails with a message that offers no workaround.
- **Impact**: `requires-python = ">=3.14"` accepts `3.14t`. A contributor (or a future CI image) that picks the free-threaded 3.14 build hits a hard, un-workaroundable failure with a misleading "check if an updated version of PyO3 is available" hint — while the real answer is "use the GIL build, the pin is deliberate".
- **Migration Path**: no code change. Add one line to `.cargo/config.toml`'s comment block and to `docs/CONTRIBUTING.md`: the GIL-enabled CPython 3.14 build is required; free-threaded (`3.14t`) is not supported at the pinned pyo3.
- **Effort**: Small.
- **Risk**: A contributor onboarding on a free-threaded interpreter is hard-blocked with no documented escape.

---

### D6-5: `Cargo.toml` declares no `rust-version` (MSRV) field

- **Severity**: LOW
- **Dimension**: Cargo
- **Location**: `vendor/auralis-dsp/Cargo.toml:1-4`
- **Status**: NEW (adjacent to #4531, which covers `rust-toolchain.toml`/lockfile but not the manifest's `rust-version` key)
- **Verified Against**: full read of the 20-line manifest; local toolchain is `rustc 1.96.0`.
- **Evidence**:
  ```toml
  [package]
  name = "auralis-dsp"
  version = "0.1.0"
  edition = "2021"
  # no rust-version
  ```
  All three release jobs use `- uses: dtolnay/rust-toolchain@stable` (`build-release.yml:80`, `:210`, `:316`) — a floating `stable`, so every release builds with whatever rustc was current that day, with no floor recorded anywhere and no ceiling either.
- **Impact**: `cargo` cannot emit its "package `auralis-dsp` requires rustc X" diagnostic; a contributor on an older stable gets a raw type/borrow error instead. Nothing in the repo records that the crate is built and tested on 1.96 — combined with the untracked `Cargo.lock` (#4531) and the floating `@stable` toolchain, there is no reproducible Rust build record at all: neither the compiler version nor the dependency graph that produced any shipped wheel can be recovered.
- **Migration Path**: add `rust-version = "1.85"` (or whatever floor is verified) to `[package]`. This is independent of the pyo3 pin.
- **Effort**: Small (1 line).
- **Risk**: Low; a confusing failure mode for new contributors and for any future MSRV-sensitive dependency bump.

---

### D6-6: `python setup.py build_ext --inplace` recommended in Rust DSP docs

- **Severity**: LOW (documentation only)
- **Dimension**: Python packaging / docs
- **Location**: `docs/features/README_RUST_DSP_INTEGRATION.md:168`
- **Status**: NEW
- **Deprecated API**: direct `python setup.py <command>` invocation
- **Deprecated Since**: setuptools 58.3 (`SetuptoolsDeprecationWarning`); escalated to a hard error for most commands in setuptools 80.
- **Verified Against**: repo has **no `setup.py` at all** — the root build backend is `hatchling.build` (`pyproject.toml:1-3`) and the Rust crate is built by maturin.
- **Evidence**: `maturin develop  # or python setup.py build_ext --inplace` — the alternative offered cannot work: there is no `setup.py` to run, and even if there were, `setup.py build_ext` is the canonical deprecated invocation.
- **Migration Path**: delete the ` # or python setup.py build_ext --inplace` clause. Same file also carries `cargo build --release` / `cargo test --release` at lines 56/65/184 — those are fine, and (because they are documented as run from inside `vendor/auralis-dsp/`) they pick up `.cargo/config.toml`.
- **Effort**: Small (1 line).
- **Risk**: A contributor following the fallback wastes time on a command that cannot succeed.

---

### D6-7: Benchmark test hardcodes a `cp313` wheel filename that Python 3.14 can never produce

- **Severity**: LOW (test-only)
- **Dimension**: Rust build / test rot
- **Location**: `tests/test_phase5_rust_benchmark.py:281-296`
- **Status**: NEW
- **Verified Against**: actual artifacts in `vendor/auralis-dsp/target/wheels/` — the current build produces `auralis_dsp-0.1.0-cp314-cp314-linux_x86_64.whl`; the path in the test is `...-cp313-cp313-manylinux_2_35_x86_64.whl`.
- **Evidence**:
  ```python
  wheel_path = (Path(__file__).parent.parent
      / "vendor/auralis-dsp/target/wheels/auralis_dsp-0.1.0-cp313-cp313-manylinux_2_35_x86_64.whl")
  if wheel_path.exists():
      subprocess.run(["pip", "install", str(wheel_path)], check=True)
  else:
      subprocess.run(["maturin", "build", "--release"], cwd=.../"vendor/auralis-dsp", check=True)
  ```
  Two separate bits of rot: the interpreter tag is `cp313` (dead under `requires-python = ">=3.14"`), and the platform tag is `manylinux_2_35` while a local `maturin build` emits `linux_x86_64`. The `.exists()` check therefore always fails, so the branch silently degrades to a full release build inside a test.
  Positive note: the fallback's `cwd=` **is** the crate dir, so `.cargo/config.toml` applies and the rebuild would actually succeed. This is test-only and the test is `@pytest.mark.benchmark`-gated, so it is not in the default path.
- **Migration Path**: glob `target/wheels/auralis_dsp-*.whl` and pick the newest instead of hardcoding a tag; or drop the auto-install block entirely and skip the benchmark when the extension is missing (which is what `tests/vendor/test_rust_panic_handler.py:45` already does correctly).
- **Effort**: Small.
- **Risk**: A benchmark run triggers an unexpected multi-minute release compile; low blast radius.

---

### D6-8: GitHub Actions still on Node-20 action majors — GitHub is force-upgrading them and warning on every run *(cross-dimension: CI, flag for dedup)*

- **Severity**: LOW
- **Dimension**: CI tooling *(found via `rust-audit.yml`; **may belong to another dimension's scope — dedup before filing**)*
- **Location**: 6 workflow files — `rust-audit.yml`, `backend-tests.yml`, `frontend-test.yml`, `frontend-typecheck.yml`, `lockfile-guard.yml`, `requirements-pin-guard.yml`
- **Status**: NEW
- **Deprecated API**: action majors whose bundled runtime is `node20`
- **Deprecated Since**: announced 2025-09-19; runners now **force** these onto Node 24 and warn
- **Verified Against**: a **live 2026-07-27 CI log**, not release notes — `gh run view 30255593758 --log-failed`:
  ```
  Node 20 is being deprecated. This workflow is running with Node 24 by default. If you need to
  temporarily use Node 20, you can set the ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true ...
  ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being
  forced to run on Node.js 24: actions/checkout@v4.
  ```
- **Evidence**: the repo is **half-migrated**, which is the real signal — both majors of the same action coexist across workflows (`grep -rn 'uses:' .github/workflows/ | sort | uniq -c`):
  | Action | Old (node20) | New | 
  |---|---|---|
  | `actions/checkout` | **9× @v4** | 5× @v6 |
  | `actions/upload-artifact` | **2× @v4** | 4× @v7 |
  | `actions/setup-python` | **2× @v5** | 4× @v6 |
  | `actions/setup-node` | **2× @v4** | 3× @v6 |
  | `pnpm/action-setup` | **2× @v4** | 3× @v6 |

  So someone already did this upgrade — on `build-release.yml` and the newer workflows — and the six older files were missed. Not on current majors: `taiki-e/install-action@v2`, `softprops/action-gh-release@v3`, `actions/download-artifact@v8`, `dtolnay/rust-toolchain@stable` (all fine).
- **Migration Path**: bump the 17 stale `uses:` lines to the majors already proven working elsewhere in the same repo. Mechanical, no behaviour change expected.
- **Effort**: Small.
- **Risk**: Currently only warnings — GitHub is silently running them on Node 24 anyway. When the forced-compat window closes these six workflows stop running, which includes both lockfile guards and the backend test gate.

---

## Informational — known-blocked pin (NOT a finding, do not file)

`pyo3 = "0.23"` / `numpy = "0.23"` (`vendor/auralis-dsp/Cargo.toml:12-13`) is a **deliberate, documented pin**, not drift. `vendor/auralis-dsp/UPGRADE_PLAN.md` records the reason in full: bumping to 0.29 compiles but every array-accepting call then raises `TypeError: 'ndarray' object is not an instance of 'ndarray'`, because numpy-rs 0.29 targets NumPy's ABI v2 and is incompatible with the NumPy 2.x in use; this reproduces on 3.13 as well, so it is a rust-numpy problem, not a Python-version one. Two RUSTSEC advisories (RUSTSEC-2025-0020 `PyString::from_object`, RUSTSEC-2026-0177 `PyCFunction::new_closure`) are `--ignore`d in CI with a verified-unreachable justification — I re-verified reachability independently: `grep` over all 19 `src/*.rs` finds **zero** occurrences of either API. **No version bump is recommended.** (The only live concern attached to this pin is D6-3: the gate that is supposed to watch it cannot read its lockfile.)

`ndarray = "0.16"` is current (0.16 is the latest major). `edition = "2021"` is not deprecated — edition 2024 is available at rustc 1.96 but 2021 remains fully supported; migrating is discretionary, not a deprecation, so it is deliberately **not** filed.

## Verified CLEAN — checks that found nothing (recorded so they are not re-run)

These were all searched and came back empty. Reporting the negatives explicitly, per the anti-inflation rule.

| Check | Result | Command |
|---|---|---|
| **`py.allow_threads` on every exported fn** | **CLEAN — all 11/11 release the GIL.** `hpss:111`, `yin:158`, `chroma_cqt:201`, `detect_tempo:272`, `envelope_follow:317`, `compress:414`, `limit:501`, `compute_fingerprint:580`, `apply_multiband_eq:675`, `detect_onsets:712`, `process_chunks:768` — all in `py_bindings.rs`, each wrapping the compute in `py.allow_threads(\|\| catch_unwind(...))` with a `#2447` reference. The severity-table row "Rust DSP holds GIL during long compute → MEDIUM" **does not apply**. | `grep -rn allow_threads src/` |
| `IntoPy` / `ToPyObject` (deprecated at pyo3 0.23 → `IntoPyObject`) | 0 hits | `grep -rn 'IntoPy\b\|ToPyObject' src/` |
| `*_bound` constructors (`PyModule::new_bound`, `PyArray::from_vec_bound`, `wrap_pyfunction_bound!`, `PyList::new_bound`, …) | 0 hits. Code already uses the unsuffixed 0.23 names: `wrap_pyfunction!` (`py_bindings.rs:29-64`), `PyDict::new(py)` (`:427,:514,:594,:722,:778`), `into_pyarray(py)` (`:121,:168,:211,…`). | `grep -rn '_bound' src/` |
| `Python::acquire_gil` / `GILPool` (removed) | 0 hits | `grep -rn 'acquire_gil\|GILPool' src/` |
| gil-refs API (`&PyAny` style; feature removed in 0.23) | 0 hits — module signature is already the Bound form: `fn auralis_dsp(_py: Python<'_>, m: &Bound<'_, PyModule>)` (`py_bindings.rs:27`), and all array params are `PyReadonlyArray1/2<'_, T>`. | read of `py_bindings.rs` |
| `#[pyfn]` (→ `#[pyfunction]` + `wrap_pyfunction!`) | 0 hits — all 11 wrappers use `#[pyfunction]` with `#[pyo3(signature = ...)]`. | `grep -rn '#\[pyfn\]' src/` |
| `unsafe` blocks | 0 hits across all 19 files | `grep -rn unsafe src/` |
| ndarray 0.16 deprecations: `.into_shape()`, `Zip::apply`, `.genrows()`, `.gencolumns()`, `.scalar_sum()`, `azip!`, `stack!` | **0 hits for every one** | `grep -rn 'into_shape\|Zip::apply\|genrows\|gencolumns\|scalar_sum\|azip!\|stack!' src/` |
| Deprecated Cargo.toml syntax: wildcard `*` versions, git deps without `rev`, deprecated `crate-type` values | none. All 7 deps use caret ranges; `crate-type = ["cdylib", "rlib"]` are both current values. | full read of Cargo.toml |
| maturin `[tool.maturin]` deprecated keys (`sdist-include`, `manylinux`→`compatibility`, `bindings`, `python-source`/`module-name`) | **N/A — no `[tool.maturin]` table exists.** No `pyproject.toml` under `vendor/`; the root one uses `hatchling.build`. maturin runs on pure CLI defaults. | `find ./vendor -name pyproject.toml`; `grep maturin pyproject.toml` |
| Other Cargo.toml files in repo | only one exists | `find . -name Cargo.toml` excl. node_modules/target |

## Build-path coverage for `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` — the documented command DOES work

The parent's hypothesis was that `cd vendor/auralis-dsp && maturin develop`, as documented in CLAUDE.md with no env var, cannot work. **It does work** — the flag is supplied by a tracked cargo config, not by the shell:

`vendor/auralis-dsp/.cargo/config.toml:21-22` (tracked — confirmed in `git ls-files`):
```toml
[env]
PYO3_USE_ABI3_FORWARD_COMPATIBILITY = "1"
```
Cargo discovers `.cargo/config.toml` by walking up from the **current working directory**, and applies `[env]` to the processes it spawns (build scripts included). Since every documented invocation `cd`s into the crate first, all of them are covered.

| Build path | Location | Env var supplied? |
|---|---|---|
| `cd vendor/auralis-dsp && maturin develop` (CLAUDE.md:28, AGENTS.md:32/156, README.md:138, docs/CONTRIBUTING.md:28, docs/architecture/module-map.md:129, docs/subsystems/dsp-engine.md:219, verify-release.md:114) | cwd inside crate | ✅ via `.cargo/config.toml` |
| `cargo build --release` / `cargo test --release` (docs/features/RUST_DSP_STATUS.md:51-52, README_RUST_DSP_INTEGRATION.md:56/65) | documented as run from inside the crate | ✅ via `.cargo/config.toml` |
| `build.js` → `buildRustDsp()` | `build.js:170-176`, `cwd = vendorDspDir` **and** explicit `{ PYO3_USE_ABI3_FORWARD_COMPATIBILITY: '1' }` | ✅ (belt and braces) |
| `.github/workflows/build-release.yml` (3 jobs) | lines ~116 / ~234 / ~337, explicit `env:` | ✅ (pre-confirmed by parent) |
| `tests/test_phase5_rust_benchmark.py:292` `maturin build --release` | `cwd=.../vendor/auralis-dsp` | ✅ via `.cargo/config.toml` (see D6-7 for unrelated rot in that block) |
| `.github/workflows/rust-audit.yml` | `cargo audit` only — never compiles | N/A (but see D6-3) |
| `desktop/`, `dev.js`, `scripts/` | grep for `cargo`/`maturin`/`rust` → **0 hits**; none of them build the crate | N/A |

**One residual gap worth knowing**: cargo resolves `.cargo/config.toml` from the *cwd*, not from `--manifest-path`. Any future invocation of the form `cargo build --manifest-path vendor/auralis-dsp/Cargo.toml` run from the repo root would **not** pick the flag up and would hard-fail on Python 3.14. No such invocation exists today; noting it so a future CI step doesn't reintroduce the breakage. Not filed as a finding (no live call site).

## Coverage

**Examined:**
- `vendor/auralis-dsp/Cargo.toml` (full, 20 lines), `vendor/auralis-dsp/.cargo/config.toml` (full), `vendor/auralis-dsp/UPGRADE_PLAN.md` (full).
- `vendor/auralis-dsp/src/` — **all 19 `.rs` files** swept by grep for every pyo3-0.23 and ndarray-0.16 deprecation in the task list; `py_bindings.rs` (785 lines) and `lib.rs` (53 lines) read in full line-by-line.
- `.github/workflows/rust-audit.yml` (full), `.github/workflows/build-release.yml` (Rust/maturin steps), `build.js:60-200`, `tests/test_phase5_rust_benchmark.py:275-310`, root `pyproject.toml` build-system/requires-python.
- Repo-wide grep for `maturin|cargo build|cargo check|cargo test|cargo audit|PYO3_USE_ABI3` across `*.py *.js *.cjs *.mjs *.sh *.yml *.yaml *.toml *.json *.md Makefile` (node_modules/, target/ excluded) — every hit triaged into the build-path table above.
- **Upstream crate sources read as primary evidence** (not release notes, not memory): `pyo3-build-config-0.23.5/src/impl_.rs` (`is_abi3`, `get_abi3_version`, `fixup_for_abi3_version`, the `Py_LIMITED_API` emit site, `ABI3_MAX_MINOR`, `MINIMUM_SUPPORTED_VERSION`) and `pyo3-ffi-0.23.5/build.rs:40-130` (`ensure_python_version`, the free-threaded guard).
- **The crate's own build artifacts** as ground truth: all 8 `target/{debug,release}/build/pyo3-ffi-*/output` files (which of them emit `Py_LIMITED_API`), and `target/wheels/` (`cp313` + `cp314` wheels present).

- **Live CI history** for the Rust gate: `gh run list --workflow=rust-audit.yml --limit 8` and `gh run view 30255593758 --log-failed` (read-only queries).

**Commands run** (all read-only): `rustc --version`, `cargo --version`, `git check-ignore -v vendor/auralis-dsp/{Cargo.lock,target}`, `git ls-files vendor/auralis-dsp/`, `find` for `Cargo.toml`/`pyproject.toml`/`rust-toolchain*`/`benches`, multiple `grep -rn` over `src/`, `.github/workflows/` and the repo, reads of the cargo-registry crate sources, and the two `gh` queries above. **No writes to the repo, no git mutations, no dependency changes.**

**NOT reached / deliberately skipped:**
- **`cargo check` was NOT run.** `target/` *is* gitignored (verified: `.gitignore:184`), so the stated precondition was met — but a check would have had to recompile against the 3.14 interpreter, and the existing `target/` already contains build outputs from *both* 3.13 and 3.14 configurations (see the 8 differing `pyo3-ffi-*` hashes). Running it risked a long rebuild inside the 420 s budget while also mutating a build cache that other concurrently-running audit agents may be reading. Direct source-level evidence from the registry crates plus the recorded build outputs answered every question the compile would have, so this trade was taken deliberately. **Consequence: any deprecation warning that only `rustc` emits — e.g. a `#[deprecated]` on a transitively-used `rustfft`/`realfft`/`rayon`/`num-complex` API — is unverified by this report.** Grep-level checks of pyo3 and ndarray deprecations are complete and independent of this.
- `cargo update`, `cargo add`, `cargo fix`, `maturin develop` — all forbidden, not run.
- `criterion` 0.5 (dev-dependency) was not audited for deprecated APIs. Confirmed there is **no `benches/` directory** (`ls -d vendor/auralis-dsp/benches` → does not exist) and no `criterion` reference in any `src/*.rs`, so the dev-dependency is dead weight — noted, not filed (it is dead-code/tech-debt, not a deprecation).
- Rust unit tests (`#[cfg(test)] mod tests` inside the 19 files) were swept by the same greps but not read individually.
- Only the `rust-audit.yml` CI history was pulled. Other workflows' run histories were not inspected, so D6-8's blast-radius claim (which workflows would stop running) is from the workflow definitions, not observed failures.

status: complete

---

## Findings — Dimension 7 (Internal deprecations / retired-architecture residue)

> Merged mechanically from `D7-internal.md` after the audit coordinator crashed (API 500) mid-merge.
> Findings retain their original `D7-n` identifiers rather than being renumbered into the `DEP-n` sequence.

### D7-1: `LibraryManager` — deprecation promise ("removed in v2.0.0") is now keepable; ZERO production callers remain, but the class + its dead cache layer (626 LOC) are still shipped
- **Severity**: MEDIUM
- **Dimension**: Internal (self-declared)
- **Location**: `auralis/library/manager.py:1-361` (whole file); re-export `auralis/library/__init__.py:12,21`; orphaned dependency `auralis/library/cache.py:1-265`
- **Status**: NEW (the `#4619` work that made this removable is done; the removal itself is not filed. Adjacent open issue #3770 is about cache invalidation *behaviour* on this class, not its removal.)
- **Deprecated API**: `auralis.library.manager.LibraryManager` (subclass of `LibraryDatabase`)
- **Deprecated Since**: v1.1.0 (stated at `manager.py:44`)
- **Removal Version**: **v2.0.0**, promised in the runtime warning text (`manager.py:79`) and the class docstring. Current version is **1.5.1** — the deadline has NOT passed, but the stated blocker has been cleared.
- **Verified Against**: live source at HEAD (`9e03236c`), `auralis/version.py` = `1.5.1`. Verified by grepping every `.py` under `auralis/`, `auralis-web/`, `scripts/`, `desktop/`.
- **Replacement**: `LibraryDatabase` + `db.repositories.<repo>` (RepositoryFactory)

**VERIFICATION OF THE `_audit-common.md` CLAIM** — the claim is *"no longer constructed on the startup path (#4619)"*. **The claim is TRUE and is in fact understated.** Reality today:

| Category | Count | Evidence |
|---|---|---|
| **Live production constructors (`LibraryManager(...)`)** | **0** | No `LibraryManager(` call exists anywhere under `auralis/`, `auralis-web/`, or `desktop/`. Backend startup builds `LibraryDatabase()` at `auralis-web/backend/config/startup.py:307`. The artwork CLI at `auralis/cli/fetch_artwork.py:146-148` documents that it used to construct it and no longer does. |
| **Live production *importers*** | **1** | `auralis/library/__init__.py:12` — `from .manager import LibraryManager`, re-exported in `__all__` at line 21. This is a pure public-API re-export; nothing else in production imports the name. |
| **Non-test, non-production (dev script) constructors** | **1** | `scripts/development/profile_fingerprint_memory.py:51,63` — a memory-profiling dev script, not on any runtime path. |
| **Test files referencing it** | **65 files / 129 `LibraryManager(` construction sites** | incl. `tests/conftest.py:273` and `tests/conftest.py:442` (two shared fixtures — these two fixtures are what fan the usage out to ~63 other files) |
| **Remaining production mentions** | **19** | all *comments/docstrings* saying "no LibraryManager fallback" or "#4619: ... not the deprecated LibraryManager" — zero code. |

**The DeprecationWarning is NOT filtered.** `pytest.ini:105-120` sets `default::DeprecationWarning` and explicitly documents (lines 116-119) that first-party `auralis.*` warnings are deliberately NOT filtered. So the 129 test construction sites are all currently emitting the "will be removed in v2.0.0" warning on every run — noise that is now purely self-inflicted, since no production code needs the class.

**Collateral dead code — `auralis/library/cache.py` (265 lines) is now reachable ONLY through the deprecated facade.** Verified importers of `auralis.library.cache`:
```
auralis/library/manager.py:21:from .cache import cached_query, get_cache_stats, invalidate_cache   <-- the ONLY production importer
```
(`auralis-web/backend/main.py:83`'s `import cache as _cache_probe` resolves to the *backend's* `auralis-web/backend/cache/` package, a different module — not this one.) `manager.py:60-64` already admits this in its own docstring: *"Nothing in production reads through them any more, so the cache — and the invalidation calls paired with it — are live for legacy callers only."* So the ~7 `@cached_query`-decorated methods, all the `invalidate_cache()` bookkeeping in `delete_track`/`update_track`/`record_track_play`, and the whole 265-line cache module are dead weight in the shipped package. This also means **open issue #3770 (cache invalidation on LibraryManager) is arguably resolved-by-deletion** rather than needing a behavioural fix.

- **Affected Files**: 3 production (`manager.py`, `cache.py`, `library/__init__.py` re-export) + 1 dev script + 65 test files
- **Migration Path**: (1) migrate the two `tests/conftest.py` fixtures (lines 273, 442) to `LibraryDatabase` — that single change covers the bulk of the 129 sites since most tests consume the fixtures; (2) mechanically rewrite the remaining direct `LibraryManager(` constructions in `tests/backend/test_boundary_*.py` (the largest cluster) and `scripts/development/profile_fingerprint_memory.py`; (3) map the ~10 facade-only method names used by tests (`add_track`, `search_tracks`, `get_all_tracks`, `create_playlist`, `get_library_stats`, `scan_directories`, …) to their repository equivalents; (4) delete `manager.py`, `cache.py`, and the `__init__.py` re-export; (5) drop `tests/backend/test_cache_invalidation.py` + `tests/mutation/test_cache_mutations_*.py` (3 files) which test only the dead cache.
- **Effort**: Medium (≈130 test sites, but mechanically uniform and fixture-concentrated)
- **Risk**: Low to production (zero production callers). Risk is entirely in test churn. Leaving it: 626 LOC of unreachable code ships in every build, `library.cache` looks live to any reader, and the v2.0.0 promise silently rots for another minor cycle.

### D7-2: Two rival `wav_encoder.py` modules — only ONE defines `WAVEncoderError`, so the backend's error taxonomy silently misclassifies half of all WAV write failures; 2 of the 4 public helpers are dead
- **Severity**: MEDIUM
- **Dimension**: Internal (duplicate implementation / incomplete migration)
- **Location**: `auralis-web/backend/encoding/wav_encoder.py:1-126` vs `auralis-web/backend/core/encoding/wav_encoder.py:1-258`; misclassification at `auralis-web/backend/core/processing_engine.py:57-68` + `core/encoding/wav_encoder.py:156-158`
- **Status**: NEW
- **Deprecated API**: neither module is *marked* deprecated — that is the problem. Two live modules with the same filename and overlapping purpose, and no stated migration direction.
- **Deprecated Since**: n/a (undeclared duplication; the older `encoding/` package dates to 2025, `core/encoding/` to 2024 per file headers)
- **Removal Version**: not scheduled
- **Verified Against**: live source at HEAD; both files read in full; all importers grepped across `auralis-web/`, `auralis/`, `tests/`.

**CORRECTION TO THE AUDIT PREMISE**: the brief states *"Two live `WAVEncoderError` classes exist; an `except` on one will NOT catch the other."* **That is not the case at HEAD.** `grep -rn 'class WAVEncoderError'` returns exactly **one** definition:
```
auralis-web/backend/encoding/wav_encoder.py:31:class WAVEncoderError(Exception):
```
`core/encoding/wav_encoder.py` defines **no** exception class at all. So there is no two-class shadowing bug. **But the underlying concern is real, in a worse form** — see below.

**THE ACTUAL BUG: the two encoders raise incompatible exception types for the same failure.**

| | `encoding/wav_encoder.py` (`encode_to_wav`) | `core/encoding/wav_encoder.py` (`WAVEncoder.encode_and_save`) |
|---|---|---|
| Raises on write/encode failure | `WAVEncoderError` (lines 78, 80) | **`OSError`** (line 158: `raise OSError(f"WAV encoding failed: {e}")`) |
| Write is atomic? | **No** — plain `open(output_path,'wb')` at line 68 | Yes — `atomic_save_audio()` staged write (#4576), line 150 |
| Bit depths | PCM_16 only (hardcoded, line 63) | PCM_16 / PCM_24 / PCM_32 (line 36-40) |
| Output | in-memory `bytes` | file on disk |

`auralis-web/backend/core/processing_engine.py:57-68` builds the user-facing error taxonomy and, importantly, **inserts `WAVEncoderError` FIRST so it beats the generic `OSError` entry**:
```python
_ERROR_CATEGORIES: list[tuple[type[BaseException], str]] = [
    (FileNotFoundError, "Audio file not found"),
    (PermissionError, "Permission denied accessing audio file"),
    (OSError, "Audio file could not be read"),
    ...
]
try:
    from encoding.wav_encoder import WAVEncoderError
    _ERROR_CATEGORIES.insert(0, (WAVEncoderError, "Audio encoding failed"))
except ImportError:
    pass
```
Consequence: a failure inside `encode_to_wav` surfaces as **"Audio encoding failed"** (correct), while the *identical* failure inside `WAVEncoder.encode_and_save` is re-raised as bare `OSError` and matches the third entry, surfacing as **"Audio file could not be read"** — a *read* message for a *write* failure. Both paths are live and both run in the same request lifecycle: `core/chunked_processor.py:575` uses the `core/encoding` encoder (`process_chunk`), and `core/chunked_processor.py:785-796` uses the `encoding/` one (`get_wav_chunk_path`). `_safe_error_message` is consumed by `processing_engine.py:547`, `routers/files.py:251,268` and `routers/system.py:142,191,263` — so this reaches the user.

**Additionally — 2 of the 4 public functions in `encoding/wav_encoder.py` have ZERO callers repo-wide (production AND test):**
```
read_wav_frame_info  -> auralis-web/backend/encoding/wav_encoder.py:83   0 callers
get_wav_chunk        -> auralis-web/backend/encoding/wav_encoder.py:111  0 callers
```
`read_wav_frame_info`'s docstring (lines 85-92) claims *"Used to make per-chunk streaming responses self-describing (#3872): ... so the frontend can trim overlap by exact sample count."* `grep -rn '3872'` across `auralis-web/` returns **only that docstring** — the feature it documents no longer exists anywhere. This is dead code preserved for a removed feature, plus doc rot asserting a live behaviour that isn't.

- **Affected Files**: production — `auralis-web/backend/encoding/wav_encoder.py`, `auralis-web/backend/encoding/__init__.py`, `auralis-web/backend/core/encoding/wav_encoder.py`, `auralis-web/backend/core/encoding/__init__.py`, `auralis-web/backend/core/chunked_processor.py`, `auralis-web/backend/core/processing_engine.py` (6). Test — `tests/backend/test_absolute_path_log_hygiene.py` (imports `encode_to_wav`), `tests/backend/test_atomic_cache_writes_4576.py` (1-2).
- **Live production caller counts**: `encode_to_wav` = **1** (`core/chunked_processor.py:787`); `WAVEncoder` = **1** (`core/chunked_processor.py:182,575`); `WAVEncoderError` = **2** (`core/chunked_processor.py:785,794` and `core/processing_engine.py:66`); `read_wav_frame_info` = **0**; `get_wav_chunk` = **0**.
- **Migration Path**: (1) delete `read_wav_frame_info` and `get_wav_chunk` (0 callers); (2) make `core/encoding/wav_encoder.py:158` raise `WAVEncoderError` (imported from the sibling module) instead of bare `OSError`, so the taxonomy classifies both paths as "Audio encoding failed" — or move `WAVEncoderError` to a shared module both import; (3) longer term, fold the surviving ~40 lines of `encoding/wav_encoder.py::encode_to_wav` into `core/encoding/WAVEncoder` as an `encode_to_bytes()` method so one module owns WAV encoding, and delete the `encoding/` package.
- **Effort**: Small (<10 sites)
- **Risk**: Today — users see "Audio file could not be read" when a disk write fails during chunk processing, which sends debugging in the wrong direction. Future — any new `except WAVEncoderError` around chunk *processing* (as opposed to chunk *streaming*) will silently not fire. Two identically-named modules also make `from encoding.wav_encoder import ...` vs `from core.encoding import ...` a coin flip for the next contributor.

### D7-3: `auralis/core/config.py` is UNIMPORTABLE dead code — permanently shadowed by the `auralis/core/config/` package that replaced it; 0 live callers, migration never finished with a delete
- **Severity**: MEDIUM
- **Dimension**: Internal (abandoned legacy module / incomplete migration)
- **Location**: `auralis/core/config.py:1-96` (entire file)
- **Status**: NEW
- **Deprecated API**: `auralis.core.config.Config`, `auralis.core.config.LimiterConfig` (the pre-`UnifiedConfig` hand-rolled classes)
- **Deprecated Since**: undeclared — the file carries no deprecation marker at all, which is exactly why it survived
- **Removal Version**: not scheduled
- **Verified Against**: Python **3.14.0** (`/mnt/data/src/matchering/.venv/bin/python`), executed live.

**A regular package always wins over a same-named module in `FileFinder`'s path hooks, so `auralis/core/config.py` can never be imported.** Proven by execution, not inference:
```
$ .venv/bin/python -c "import auralis.core.config as c; print(c.__file__, hasattr(c,'__path__'))"
resolved __file__: /mnt/data/src/matchering/auralis/core/config/__init__.py
is package: True
names: ['AdaptiveConfig', 'GenreProfile', 'LimiterConfig', 'PresetProfile', 'UnifiedConfig', ...]
```
Both `auralis/core/config.py` (a 2726-byte file, mtime Feb 13) and `auralis/core/config/` (a package) sit side by side in the same directory. Every one of the **~100 `from auralis.core.config import ...` sites** (95 of which import `UnifiedConfig`) resolves to the package. There is **no import path in the language** that reaches the `.py` file.

**Live production caller count for the module's contents: 0. Not "few" — structurally zero.**
- `Config` (the old main config class, `config.py:56`) is defined *only* there and referenced nowhere else in the repo.
- `LimiterConfig` (`config.py:18`) is a stale duplicate of `auralis/core/config/settings.py:16`. Every `LimiterConfig` reference in the repo (`unified_config.py:19,56,135`, `config/__init__.py:23,27`) binds the package's `@dataclass` version. The dead copy is a hand-written `__init__` with `assert`s; the live one is a dataclass with `__post_init__` asserts and float-typed defaults (`1.0` vs `1`).

So this is question 4 in the brief answered definitively: **the legacy module is NOT imported by production code — it cannot be — and no migration statement exists anywhere**, because the migration was completed in code and simply never finished with `git rm`.

- **Affected Files**: 1 production file, 96 lines, 0 callers. No test imports it either (impossible).
- **Evidence**: see the executed snippet above; plus `auralis/core/__init__.py:13` `from .config import UnifiedConfig` — a symbol that exists only in the package, confirming the package is the intended target.
- **Migration Path**: `git rm auralis/core/config.py`. Nothing to migrate. Optionally add a repo-lint check for `X.py` co-existing with `X/` under `auralis/`.
- **Effort**: Small (1 file, 0 sites)
- **Risk**: Zero to delete. Real cost of keeping it: it is 96 lines of plausible-looking configuration that grep, IDE "go to definition", and any future reader will surface as live; a contributor editing `LimiterConfig` defaults there would see no effect at runtime and no error.

### D7-4: `BaseRepository._session_scope()` migration stalled at 2 of 14 repositories — 90 hand-rolled session lifecycles remain, and the helper is deliberately too weak to absorb 58 of them
- **Severity**: LOW
- **Dimension**: Internal (stalled migration)
- **Location**: helper at `auralis/library/repositories/base.py:37-53`; 90 hand-rolled sites across 14 files in `auralis/library/repositories/`
- **Status**: NEW (the #4017-era `BaseRepository` extraction landed; the follow-through did not. No open issue in `issues.json` tracks the `_session_scope` rollout specifically.)
- **Deprecated API**: the hand-rolled `session = self.get_session(); try: ... finally: session.close()` idiom
- **Deprecated Since**: not formally deprecated — `base.py:41` only says "Use for read paths"
- **Removal Version**: not scheduled
- **Verified Against**: live source at HEAD; SQLAlchemy **2.0.44**. Counted mechanically (script over `auralis/library/repositories/*.py`).

**CURRENT COUNTS (this is the delta the brief asked for):**

| | count |
|---|---|
| `with self._session_scope() as session:` call sites | **22** |
| `session = self.get_session()` hand-rolled sites | **90** |
| Repositories using `_session_scope()` **at all** | **2 of 14** — only `track_repository.py` (12) and `fingerprint_repository.py` (9) |
| Repositories with **zero** adoption | **12** — album, artist, fingerprint_scheduler, fingerprint_stats, genre, playlist, queue, queue_history, queue_template, settings, similarity_graph, stats |

Prior audit-era memory recorded "~110 call sites still hand-roll"; the true count today is **90**, so ~20 sites were migrated (all inside the two adopting repos) and then the effort stopped. The two adopting files still contain **16 hand-rolled sites of their own** (`track_repository.py` 9, `fingerprint_repository.py` 7), so even they are half-migrated.

**IMPORTANT NUANCE — most of the remainder is NOT mechanically migratable.** Classifying each hand-rolled site by whether its `try` block calls `commit()`/`rollback()`:

| | count |
|---|---|
| Read-only sites (`_session_scope()` is a drop-in today) | **31** |
| Write sites (need `commit`/`rollback`, which `_session_scope()` explicitly does NOT provide — `base.py:46-47`: *"Callers remain responsible for commit()/rollback() semantics on write paths"*) | **58** |

So the helper as designed can only ever absorb ~35% of the remaining sites. **This is the real reason the migration stalled**, and it means "finish the `_session_scope` migration" is the wrong framing — the correct fix is to add a second `_transaction_scope()` context manager (commit on success, rollback on exception, close in `finally`) and migrate the 58 write sites to *that*.

**No session leaks found.** I audited every hand-rolled site for a missing `session.close()`; the two initial flags (`playlist_repository.py:309`, `track_repository.py:184`) both turned out to have `finally: session.close()` beyond an 80-line body (`playlist_repository.py:402-403`, `track_repository.py:278-279`). Correctness is currently fine — this is duplication/consistency debt, not a bug. Hence LOW.

- **Affected Files**: 14 production repository modules; 0 test files affected
- **Migration Path**: (1) add `_transaction_scope()` to `BaseRepository` (commit/rollback/close); (2) migrate the 31 read-only sites to `_session_scope()` — purely mechanical; (3) migrate the 58 write sites to `_transaction_scope()`, auditing each for the specific `except` clauses it currently uses (several return sentinel values like `True` on `IntegrityError`, e.g. `playlist_repository.py:389-394`, which a naive rewrite would break); (4) finish the two half-migrated repos first as the reference pattern.
- **Effort**: Large (89 sites across 14 files)
- **Risk**: Low if done incrementally. Doing it as one sweep risks silently changing rollback semantics on write paths that today swallow exceptions deliberately.

### D7-5: Retired-architecture residue sweep — three of four are CLEAN; the surviving residue is dead MSW mocks + docs for `/api/enhancement/*` endpoints the backend no longer serves
- **Severity**: LOW
- **Dimension**: Internal (dead code for removed features)
- **Location**: `auralis-web/frontend/src/test/mocks/handlers.ts:411-430`; `auralis-web/frontend/src/tests/MSW_QUICK_START.md:272-273`; `auralis-web/frontend/src/tests/integration/error-handling/error-handling.test.tsx:69`
- **Status**: NEW
- **Verified Against**: live source at HEAD; backend route table grepped from `auralis-web/backend/routers/`.

I cross-checked all three rows of the "Retired Architecture" table in `.claude/commands/_audit-common.md:70-74`. **Results — mostly clean, and the table is accurate:**

| Retired thing | Residue found | Verdict |
|---|---|---|
| Categorical mastering branches (`quiet` / `dynamic_loud` / `compressed_loud` classifier) | **NONE.** `auralis/core/mastering_branches/` contains only `base.py`, `continuous.py`, `soft_clip_params.py`. No `dynamic_loud` or `compressed_loud` identifier exists anywhere in the repo. The ~40 `quiet` hits are all ordinary English in comments about quiet *material* (e.g. `content_modifiers.py:106 _apply_quiet_material_rule`) or FFmpeg's `-v quiet` flag (`unified_loader.py:211`, `ffmpeg_loader.py:197`) — **not** branch names. | **CLEAN — no finding** |
| Standalone `fingerprint-server` service | **NONE in source.** `vendor/auralis-dsp/Cargo.toml` declares only `[lib] auralis_dsp` (cdylib+rlib) — no `[[bin]]`, no `tonic`/`prost`/`tokio` dependency, no `src/bin/`, zero `grpc` references in `src/`. The only hits are (a) a historical comment at `auralis/__version__.py:33`, which is correct documentation, and (b) `vendor/auralis-dsp/target/debug/.fingerprint/...bin-grpc-fingerprint-server.json`, a **stale Cargo build artifact** under `target/` (out of audit scope, and cleared by `cargo clean`). | **CLEAN — no finding** |
| `EnhancementContext` (frontend) | 3 stale *comments* in `auralis-web/frontend/src/test/mocks/handlers.ts:431,446,461` labelling handlers as "(EnhancementContext API)". Harmless doc rot — the handlers themselves mock the **live** `/api/player/enhancement/*` routes. | **doc rot only** |

**The one genuine residue is adjacent:** `handlers.ts:411-430` registers MSW handlers for
```
POST http://localhost:8765/api/enhancement/toggle    (handlers.ts:412)
POST http://localhost:8765/api/enhancement/preset    (handlers.ts:422)
```
`grep -rn '"/api/enhancement' auralis-web/backend/` returns **zero routes** — the backend serves only the `/api/player/enhancement/...` family (`routers/enhancement.py:205,269,329,387`). The `/api/enhancement/*` (no `player` segment) endpoints were removed and these mocks were never deleted.

**Live production caller count: 0.** No production frontend file references `/api/enhancement/` without `/player/`; `src/config/api.ts:73-75` and `src/hooks/enhancement/useEnhancementControl.ts:256,330,402` all use the correct `/api/player/enhancement/*` paths. The only remaining consumer is a test — `src/tests/integration/error-handling/error-handling.test.tsx:69` asserts against `/api/enhancement/state`, a **third** path that exists in neither the backend nor the mock set.

Consequence: a test that hits a removed endpoint gets a green MSW response instead of a 404, so the mock layer actively conceals that the contract is gone. `src/tests/MSW_QUICK_START.md:272-273` documents these dead routes as if they were the real API, so new tests are actively steered onto them.

- **Affected Files**: 3 (all test/doc; 0 production)
- **Migration Path**: delete `handlers.ts:411-430`; delete the two lines from `MSW_QUICK_START.md:272-273`; fix `error-handling.test.tsx:69` to target a route that exists; drop the stale "(EnhancementContext API)" comments at `handlers.ts:431,446,461`.
- **Effort**: Small (<10 sites)
- **Risk**: Low. Leaving it keeps the MSW layer able to green-light calls to endpoints that would 404 in the real app — the exact failure mode contract tests are meant to catch.

### D7-6: Nine self-declared "kept for backward compatibility" shims in the ENGINE have ZERO production callers — all are kept alive solely by tests
- **Severity**: LOW
- **Dimension**: Internal (dead compatibility shims)
- **Status**: NEW
- **Verified Against**: live source at HEAD. Caller counts obtained by grepping each symbol across `auralis/` + `auralis-web/` (production) and `tests/` separately, excluding the `def` line itself.

Every row below is a shim the code *itself* labels as compatibility-only. **None has a single production caller.** Per the brief's rule, zero production callers = dead shim.

| # | Symbol | Location | Self-declared as | Prod callers | Test refs |
|---|---|---|---|---|---|
| 1 | `QueueManager = QueueController` (module-level alias) | `auralis/player/enhanced_audio_player.py:38-39` | *"Backward compatibility alias for old test code"* | **0** | **0** |
| 2 | `QueueController.__init__(..., library_manager=None)` | `auralis/player/queue_controller.py:31,38` | *"Deprecated, kept for backward compatibility only"* | see D7-7 | — |
| 3 | `QueueController.clear()` | `auralis/player/queue_controller.py:112` | *"backward compatibility alias"* for `clear_queue()` | **0** | — |
| 4 | `QueueController.set_queue()` | `auralis/player/queue_controller.py:334` | *"(for backward compatibility)"* | **0** | — |
| 5 | `QueueHistoryRepository.undo(queue_repository=None)` | `auralis/library/repositories/queue_history_repository.py:105,116` | *"queue_repository: Unused; kept for backwards-compatible signature"* | **0** — production calls `repo.undo` with no args (`auralis-web/backend/routers/player.py:579`) | 7 (`tests/integration/test_queue_history.py:168,193,219,224,233,258,590`) |
| 6 | `create_psychoacoustic_eq()` | `auralis/dsp/eq/__init__.py:18-27` (also in `__all__`) | *"Factory function for backward compatibility"* | **0** | 4 |
| 7 | `_a_weighting_curve`, `_c_weighting_curve`, `_map_to_bands`, `_calculate_rolloff` (4 methods) | `auralis/analysis/base_spectrum_analyzer.py:228-280` | each *"(backward compatibility wrapper)"* — every one is a one-line forward to `SpectrumOperations.*` | **0** each | 1 each |
| 8 | `LibraryScanner.scan_folder()` | `auralis/library/scanner/scanner.py:326-355+` | *"Backward compatibility method"* / *"compatible with the old test expectations"* | **0** | 26 |
| 9 | `LibraryScanner.scan_single_directory()` | `auralis/library/scanner/scanner.py:322` | one-line forward to `scan_directories([directory])` | **0** | 15 |

Notable specifics:

**Row 1 is a name collision, not just dead weight.** `auralis/player/enhanced_audio_player.py:39` binds the name `QueueManager` to `QueueController`, while `auralis/player/components/queue_manager.py:27` defines a genuinely different `QueueManager` class (the locked queue data structure), and `auralis-web/backend/services/queue_protocols.py:22` defines a third `QueueManager` (a `Protocol`). `auralis/player/queue_controller.py:15` imports the *real* one (`from .components import QueueManager`) into the very module the alias points at. So `from auralis.player.enhanced_audio_player import QueueManager` and `from auralis.player.components import QueueManager` return **different classes with different APIs**. Nothing — production or test — imports the alias; it is pure hazard with no user.

**Row 8's docstring is self-refuting**: *"This is compatible with the old test expectations."* A production method whose stated contract is "matches what the old tests expect" and which no production code calls is, by definition, test scaffolding living in the shipped package (26 test references keep it green).

- **Affected Files**: 6 production modules; ~55 test references
- **Migration Path**: for rows 1, 3, 4 — delete outright (0 refs anywhere for row 1). For rows 5-9 — inline the wrapper at each test call site (`SpectrumOperations.compute_a_weighting(...)`, `PsychoacousticEQ(EQSettings(...))`, `scan_directories([dir])`, `undo()`), then delete. Row 8 (`scan_folder`, 26 refs) is the only one with real churn; it may be worth keeping as a documented convenience rather than a "compat" shim — but then relabel it, because the current comment tells every reader it is removable.
- **Effort**: Small for rows 1-7 (<10 sites each); Medium overall because of rows 8-9 (~41 test refs)
- **Risk**: None to production (zero callers by construction). The cost of keeping them is that `grep` for "backward compatibility" surfaces 9 false leads on every future audit, and row 1 is an active foot-gun for anyone importing `QueueManager` from the wrong module.

### D7-7: The LIVE production startup path passes a deprecated `library_manager=` argument that is threaded through two constructors and then silently discarded
- **Severity**: MEDIUM
- **Dimension**: Internal (deprecated API with a live production caller)
- **Location**: `auralis-web/backend/config/startup.py:450-454` → `auralis/player/enhanced_audio_player.py:76,84,99` → `auralis/player/queue_controller.py:31,38-41`
- **Status**: NEW
- **Deprecated API**: the `library_manager` keyword parameter of `AudioPlayer.__init__` and `QueueController.__init__`
- **Deprecated Since**: "Phase 6C" per `auralis/player/queue_controller.py:25` / `enhanced_audio_player.py:69` (*"Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)"*)
- **Removal Version**: not scheduled
- **Verified Against**: live source at HEAD; the full call chain read end-to-end.

**This is the one deprecated internal API in the engine that still has a live production caller — 1 — and it is on the boot path.**

```python
# auralis-web/backend/config/startup.py:450
globals_dict['audio_player'] = AudioPlayer(
    player_config,
    library_manager=globals_dict['library_manager'],     # <-- deprecated arg, LIVE
    get_repository_factory=lambda: globals_dict.get('repository_factory')
)
```
`AudioPlayer.__init__` documents the parameter as *"library_manager: Deprecated, kept for backward compatibility only"* (`enhanced_audio_player.py:84`), never stores it, and forwards it:
```python
# auralis/player/enhanced_audio_player.py:99
self.queue = QueueController(get_repository_factory, library_manager)
```
`QueueController.__init__` documents it identically (`queue_controller.py:38`) and its body is:
```python
self.queue: Any = QueueManager()
self.get_repository_factory = get_repository_factory
```
— **the parameter is never read, never stored, and never used.** The value travels through two frames and is dropped.

**Two compounding problems:**
1. **The name is now a lie.** Per #4619, `globals_dict['library_manager']` is a `LibraryDatabase`, not a `LibraryManager` (`startup.py:307`). So the argument is a deprecated parameter, named after a deprecated class, carrying an instance of the *replacement* class, into a function that ignores it.
2. **It makes the deprecation look incomplete when it isn't.** Anyone auditing "does anything still depend on LibraryManager?" finds this live call and reasonably concludes the migration is unfinished. It is not — the argument is inert. (This is likely part of why the `_audit-common.md` claim needed re-verification at all; see D7-1.)

- **Affected Files**: 3 production files. Production callers passing the argument: **1** (`startup.py:452`). Production functions accepting it: **2**. Test call sites passing it: **0** — every test constructs `QueueController(get_repository_factory_callable)` positionally without it (`tests/conftest.py:322`, `tests/backend/conftest.py:352`, `tests/auralis/player/conftest.py:35`, `tests/auralis/player/test_enhanced_player_detailed.py:50`, `tests/auralis/player/test_queue_controller.py:35`).
- **Migration Path**: delete the `library_manager` parameter from both `__init__` signatures, delete the pass-through at `enhanced_audio_player.py:99`, and drop the keyword at `startup.py:452`. Three edits; nothing reads the value, so there is no behaviour to preserve. Also rename the `globals_dict['library_manager']` key to `library_database` in the same pass (12 backend files reference it) or the misleading name outlives the parameter.
- **Effort**: Small (<10 sites for the parameter; the optional key rename is ~66 references across 12 files)
- **Risk**: Zero behavioural risk — the value is provably unused. Leaving it guarantees the next audit re-litigates whether `LibraryManager` is still load-bearing.

### D7-8: WebSocket `library_updated` payload still ships a `reason` field "kept for backward compat" — no client has ever read it, and the TS contract does not declare it
- **Severity**: LOW
- **Dimension**: Internal (deprecated wire field kept for a client that cannot exist)
- **Location**: `auralis-web/backend/routers/library_scan.py:184-189`; `auralis-web/backend/services/library_auto_scanner.py:365-372`; contract at `auralis-web/frontend/src/types/ws/library.ts:29-37`
- **Status**: NEW
- **Deprecated API**: the `data.reason` field of the `library_updated` WebSocket message
- **Deprecated Since**: #3544 (the commit that introduced `action` as the replacement)
- **Removal Version**: not scheduled
- **Verified Against**: live source at HEAD; both backend emitters and the full frontend consumer set grepped.

```python
# auralis-web/backend/routers/library_scan.py:183-189
"type": "library_updated",
# `reason` kept for backward compat; new consumers use `action` (#3544).
"data": {
    "action": "scan",
    "reason": "scan",      # <-- duplicate of `action`, same literal value
    "track_count": result.files_added,
},
```
The identical block is duplicated at `services/library_auto_scanner.py:365-372` (auto-scan path), whose own comment at line 358-360 says the payload *"matches the manual-scan emit (#3544) — action + counts that the frontend LibraryUpdatedMessage type actually declares"* — while still emitting the undeclared `reason`.

**Consumer count: 0.** The TypeScript contract omits it entirely:
```ts
// auralis-web/frontend/src/types/ws/library.ts:29-37
export interface LibraryUpdatedMessage extends WebSocketMessage {
  type: 'library_updated';
  data: {
    action: 'scan' | 'import' | 'update';
    track_count?: number;
    album_count?: number;
    artist_count?: number;
  };            // <-- no `reason`
}
```
The only frontend subscriber is `auralis-web/frontend/src/hooks/library/useLibraryWithStats.ts:72-78`, which reacts to the message type and never inspects `data.reason`. `grep` for `.reason` across `src/` returns three unrelated hits (queue recommendations, an `AbortSignal.reason`). Type guard `types/ws/guards.ts:98` checks only `msg.type`.

**The "backward compat" rationale is structurally void here.** Auralis ships as a single Electron app: the frontend, the FastAPI backend and the Rust DSP are bundled and versioned together on localhost. There is no older client that could still be reading `reason` — backend and frontend are always the same build. A wire-compatibility shim only makes sense across independently-deployed versions, which this architecture does not have.

- **Affected Files**: 2 production backend files; 0 consumers
- **Migration Path**: delete the `"reason": "scan",` line from both emitters and the accompanying comment. No contract change is needed — the TS interface already reflects the intended shape.
- **Effort**: Small (2 sites)
- **Risk**: Zero. Leaving it means the message a `sync-contracts` run compares against the TS type will keep showing an undeclared extra field forever.

### D7-9: `auralis/player/realtime_processor.py` is a self-declared re-export shim whose own docstring says not to use it — but 2 live production modules import through it
- **Severity**: LOW
- **Dimension**: Internal (incomplete migration, live production callers)
- **Location**: `auralis/player/realtime_processor.py:1-27` (entire file is the shim)
- **Status**: NEW
- **Deprecated API**: importing `RealtimeProcessor` (and 4 siblings) from `auralis.player.realtime_processor` instead of `auralis.player.realtime`
- **Deprecated Since**: undeclared — the file says only *"For new code, prefer importing from auralis.player.realtime directly"* (line 6)
- **Removal Version**: not scheduled
- **Verified Against**: live source at HEAD.

The whole module is 27 lines that re-export `AdaptiveGainSmoother`, `AutoMasterProcessor`, `PerformanceMonitor`, `RealtimeLevelMatcher`, `RealtimeProcessor` from `.realtime`.

**Live production callers of the shim path: 2.**
```
auralis/player/enhanced_audio_player.py:36:from .realtime_processor import RealtimeProcessor
auralis/player/fingerprint_loader_mixin.py:17:from .realtime_processor import RealtimeProcessor
```
Test callers: 3 (`tests/auralis/core/test_core.py:320`, `tests/auralis/player/conftest.py:76`, `tests/auralis/player/test_realtime_processor.py:23`).

This is an *actually* incomplete migration (unlike D7-6's zero-caller shims): the module tells new code to bypass it while the two most central player modules still route through it, so the shim can never age out on its own.

Same pattern, lower stakes, elsewhere — reported here rather than as separate findings:
- `auralis/library/migrations/__init__.py:12-22` — re-exports `MigrationManager`/`backup_database`/`check_and_migrate_database` from the parent `migration_manager.py` *"for backward compatibility"*. **0 production importers**; 2 test importers (`tests/validation/validate_version_system.py:38,97`). The directory must exist regardless (it holds the `.sql` migration files), so only the re-export block is removable.
- `auralis/dsp/advanced_dynamics.py:32` and `auralis/io/unified_loader.py:28` — both labelled "re-export for backward compatibility"; both still have production importers, so they are the same shape as the primary finding.

- **Affected Files**: 1 shim module + 2 production importers + 3 test importers
- **Migration Path**: rewrite the 5 import statements to `from .realtime import RealtimeProcessor` (2 production, 3 test), then delete `realtime_processor.py`. Purely mechanical.
- **Effort**: Small (5 sites)
- **Risk**: None. The shim re-exports the same objects; the import path is the only difference.


---

## Dimensions not covered / coverage caveats (consolidated)

This audit's merge step crashed twice (API 500) partway through incorporating Dimension 6 (Rust/PyO3) and Dimension 7 (Internal deprecations). Both dimensions' underlying analysis is complete and is included above in full; only the ORIGINAL merge attempt was interrupted, not the analysis. D6-3 and D6-4 had already been merged into the main findings list above as DEP-24/DEP-25 before the crash; the remaining D6 and all D7 findings are appended under their native `D6-n`/`D7-n` identifiers rather than being renumbered into the `DEP-n` sequence, to avoid renumbering collisions during this recovery.

**Dimension 6 (Rust / PyO3 / Cargo / maturin) — coverage statement, verbatim from the dimension agent:**

- Examined in full: `vendor/auralis-dsp/Cargo.toml`, `.cargo/config.toml`, `UPGRADE_PLAN.md`; all 19 `.rs` source files (swept by targeted grep for every pyo3-0.23/ndarray-0.16 deprecation; `py_bindings.rs` and `lib.rs` read line-by-line); `.github/workflows/rust-audit.yml` and the Rust/maturin steps of `build-release.yml`; `build.js:60-200`; `tests/test_phase5_rust_benchmark.py:275-310`; root `pyproject.toml` build-system section.
- Upstream crate sources read as primary evidence (not release notes, not memory): `pyo3-build-config-0.23.5` and `pyo3-ffi-0.23.5` internals, plus the crate's own compiled build artifacts (8 `target/*/build/pyo3-ffi-*/output` files) and live CI run history for `rust-audit.yml`.
- **NOT reached / deliberately skipped**: `cargo check` was not run (would risk a long rebuild inside the time budget and could mutate a build cache other concurrent audit agents might be reading; source-level evidence answered the same questions). Consequence: any deprecation warning that only `rustc` itself would emit (e.g. a `#[deprecated]` attribute on a transitively-used `rustfft`/`realfft`/`rayon`/`num-complex` API) is **unverified** by this report. `cargo update`/`add`/`fix`/`maturin develop` were not run (forbidden). `criterion` dev-dependency was not audited (confirmed dead weight — no `benches/` dir, no in-crate references — but that is tech-debt, not a deprecation, so not filed here). In-crate `#[cfg(test)]` unit tests were grep-swept but not read individually. Only `rust-audit.yml`'s CI history was pulled; other workflows' histories were not inspected, so D6-8's blast-radius claim is from workflow *definitions*, not observed failures.

**Dimension 7 (Internal deprecations / retired-architecture residue) — coverage note:**

This dimension's file did not include a separate formal coverage statement; each finding instead carries its own "Verified Against" line citing the exact files/line ranges read. Areas the dimension's 9 findings collectively establish as examined: `LibraryManager` and its cache layer, both `wav_encoder.py` modules, `auralis/core/config.py` vs the `config/` package, `BaseRepository._session_scope()` and all repositories, retired-architecture (`/api/enhancement/*`) residue across frontend and backend, engine "kept for backward compatibility" shims, the production startup path's constructor arguments, the `library_updated` WS payload contract, and `auralis/player/realtime_processor.py` plus its two sibling shim modules.

**Dimension 7B (gap-coverage follow-up) — this gap has now been partially closed.** A dedicated pass searched the same deprecation-debt class (backward-compat shims, unwired modules, dead-parameter threading, retired-architecture residue) across everywhere D7 did NOT name, using a repo-wide marker grep (`backward.?compat`, `deprecated`, `legacy`, `kept for`, `TODO.*remove`, etc.) followed by manual verification of every hit. This produced 5 new findings (D7B-1 through D7B-5, above) and an explicit "checked and found clean" list of ~20 other candidate hits that were investigated and ruled out with reasoning.

Even after D7B, the following remain **genuinely unexamined** (zero marker-grep hits is not the same as verified clean — this method only finds *self-declared* deprecation debt in code/comments, not silently dead unmarked code):
- `auralis/optimization/`, `auralis/services/`, `auralis/learning/`, `auralis/cli/` — grepped for markers only (zero hits), never independently read for undeclared dead code.
- `auralis-web/frontend/src/components/` (the large majority of files) and `auralis-web/frontend/src/store/` — only grep hits were reviewed, no broader pass.
- `desktop/src/` and `vendor/auralis-dsp/src/*.rs` — grepped only (zero hits); Rust-specific `#[deprecated]` review is Dimension 6's territory and was not re-derived here.
- Two borderline cases were identified but deliberately NOT filed, pending a decision on whether to promote them: `useKeyboardShortcuts.ts`'s `getShortcutString` (single function, test-only caller, trivial effort if promoted) and `TrackApiResponse.artist?`/`.genre?` singular fallback fields (a theoretical live path exists via the backend's `serializers.py` getattr-fallback branch; not proven to fire in production).

A genuinely exhaustive dead-code sweep (as opposed to marker-based deprecation-debt search) would require a systematic call-graph pass — e.g. the codebase-memory graph's "unused functions" query — over the areas listed above.

**General note on this recovery**: the assembly above (D6/D7 sections) was performed mechanically by extracting each dimension file's content verbatim rather than by an agent re-reading and re-synthesizing, because repeated API 500/529 errors made a fresh agent pass unreliable. No content was reworded or re-derived; formatting of section headers was added only for navigation.

---

## Findings — Dimension 7B (Internal-deprecation gap coverage)

> D7 (above) never produced a formal coverage statement, leaving unclear which internal-deprecation
> areas beyond its 9 named findings had been checked. Per an explicit ask to close that gap, a follow-up
> pass searched the areas D7 did NOT name (everything except LibraryManager, wav_encoder, core/config.py,
> BaseRepository, /api/enhancement/* residue, the named engine shims, startup constructor args, the
> library_updated WS payload, and realtime_processor.py). 5 new findings resulted, all dedup-verified
> against the 40 findings above and against open GitHub issues. Findings retain their native `D7B-n` IDs.

### D7B-1: `auralis/analysis/fingerprint/parameter_mapper.py` — a whole 442-line, 4-class fingerprint→mastering-parameter subsystem has ZERO production callers; explicitly unwired per an adjacent code comment
- **Severity**: MEDIUM
- **Dimension**: Internal (retired-architecture residue / incomplete migration)
- **Location**: `auralis/analysis/fingerprint/parameter_mapper.py:1-442` (whole file: `EQParameterMapper`, `DynamicsParameterMapper`, `LevelParameterMapper`, `HarmonicParameterMapper`, `ParameterMapper`); the disconnection is documented at `auralis-web/backend/core/processing_engine.py:304-309`
- **Status**: NEW
- **Verified Against**: live source at HEAD (`9e03236c`). `grep -rn "ParameterMapper\b" auralis/ auralis-web/backend` (excluding the class `def` lines themselves and the one comment) returns **zero** production call sites. `grep -rn "generate_mastering_parameters"` likewise returns only the class definition and the one comment.

**Evidence.** The module's own docstring states its purpose plainly:
```python
# auralis/analysis/fingerprint/parameter_mapper.py:1-11
"""
Fingerprint Parameter Mapper
Converts 25D audio fingerprints into mastering parameters (EQ, dynamics, levels).
Maps fingerprint dimensions to processor configuration:
- Frequency distribution (7D) -> 31-band EQ gains
- Dynamics (3D) -> Compressor threshold, ratio, attack, release
...
"""
```
The one place in production code that ever called it says, in a comment, that it does not anymore:
```python
# auralis-web/backend/core/processing_engine.py:304-309
fingerprint_settings = job.settings.get("fingerprint")
if fingerprint_settings and fingerprint_settings.get("enabled"):
    # parameter_mapper.generate_mastering_parameters used to be called
    # here and its output written to dead config attrs. Kept for
    # reference in case a future wire-up needs the intermediate dict.
    unsupported.append("fingerprint (parameter-mapper output is currently unread by engine)")
```
So `processing_engine.py` explicitly appends `"fingerprint"` to its `unsupported` UI-settings list — i.e. this is not merely dead code, it is a *documented, currently-active limitation*: the fingerprint-driven mastering-parameter path the frontend UI exposes cannot reach the engine at all, because the module that would produce those parameters is not called from anywhere.

**Live callers found: 0 production, 2 non-production.** `scripts/generate_ab_test_audio.py:32,428` (a standalone dev script for generating A/B comparison audio) and the test suite (`tests/test_parameter_mapper.py`, `tests/test_phase25_1_eq_saturation.py`, `tests/test_phase25_2_listening_tests.py`, `tests/test_phase25_parameter_validation.py`, `tests/test_chroma_rust_validation.py` — 5 files, well over 60 references) are the only consumers. This matches the same shape D7-1 found for `LibraryManager`: a substantial module kept alive solely by tests plus one dev script, with a comment in production code confirming it was deliberately unwired.

**This predates, and is a casualty of, the continuous-parameter-space rewrite** (`_audit-common.md`'s "Retired Architecture" table: categorical mastering branches were replaced by `auralis/core/processing/continuous_space.py`'s `ProcessingCoordinates`). `ParameterMapper` was the older per-dimension mapping approach; `continuous_space.py` now derives mastering parameters continuously from the 3D coordinate space instead of the 25D→31-band mapping this module implements. Nothing deletes the older module, so it sits in the shipped package looking like a live, load-bearing piece of the fingerprint pipeline.

- **Affected Files**: 1 production file (442 lines, 0 callers) + 1 dev script + 5 test files (~65+ references)
- **Migration Path**: (1) confirm with the frontend UI settings surface (`fingerprint` toggle in `ProcessingSettings`) whether fingerprint-driven parameter generation is still an intended feature; if yes, wire `ParameterMapper.generate_mastering_parameters()` into `processing_engine.py` in place of the `unsupported.append(...)` branch; if no (superseded by continuous-space), delete the module, `scripts/generate_ab_test_audio.py`'s usage, and the 5 test files, and remove the `fingerprint` toggle from the settings schema so the UI stops offering a control with no effect. (2) Either way, resolve the ambiguity — right now the UI can turn on a "fingerprint" processing option that is silently a no-op, which is a user-facing broken-promise bug distinct from the code-cleanliness question.
- **Effort**: Medium (module deletion is small; the UI/schema follow-through and confirming test coverage overlap elsewhere is the larger piece)
- **Risk**: Low to delete (no production callers). The cost of keeping it as-is: a UI toggle that silently does nothing (separate from this report's scope, but worth flagging to whoever owns product behavior), plus 442 lines that read as live fingerprint→engine wiring to any future contributor or auditor.

---

### D7B-2: `advanced_dynamics.py`'s genre-adaptive `detection_mode` selection is threaded into `Compressor.process()`, which silently discards it — adaptive detection mode is a no-op for every track
- **Severity**: MEDIUM
- **Dimension**: Internal (deprecated/inert parameter with live production callers, presented as active behavior)
- **Location**: producer — `auralis/dsp/advanced_dynamics.py:133-134` (`_get_detection_mode`, `auralis/dsp/advanced_dynamics.py:172-184`); consumer — `auralis/dsp/dynamics/compressor.py:86,96` (`Compressor.process(audio, detection_mode="rms")`); second live caller — `auralis/player/realtime/auto_master.py:162`
- **Status**: NEW
- **Verified Against**: live source at HEAD; full body of `Compressor.process()` read (lines 86-140+) — confirmed no branch anywhere on `detection_mode`.

**This is the same *"argument travels through frames and is silently dropped"* shape D7-7 found for `library_manager=`, but on a different call chain, and arguably worse: here the *producer* side gives no indication the value is inert.**

`AdvancedDynamicsProcessor.process()` computes a detection strategy from content analysis before every compression pass:
```python
# auralis/dsp/advanced_dynamics.py:133-134
detection_mode = self._get_detection_mode(content_info)
processed_audio, comp_info = self.compressor.process(processed_audio, detection_mode)
```
```python
# auralis/dsp/advanced_dynamics.py:172-184
def _get_detection_mode(self, content_info: dict[str, Any] | None) -> str:
    """Determine optimal detection mode based on content"""
    if not content_info:
        return "rms"  # Default
    genre = content_info.get('genre_info', {}).get('primary', 'pop')
    if genre in ['classical', 'jazz', 'acoustic']:
        return "rms"       # Better for musical content
    elif genre in ['electronic', 'hip_hop', 'metal']:
        return "peak"      # Better for transient-heavy content
    else:
        return "hybrid"    # Balanced approach
```
This reads as genuine, working genre-adaptive DSP — different detection strategies chosen per genre for better compression behavior. But `Compressor.process()`'s own docstring admits the parameter does nothing:
```python
# auralis/dsp/dynamics/compressor.py:86,96
def process(self, audio: np.ndarray, detection_mode: str = "rms") -> tuple[np.ndarray, dict[str, float]]:
    """
    ...
    Args:
        detection_mode: Unused, kept for API compatibility
    """
```
The method body (read in full) computes gain reduction purely from `np.abs`/`np.max` sample levels — there is no `if detection_mode == "peak"` / `"rms"` / `"hybrid"` branch anywhere in `compressor.py`. A second live production caller, `auralis/player/realtime/auto_master.py:162`, hardcodes `detection_mode="hybrid"` — also inert.

**Consequence**: the genre-based detection-mode selection is fully computed (CPU cost, however small) and then thrown away on every single compression pass, offline and realtime. Anyone reading `advanced_dynamics.py` in isolation (which is where `_get_detection_mode` lives, with no comment there admitting the value goes nowhere) would reasonably conclude the compressor's detection strategy adapts to genre. It does not, and cannot, given the current `Compressor.process()` implementation.

- **Affected Files**: 3 production files (`advanced_dynamics.py`, `compressor.py`, `realtime/auto_master.py`); 0 test files depend on the value actually changing behavior (tests instantiate `Compressor.process()` with the default or an explicit mode and never assert differing output between modes — consistent with the parameter being fully inert today)
- **Migration Path**: Either (a) implement per-mode gain-reduction logic in `Compressor.process()` (peak-only vs RMS vs hybrid detection, per the original design intent implied by the parameter name and `_get_detection_mode`'s branching), or (b) if RMS-style detection via the existing per-sample envelope follower was intentionally judged sufficient for all content types, delete `_get_detection_mode()`, stop passing `detection_mode` from both call sites, and remove the parameter from `Compressor.process()` — a comment at the `_get_detection_mode` call site should say why, so the next reader doesn't rediscover this.
- **Effort**: Small to remove (3 call/definition sites); Medium to actually implement the described behavior
- **Risk**: No behavioral regression either way (the value has never been read). The risk of leaving it as-is is purely to correctness expectations: any future engine change that assumes `detection_mode` works (e.g. a bug report "peak detection isn't kicking in for electronic tracks") will be very hard to diagnose without knowing this parameter has always been a no-op.

### D7B-3: `auralis/dsp/dynamics/vectorized_envelope.py` — an entire alternate `FastEnvelopeFollower` class, both module factory functions, and the single-sample `.process()` compatibility method have ZERO callers anywhere (production or test)
- **Severity**: LOW
- **Dimension**: Internal (dead code / unused alternate implementation)
- **Location**: `auralis/dsp/dynamics/vectorized_envelope.py:45-51` (`VectorizedEnvelopeFollower.process()`), `:174-218` (`FastEnvelopeFollower`, whole class), `:222-240` (`create_vectorized_envelope_follower()`), `:243-260` (`create_fast_envelope_follower()`)
- **Status**: NEW
- **Verified Against**: live source at HEAD. `Compressor` (`compressor.py:44`) and `Limiter`/`AutoMasterProcessor` (`limiter.py:51`) both construct `EnvelopeFollower` aliased from `VectorizedEnvelopeFollower`, but call only `.process_buffer(...)` (`compressor.py:125`, `limiter.py:102`) and `.reset()` — never `.process()`. `process_buffer()`'s own body (lines 120-137) only ever calls `self.process_buffer_numba(...)` or `self.process_buffer_vectorized(...)`, so those two ARE live (via internal dispatch); everything else in the file is not.

| Symbol | Callers (prod) | Callers (test) |
|---|---|---|
| `VectorizedEnvelopeFollower.process()` (single-sample, docstring: *"for backward compatibility"*) | 0 | 0 |
| `FastEnvelopeFollower` (whole class, `process_buffer_fast()`) | 0 | 0 |
| `create_vectorized_envelope_follower()` | 0 | 0 |
| `create_fast_envelope_follower()` | 0 | 0 |

`FastEnvelopeFollower`'s docstring (`:175-179`) frames it as a legitimate alternative ("segment-based processing... more vectorization opportunities"), not as deprecated — but it has never been wired up anywhere: no production module imports it, and neither factory function has a single caller repo-wide (`grep -rn "create_vectorized_envelope_follower\|create_fast_envelope_follower"` returns only the two `def` lines each).

- **Affected Files**: 1 production file, ~75 of its 260 lines are unreachable
- **Migration Path**: delete `process()` (line 45-51), the entire `FastEnvelopeFollower` class (174-218), and both factory functions (222-260); keep `VectorizedEnvelopeFollower.process_buffer/_numba/_vectorized/reset`, which are the only methods `Compressor`/`Limiter` use.
- **Effort**: Small (single file, no external references to update)
- **Risk**: Zero. Nothing constructs `FastEnvelopeFollower` or calls the dead methods.

### D7B-4: `ChunkOperations.calculate_total_chunks()` is a dead sibling of the actually-used `StreamlinedCacheManager._calculate_total_chunks()` — same delegation target, zero callers, and its own `chunk_interval` parameter is a no-op by construction
- **Severity**: LOW
- **Dimension**: Internal (dead code / duplicate implementation)
- **Location**: `auralis-web/backend/core/chunk_operations.py:346-368`
- **Status**: NEW
- **Verified Against**: live source at HEAD. `grep -rn "calculate_total_chunks"` across `auralis-web/` and `tests/` (excluding the `def` line) returns only unrelated hits for a **different** method, `StreamlinedCacheManager._calculate_total_chunks` (`auralis-web/backend/cache/manager.py:181-191`), which independently delegates to the same `content_chunk_count()` SoT and is the one actually called (`cache/manager.py:253`) and tested (`tests/backend/test_cache_total_chunks_delegation_4620.py`, `tests/backend/test_streamlined_cache.py:182-192`).

```python
# auralis-web/backend/core/chunk_operations.py:346-368
@staticmethod
def calculate_total_chunks(
    total_duration: float,
    chunk_interval: int = 10
) -> int:
    """
    ...
    Args:
        total_duration: Total audio duration in seconds
        chunk_interval: Interval between chunk starts (kept for back-compat;
            the canonical overlap model lives in chunk_boundaries)
    ...
    """
    from core.chunk_boundaries import content_chunk_count
    return content_chunk_count(total_duration)
```
The `chunk_interval` parameter is accepted but never referenced in the body — it is inert by construction, not just unused by callers (there are no callers at all). This is a narrower, single-method version of the same pattern D7-9 found for whole shim *modules*: two independent implementations converged on delegating to the same SoT (`content_chunk_count`) after #4620/#4124, and only one of the two ever got wired up to a caller.

- **Affected Files**: 1 production file, 1 dead static method (23 lines incl. docstring)
- **Migration Path**: delete `ChunkOperations.calculate_total_chunks()` and `get_chunk_time_range()` if the latter is also unreferenced (not verified in this pass — see coverage note below); no caller migration needed since there are no callers.
- **Effort**: Small (<5 lines net change)
- **Risk**: Zero — dead code by construction.

### D7B-5: `auralis-web/frontend/src/theme/themeConfig.ts` builds and exports a full MUI dark theme (`auralisTheme`, both named and default) that nothing imports
- **Severity**: LOW
- **Dimension**: Internal (dead code — eagerly-constructed unused export)
- **Location**: `auralis-web/frontend/src/theme/themeConfig.ts:508-515`
- **Status**: NEW
- **Verified Against**: live source at HEAD. `grep -rn "themeConfig"` across `auralis-web/frontend/src` shows exactly two importers of the module: `ThemeContext.tsx:4` (imports `createAuralisTheme`, the factory — not `auralisTheme`) and a test importing `glassEffects`/`darkColors`/`gradients`. Neither the named export `auralisTheme` nor the file's `export default` is imported anywhere.

```ts
// auralis-web/frontend/src/theme/themeConfig.ts:508-515
// Export default dark theme for backward compatibility
export const auralisTheme = createAuralisTheme('dark');
...
export default auralisTheme;
```
The comment's own framing ("for backward compatibility") is the tell: `ThemeContext.tsx` — the only consumer that matters, since it is what actually builds the live MUI theme via `ThemeProvider` — calls `createAuralisTheme(mode)` directly so it can react to light/dark mode changes; a static pre-built dark-only instance is structurally useless to it. `createAuralisTheme()` builds a full MUI theme object (palette, typography, ~15 component style overrides per the surrounding file), so this is a non-trivial object constructed at module-import time purely to sit unused.

- **Affected Files**: 1 production file
- **Migration Path**: delete lines 508-509 and 515 (the `auralisTheme` const, its comment, and the default export). Confirm no re-export elsewhere depends on the default export before deleting (checked: none found).
- **Effort**: Small (3 lines)
- **Risk**: Zero — unused by construction, verified no importers.

---

