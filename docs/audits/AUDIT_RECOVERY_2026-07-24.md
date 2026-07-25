# Working-State Recovery Audit — 2026-07-24

**Scope**: End-to-end Auralis recovery: root launchers, Electron ownership, FastAPI startup/readiness, fresh-database behavior, library/fingerprint persistence, mono and stereo enhancement paths, React build/runtime contracts, WebSocket lifecycle, test infrastructure, and the vendored Rust DSP boundary.

**Goal**: Get the application **working, not finished**. “Working” is defined below as a truthful, repeatable launch followed by a small set of real library and playback flows. It does not require clearing all lint, type, test, documentation, or architectural debt first.

**Method**: Indexed the repository into the codebase knowledge graph (37,222 nodes / 127,943 edges), traced startup and playback call paths, reproduced launch/build/test failures, booted a real isolated backend, and deduplicated against the 200 open GitHub issues returned on 2026-07-24, the eight 2026-07-12 audit reports in `docs/audits/`, and local issue snapshots (none present). Findings below are included only where the current tree did not disprove them.

**Revision audited**: `master` at `74f6dfc1`.

---

## Executive Verdict

The app is recoverable without a rewrite. The engine imports, dependencies resolve, the FastAPI backend can reach real readiness in about two seconds, and the frontend produces a production bundle. The immediate problem is that **the supported way to start and verify the product is broken and contradictory**:

- `npm run dev` exits before starting anything because `dev.js` resolves every component one directory above the repository.
- If those paths are corrected alone, the root supervisor and Electron both try to own the backend; Electron then force-kills every PID using port 8765, including the backend the root supervisor just launched.
- The alternative Python launcher ignores `--port`, sleeps for three seconds, and declares success without checking the child or HTTP readiness.
- Electron treats connection errors and health timeouts as a passed health check.
- The only full-stack smoke script is not collected by pytest and polls the obsolete port 8000.

Behind that launch failure are three live product defects that belong in the first recovery slice:

1. Fresh databases cannot insert their first fingerprint because raw SQL omits the `is_reference` `NOT NULL` column, whose model default is Python-side only. The exception is swallowed, so fingerprint persistence silently fails on new installs.
2. Adaptive processing crashes on `(samples, 1)` mono audio because `LoudnessMeter` treats every 2-D array as stereo and indexes channel 1.
3. Open issue **#4426** remains present: rapid track clicks can let the older request win and play the wrong track.

The broad red test surface is real but misleading. The frontend build passes; 102 of the 208 frontend failures are concentrated in five old suites whose providers, mocks, and virtualization assumptions no longer match production. The Rust adapter used by Python passes its eight boundary tests, while the Rust crate’s own suite has ten failures that mix real public-API defects with invalid test expectations. These are reasons to repair the gates, not evidence of 218 independent product bugs.

### Severity Summary

| Severity | Count | Findings |
|---|---:|---|
| CRITICAL | 0 | — |
| HIGH | 4 | REC-01, REC-02, REC-03, REC-04 |
| MEDIUM | 3 | REC-05, REC-06, REC-07 |
| LOW | 1 | REC-08 |

### Status Summary

| Status | Count | Findings |
|---|---:|---|
| NEW | 7 | REC-01, REC-02, REC-03, REC-05, REC-06, REC-07, REC-08 |
| Existing open issue | 1 | REC-04 → #4426 |

---

## What Already Works

These results narrow the recovery instead of merely cataloguing failures:

- Python 3.13.9 imports both the core package and backend; `uv pip check` reports all 95 installed packages compatible.
- A real Uvicorn process, run against an isolated temporary home/database, became ready in about two seconds:
  - `GET /api/health` → 200, `healthy`, Auralis available
  - `GET /api/version` → 200, version `1.5.0`
  - `GET /api/library/stats` → 200 with a valid empty-library payload
  - `GET /` → 200
- Frontend `pnpm run build` succeeds (1,444 modules transformed).
- The production Python test collection succeeds with **5,466 tests**.
- 81 targeted tests covering the July high-risk fixes completed with **77 passed / 4 skipped**:
  - level transition smoothing
  - shared processor flag atomicity
  - player lock ordering
  - offline mono mastering
  - cancellable FFmpeg/job processing
  - served artwork directory
  - backend pagination invariants
- Frontend heartbeat, pagination, and single-invocation play tests completed with **43/43 passed**.
- The Python↔Rust fingerprint adapter completed with **8/8 passed**.
- Current source and regression tests confirm that the July 12 heartbeat, artwork-directory, pagination, level-smoothing, processor-toggle, gapless lock-scope, mono file-output, and FFmpeg-cancellation findings were fixed. They are not reopened here.

---

## HIGH Findings

### REC-01: There is no usable single-owner application launcher

- **Severity**: HIGH
- **Dimension**: Startup / Process Lifecycle
- **Location**: `package.json:6-18`; `dev.js:20-55,57-251,295-325`; `desktop/main.js:26-248,393-429`; `launch-auralis-web.py:52-183`; `auralis-web/backend/main.py:209-216`
- **Status**: NEW
- **Description**: The three launch layers disagree about paths, package manager, port, readiness, and backend ownership.
- **Evidence**:
  1. From the repository root, `npm run dev` exits immediately:
     ```
     [SETUP] Installing Electron dependencies...
     [DEV] Failed to start: spawn npm ENOENT
     ```
     `dev.js` itself is in the repository root, but constructs component paths with `path.join(__dirname, '..', ...)`. It therefore looks for `desktop`, `auralis-web/backend`, and `auralis-web/frontend` one directory above the repository.
  2. `dev.js.start()` intends to start backend → frontend → Electron. Electron’s `initialize()` independently calls `startPythonBackend()`, which first calls `cleanupPort()`. That cleanup enumerates every PID bound to 8765 and runs `kill -9` / `taskkill /F`, without proving the process belongs to Auralis.
  3. Root and Python launchers use `npm` even though both JS workspaces declare pnpm and project instructions define pnpm as the supported manager.
  4. `launch-auralis-web.py.start_backend(port=...)` logs the requested port but starts `main.py` without passing it. `main.py` hardcodes 8765. `--port 9000` therefore prints URLs for 9000 while the child still binds 8765.
  5. The root launcher’s frontend branch marks a missing frontend “ready,” and after ten seconds marks a non-ready frontend “ready” anyway.
- **Impact**: The documented root development command does not start the app. A superficial path-only fix creates a second failure: two backend owners race, and one force-kills the other. The current cleanup can also terminate an unrelated user process on port 8765.
- **Attempted disproof**: Started backend and frontend components independently. The backend itself boots and the frontend itself builds, confirming this is orchestration failure rather than missing dependencies. Traced both backend creation paths to confirm duplicate ownership.
- **Required fix**:
  - Introduce one canonical root supervisor and one explicit backend owner per mode.
  - Recommended contract:
    - development: root supervisor owns backend + Vite; Electron connects with `AURALIS_BACKEND_MODE=external`
    - packaged desktop: Electron owns its child backend with `AURALIS_BACKEND_MODE=managed`
  - Propagate one `AURALIS_BACKEND_PORT` to Uvicorn, Electron, Vite/API config, and smoke tests.
  - Remove runtime dependency installation.
  - Never kill a PID discovered only by port. Terminate only a stored child handle/process group created by the current run.
  - Make root scripts pnpm-native and add the root `packageManager` field.

### REC-02: Fresh databases silently reject every first fingerprint insert

- **Severity**: HIGH
- **Dimension**: Library / Persistence
- **Location**: `auralis/library/models/fingerprint.py:22-92`; `auralis/library/repositories/fingerprint_repository.py:491-640`; `auralis/analysis/fingerprint/fingerprint_service.py:431-447`; `auralis/library/migration_manager.py:321-346`; `auralis/library/migrations/migration_v014_to_v015.sql:13`
- **Status**: NEW
- **Description**: `TrackFingerprint.is_reference` is `nullable=False, default=False`, but that is an ORM-side default. Fresh databases are created through `Base.metadata.create_all`, whose generated SQLite DDL is `is_reference BOOLEAN NOT NULL` with no server default. Both raw-text insert paths (`upsert` and `store_fingerprint`) omit `is_reference`, catch the resulting exception, and return failure.
- **Evidence**:
  - Compiled current model DDL:
    ```
    is_reference BOOLEAN NOT NULL,
    fingerprint_version INTEGER NOT NULL,
    ```
  - `FingerprintRepository.upsert()` supplies `fingerprint_version` explicitly but not `is_reference`.
  - `FingerprintRepository.store_fingerprint()` does the same.
  - All three focused persistence regressions fail because no row exists after the repository call:
    ```
    3 failed: no row for track_id=1
    ```
  - Upgraded databases are not equivalent: migration v14→v15 added `is_reference INTEGER NOT NULL DEFAULT 0`, so this is specifically a fresh-schema/create-all defect.
  - `FingerprintService._save_to_database()` calls this `upsert()` and turns its swallowed failure into `False`.
- **Impact**: On a new install or fresh test database, computed fingerprints are not persisted. Similarity, reference-cloud target selection, and cache reuse either remain empty or repeatedly recompute, while the app can continue without explaining why.
- **Attempted disproof**: Verified the same repository against a real fresh SQLite schema; verified that the migration schema has a server default and therefore limits the scope to create-all/fresh databases.
- **Required fix**:
  - Add `server_default=false()` (or explicit SQL default `0`) to `is_reference`.
  - Also include `is_reference` explicitly in raw INSERT parameters so repository correctness does not depend on DDL flavor.
  - Stop returning an unattached synthetic `TrackFingerprint` from `upsert`; return/refetch the persisted row or a truthful success type.
  - Do not swallow an integrity failure at debug level. Surface a structured repository error and make the fingerprint job terminal state reflect it.
  - Turn the three existing red tests green and run them once against both a create-all database and a migrated v14 database.

### REC-03: Adaptive processing crashes on two-dimensional mono audio

- **Severity**: HIGH
- **Dimension**: Audio Processing / Channel Invariants
- **Location**: `auralis/analysis/loudness_meter.py:108-173`; call path through `quality_metrics.py:116,229` → `continuous_mode.py:389` → `hybrid_processor.py:343`; regression at `tests/auralis/test_audio_processing_invariants.py:252`
- **Status**: NEW
- **Description**: `LoudnessMeter.apply_k_weighting()` handles 1-D mono correctly, but its `else` branch labels every 2-D input “Stereo.” During state initialization it unconditionally reads `audio_chunk[0, 1]`. A standard `(samples, 1)` mono buffer therefore raises `IndexError`.
- **Evidence**:
  ```
  IndexError: index 1 is out of bounds for axis 1 with size 1
  ```
  Reproduced through the real `HybridProcessor.process()` path, not by calling the helper in isolation.
- **Impact**: Mono material represented as `(n, 1)` cannot complete adaptive enhancement. This is a primary playback/mastering path and produces a hard failure rather than degraded output.
- **Attempted disproof**: The separate offline file-output mono regression now passes, but it exercises a different sibling path. The invariant suite still reproduces this crash in current source.
- **Required fix**:
  - Define one channel-shape contract at engine entry: either normalize `(n, 1)` to `(n,)`, or make the meter channel-count agnostic.
  - If retaining 2-D shapes, initialize filter state by iterating `audio_chunk.shape[1]`; never hardcode two columns.
  - Reset/rebuild filter state when the channel count changes between calls.
  - Add stateful regressions for 1-D mono, `(n,1)`, `(n,2)`, and sequential mono→stereo→mono processing.
  - Run the same fixtures through normal playback, enhanced streaming, and offline mastering.

### REC-04: Rapid track selection can play the older track

- **Severity**: HIGH
- **Dimension**: Frontend Playback Correctness
- **Location**: `auralis-web/frontend/src/hooks/player/usePlayTrack.ts:27-92`
- **Status**: Existing: **#4426 (OPEN)**
- **Description**: Every `playTrack()` creates and stores a new `AbortController`, but never aborts the previous controller before overwriting the ref. Two overlapping queue POSTs can resolve out of order; the older request can send the last `play_enhanced` message and replace the user’s newer selection.
- **Evidence**:
  ```ts
  const controller = new AbortController();
  abortRef.current = controller;
  ```
  Sibling hooks already use abort-before-replace. The six current tests cover only single invocations.
- **Impact**: Under normal rapid clicking and variable local latency, playback and the success toast can revert to the wrong track.
- **Attempted disproof**: Re-read current source and ran the focused six-test file; no overlap regression exists and the missing abort remains.
- **Required fix**: Implement abort-before-replace, guard all post-await effects with controller identity/current request generation, and add a two-deferred-request test proving “last user intent wins.”

---

## MEDIUM Findings

### REC-05: Startup can claim readiness when the backend or engine is unavailable

- **Severity**: MEDIUM
- **Dimension**: Readiness / Failure Reporting
- **Location**: `desktop/main.js:250-295,393-429`; `launch-auralis-web.py:102-183`; `auralis-web/backend/config/startup.py:458-466`; `auralis-web/backend/routers/health.py:24-64`; `tests/backend/full_stack_smoke.py:15-179`
- **Status**: NEW
- **Description**:
  - Electron’s health request resolves successfully on connection errors and timeouts, then prints “Backend health check passed.”
  - The Python launcher sleeps a fixed three seconds, never polls the child or endpoint, and prints “Auralis Web Interface is running.”
  - Component initialization failures are caught, partial state is rolled back, and the API continues. `/api/health` is a liveness endpoint that always returns `status="healthy"` with the import-time `HAS_AURALIS` flag; it does not represent post-startup component readiness.
  - `tests/backend/full_stack_smoke.py` is not named `test_*.py`, collects zero tests, and polls `localhost:8000` while the backend hardcodes 8765.
- **Impact**: Launchers and CI cannot distinguish a useful app from a live HTTP shell with rolled-back components. Users can receive a window and success logs even when requests will fail or return 503.
- **Attempted disproof**: A healthy isolated backend does answer correctly; the defect is specifically the failure branch and the absence/misuse of readiness semantics.
- **Required fix**:
  - Keep `/api/health` as process liveness.
  - Add `/api/ready` backed by mutable startup state and checks for library/repository/settings/player/processing components required by the selected mode.
  - Make every launcher poll `/api/ready`, fail on child exit, show captured tail logs, and use one bounded timeout.
  - Convert the smoke script into a collected, isolated test that selects an ephemeral port and temporary home/database.

### REC-06: Frontend verification is broadly red, but mostly because the harness drifted

- **Severity**: MEDIUM
- **Dimension**: Frontend Build / Test Reliability
- **Location**: `auralis-web/frontend/package.json:27-60`; `src/components/shared/CacheHealthMonitor.tsx:229`; multiple `src/**/__tests__`
- **Status**: NEW
- **Description**:
  - Production build passes, but `pnpm run type-check:prod` fails one error: `new Date(cacheHealth.timestamp)` receives `string | undefined`. The component has graph in-degree zero and is currently unmounted, so this is a release gate defect rather than a live-screen crash.
  - Full Vitest: **35 failed files / 178 passed files; 208 failed / 3,174 passed / 23 skipped tests; one unhandled rejection**.
  - The top five files account for 102 failures. Focused reproduction shows shared harness drift:
    - `TrackRow`: mocked Toast module omits `ToastProvider`
    - `PlayerControls`: component now requires Redux but tests render without a Provider
    - `TrackList`: virtual rows are not rendered under the obsolete jsdom/observer mocks
    - other failures include unwrapped async updates and stale UI expectations
  - `pnpm run test:memory` cannot start Vitest because Node is asked to parse the shell shim `node_modules/.bin/vitest` as JavaScript.
- **Impact**: The suite cannot protect recovery changes. A red result cannot distinguish a real playback regression from a missing provider, and the intended bounded-memory command is unusable.
- **Attempted disproof**: Production bundle completed; focused heartbeat/pagination/play tests passed 43/43. This confirms the 208 count must not be treated as 208 production defects.
- **Required fix**:
  - Fix or delete the dead `CacheHealthMonitor` before making production type-check blocking.
  - Invoke Vitest via the package binary (`vitest`) or its real JS entry, not `.bin/vitest` under `node`.
  - Repair shared test renderers first (Redux, Toast, WebSocket, router, QueryClient, virtualizer geometry), then rerun and classify the remaining failures.
  - Fail on unhandled rejections.
  - Preserve a small “working-state” suite that uses fewer mocks and exercises the real REST/WS contracts.

### REC-07: The Rust DSP crate’s red suite mixes live API defects with invalid tests

- **Severity**: MEDIUM
- **Dimension**: Rust DSP / Contract Confidence
- **Location**: `vendor/auralis-dsp/src/compressor.rs:154-168,197-250`; `stereo_analysis.rs:52-60,194-236`; `spectral_features.rs:82-105,197-205`; `variation_analysis.rs:6-99,168-200`; `fingerprint_compute.rs:197-306,545-571`
- **Status**: NEW
- **Description**: `cargo test --lib` reports **84 passed / 10 failed** across compressor, fingerprint, onset, spectral, stereo, and variation modules. The failures are not one coherent production regression:
  - Real exposed defect: the compressor calculates a block peak/RMS, then advances a per-sample envelope follower only once. With a constant `0.8` signal, threshold `-10 dB`, ratio `4:1`, the public Python binding reports `input_level_db=-15.79`, `gain_reduction_db=0`, and unchanged output.
  - Invalid/stale test: `compute_energy([0.3, 0.4])` is RMS `sqrt(0.125)=0.3536`, while the test expects `0.25`.
  - Undefined fixture: correlation tests use constant signals with zero variance, for which Pearson correlation is undefined, yet demand ±1.
  - Ambiguous contract: “dynamic range variation” compares within-frame peak/min ratios, while its test expects different constant frame amplitudes to count as varying dynamic range (that is loudness variation, which already reports correctly).
  - The Python fingerprint boundary used by the app passes 8/8 tests on normal fixtures.
- **Impact**: The crate cannot be certified, and at least one public PyO3 API does not implement its advertised behavior. However, the app currently uses the Python compressor implementation; no in-tree production caller of `auralis_dsp.compress` was found. This is not a P0 launch blocker.
- **Attempted disproof**: Reproduced the public compressor error through the installed extension; separately ran the live fingerprint adapter suite successfully and inspected each failed unit’s mathematical expectation.
- **Required fix**:
  - Write behavioral contracts before editing algorithms: steady tone, impulse, white noise, correlated/anti-correlated non-constant stereo, silence, and real music excerpts.
  - Correct invalid fixtures and expected formulas.
  - Fix the compressor’s time-domain smoothing or mark/remove the binding until it is production-ready.
  - Compare Rust fingerprint output against the canonical Python/reference implementation with tolerances on real fixtures.
  - Only then make `cargo test --lib` and a small PyO3 boundary suite blocking.

---

## LOW Finding

### REC-08: Static quality debt is large but is not the shortest path to a working app

- **Severity**: LOW
- **Dimension**: Maintainability / Tooling
- **Location**: repository-wide
- **Status**: NEW (aggregate baseline; individual items overlap existing debt issues)
- **Description**:
  - Ruff: 916 findings (355 safe auto-fixable), dominated by broad exception handling, import ordering, and modernization.
  - Mypy: 274 errors in 93 files.
  - Clippy with `-D warnings`: 42 errors.
  - Frontend production build warns about an `Alert` barrel re-export creating a circular cross-chunk dependency and a 705 KB vendor chunk.
  - Runtime-version declarations disagree: `.python-version` and the working virtualenv use Python 3.13.9, the root `package.json` requires Python 3.14+, and Electron’s recovery message asks for Python 3.13+.
  - Root `Makefile` references absent scripts (`build_auralis.py`, `run_all_tests.py`, `auralis_gui.py`), and docs still mix npm, pnpm, ports 8000/8765, and incomplete frontend-build instructions.
- **Impact**: These slow change and hide signal, but bulk cleanup before REC-01..04 would increase risk while leaving the app unlaunchable.
- **Required fix**: Freeze counts, enforce “no new debt” on touched files, and reduce by subsystem after the working-state gate is green. Handle the Rollup cycle before relying on the affected lazy chunks in the acceptance smoke.

---

## Test Baseline and Interpretation

| Check | Result | Interpretation |
|---|---|---|
| `uv pip check` | 95 packages compatible | Environment is not the launch blocker |
| Python import/backend import | Pass | Core and API modules load |
| Real isolated Uvicorn boot | Pass, ready in ~2s | Backend can work |
| Python collection | 5,466 tests | Discovery works |
| Broad Python `not slow` run | Manually stopped at 27%; at least 4 failures surfaced | Too broad/slow for the first gate; use targeted slices |
| Fingerprint persistence tests | 3/3 fail | Live fresh-schema defect (REC-02) |
| Audio invariants | 1 mono crash, 17 pass, 1 xfail | Live channel defect (REC-03) |
| Album API file | 30 pass, 2 fail | Failures are stale Mock return shape, not yet a confirmed route bug |
| Targeted July high-risk regressions | 77 pass, 4 skip | Prior fixes remain present |
| Frontend production build | Pass with chunk warnings | Bundle can be produced |
| Frontend production type-check | 1 error | Dead component still blocks the type gate |
| Full frontend Vitest | 208 fail, 3,174 pass, 23 skip | Mostly harness/test drift; must be triaged |
| Targeted WS/pagination/play frontend | 43/43 pass | Several repaired live contracts are sound |
| Rust `cargo test --lib` | 84 pass, 10 fail | Mixed implementation and test-contract defects |
| Python↔Rust fingerprint glue | 8/8 pass | Current normal-fixture boundary works |

---

## Definition of “Working”

The recovery is complete when a clean checkout can pass this contract on a developer machine and in CI:

1. One documented command installs nothing implicitly, starts the selected mode, and returns non-zero if any required child fails.
2. Startup uses an isolated fresh home/database and reaches `/api/ready`; logs and UI do not claim success before that.
3. Shutdown terminates only children created by that run and leaves no backend/Vite/FFmpeg process behind.
4. Scan a fixture folder containing:
   - stereo WAV
   - `(n,1)` mono WAV
   - one FFmpeg-routed file such as MP3
5. Library totals, pagination, album/artist drill-down, and artwork remain correct across at least three pages.
6. Fingerprints persist on the fresh database and remain after restart.
7. Play each fixture in normal and enhanced mode; seek, pause/resume, next, previous, and queue update work.
8. Two rapid track selections always leave the second track active.
9. Keep the WebSocket open for at least 75 seconds without a heartbeat reconnect.
10. Assert audio invariants at the stream boundary: finite float32 PCM, same sample count, valid channel count, no exception.
11. Browser/Electron console has no uncaught exception or unhandled promise rejection during the flow.

Explicitly **not required** for this milestone:

- all 5,466 Python tests green
- all 3,405 frontend tests green
- zero Ruff/Mypy/Clippy warnings
- finished cache/similarity/dead UI surfaces
- bundle-size optimization or visual polish

---

## Recovery Plan

### Phase 0 — Make startup truthful and single-owner

1. Add a small launch contract module:
   - one port source (`AURALIS_BACKEND_PORT`)
   - one mode (`web`, `desktop-dev`, `desktop-packaged`)
   - one backend ownership flag (`external`, `managed`)
   - explicit child PID/process-group tracking
2. Replace the path arithmetic in `dev.js` with repository-root-relative paths and pnpm commands.
3. Remove duplicate backend startup:
   - root owns backend in web/desktop-dev
   - Electron owns backend only in packaged mode
4. Delete force-kill-by-port behavior. On port collision, fail with the PID/port diagnostic and ask the user to resolve it.
5. Teach Uvicorn to read the configured port.
6. Add mutable startup state and `/api/ready`.
7. Make all supervisors poll readiness and child liveness.
8. Convert `full_stack_smoke.py` into a collected isolated subprocess test.

**Exit gate**: `pnpm dev` reaches a truthful ready state from a clean checkout and shuts down cleanly; a deliberately failed backend never opens a “ready” window.

### Phase 1 — Repair the smallest complete product slice

1. Fix fresh-database fingerprint inserts (REC-02).
2. Fix `(n,1)` mono K-weighting/state handling (REC-03).
3. Fix last-intent-wins track selection (#4426 / REC-04).
4. Add fixture-based regressions at the product boundaries, not just helper units.
5. Exercise scan → persist → list → play normal → play enhanced → restart.

**Exit gate**: all eleven “Definition of Working” checks pass against a fresh temporary home/database.

### Phase 2 — Restore trustworthy gates

1. Fix the one production TypeScript error.
2. Repair `test:memory` and `test:coverage:memory`.
3. Repair shared frontend render infrastructure before editing individual assertions:
   - Provider composition
   - Toast/WebSocket partial mocks
   - virtualizer sizes and IntersectionObserver
   - async `act` boundaries
4. Classify every remaining frontend failure as:
   - product regression
   - stale expectation
   - test harness
   - dead surface to delete
5. Fix the fresh-fingerprint and mono Python regressions first, then run subsystem suites. Repair stale album fingerprint mocks separately.
6. Split Rust failures into invalid fixtures vs implementation defects; fix the exposed compressor contract and add real-audio fingerprint comparison.
7. Create one fast command, for example `pnpm test:working`, that runs:
   - production TypeScript check
   - frontend working-state tests
   - targeted Python startup/library/audio tests
   - Rust/PyO3 boundary tests
   - isolated full-stack smoke

**Exit gate**: the fast working-state gate is deterministic and green three consecutive times.

### Phase 3 — Harden real-session behavior

1. Add the 75-second WebSocket heartbeat soak to CI.
2. Add rapid switching, queue mutation during playback, and restart/resume flows.
3. Validate WAV/FLAC/MP3, mono/stereo, short tracks, and corrupted input.
4. Verify cancellation leaves no FFmpeg process.
5. Run concurrency regressions around player locks, processor sharing, scanning, and fingerprint scheduling.
6. Inspect the production bundle’s metadata-dialog and toast chunks to eliminate the Rollup execution-order warning.

**Exit gate**: ten repeated end-to-end runs with no wrong track, orphan process, 500, uncaught UI exception, or PCM invariant violation.

### Phase 4 — Reduce debt without destabilizing recovery

1. Enforce no-new Ruff/Mypy/Clippy debt on modified files.
2. Remove or revive dead cache/analysis surfaces; do not keep broken unmounted components in the production type graph.
3. Consolidate duplicate HTTP clients, pagination hooks, and launcher docs.
4. Repair or remove stale Make targets and npm instructions.
5. Work through the broader open-issue and audit backlog by user impact.

---

## Recommended Change Sequence

Keep recovery changes reviewable and bisectable:

1. **Launch contract + no destructive port cleanup**
2. **Readiness endpoint + isolated collected smoke**
3. **Fresh DB fingerprint persistence**
4. **Mono channel normalization**
5. **Rapid track last-intent-wins (#4426)**
6. **Frontend production type/test harness**
7. **Rust behavioral contracts and exposed compressor**
8. **Static debt/docs cleanup**

Do not combine the broad Ruff/Mypy/format cleanup with phases 0–2; it would obscure the functional diffs and make regression bisection much harder.

---

## Deduplication Notes

- REC-04 is already tracked by open issue #4426 and should not be re-filed.
- No matching open issue or current audit finding was found for:
  - root `dev.js` resolving outside the repository
  - duplicate backend ownership / kill-by-port behavior
  - ignored launcher port and false health success
  - fresh-schema `is_reference` insert failure
  - `(n,1)` LoudnessMeter crash
  - broken Vitest memory script
  - current Rust ten-failure cluster
- July 12 findings for heartbeat pong, artwork serving directory, frontend pagination, level smoothing, shared processor flag, player lock scope, offline mono file output, and cancellable FFmpeg were rechecked and are fixed in current source.
- Open documentation issue #4267 overlaps the incomplete quick-start story, but not the executable launcher defects in REC-01.
- Existing Rust issue #3690 covers `chroma_energy` semantics only, not REC-07.

---

## Bottom Line

This is not a “fix hundreds of random tests” recovery. The fastest credible route is:

1. establish one truthful launcher and readiness contract,
2. fix fresh fingerprint persistence and mono adaptive processing,
3. close the wrong-track race,
4. automate the eleven-item working-state flow,
5. then use that green slice to triage the larger red suites safely.

That produces a genuinely usable application while preserving a clear boundary between **working** and **finished**.
