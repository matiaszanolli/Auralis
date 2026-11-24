# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) — and, via the
pointer in `AGENTS.md`, other agent tooling — when working with code in this
repository. This is the single hand-maintained source of truth; `AGENTS.md`
is a thin stub that points here rather than an independent copy (#5027).

**Project**: Auralis — Music player with real-time audio enhancement
**Version**: 1.5.1 recovery milestone (`auralis/version.py` is source of truth; not tagged)
**Python**: 3.14+ | **Node**: 24+ | **Rust**: Required (PyO3 DSP module)
**License**: AGPL-3.0 (dual-licensed, see COMMERCIAL_LICENSE.md)

## Commands

```bash
# Set up and launch from the repository root
# `--python-preference only-managed` or uv silently picks a stale pyenv shim
uv venv --python-preference only-managed && source .venv/bin/activate
uv pip install -r requirements.txt                      # runtime only
uv pip install -e '.[dev]' maturin                       # pytest, mypy, ruff; the Rust build tool
pnpm --dir auralis-web/frontend install --frozen-lockfile
pnpm --dir desktop install --frozen-lockfile
pnpm run dev                                             # Electron, backend :8765, Vite :3000
python launch-auralis-web.py --dev --no-browser           # Browser preview, same ports

# Test — scope first, widen once. `-q` keeps passes as dots; `-v` dumps every
# test name into context for thousands of tests.
python -m pytest -q -m "not slow" tests/auralis/dsp     # A domain (the normal inner loop)
python -m pytest tests/path.py::test_name -vv -s        # Single test
cd auralis-web/frontend && pnpm run test:memory         # Frontend (2GB heap; OOMs without it)

# Whole backend suite. NOT "~2-3 min" — it is tens of minutes. These two files
# used to hang as whole files; #4781/#5095 fixed both and per-push CI runs them,
# but the nightly still excludes them, and so should a local whole-suite run:
python -m pytest -q -m "not slow" \
  --ignore=tests/backend/test_system_api.py \
  --ignore=tests/concurrency/test_thread_safety.py

# Type check
mypy auralis/ auralis-web/backend/ --ignore-missing-imports
cd auralis-web/frontend && pnpm run type-check

# Build Rust DSP (required before first run: /api/ready stays 503 without it).
# `--uv` because a uv venv has no pip, which plain `maturin develop` needs.
cd vendor/auralis-dsp && maturin develop --uv --release
```

## CI gates and the failure baselines

The test gates are **ratchets**: a run is judged against a checked-in list of
known failures and fails only on failures *not* in that list. The list may
shrink, never grow. All three lists (backend, nightly slow, frontend) are
**empty**, so any test failure is new. `--strict-stale` also fails a job on a
listed test that now passes.

| Workflow | Runs | Baseline | Gate script |
|---|---|---|---|
| `frontend-test.yml` | `pnpm run test:ci`, then `test:weak` | `auralis-web/frontend/test-baseline.json` | `auralis-web/frontend/scripts/check-test-baseline.mjs --strict-stale` |
| `backend-tests.yml`, job `pytest` | `pytest --junitxml` | `pytest-baseline.json` | `scripts/check_pytest_baseline.py --strict-stale` |
| `backend-tests.yml`, job `gates` | weak/zero-assertion, LOC ratchet, breadcrumbs, ruff F401/F811/F841 | `weak-assertions-baseline.json`, `zero-assertions-baseline.json`, `loc-ceilings.json` | `scripts/check_weak_assertions.py`, `check_loc_ratchet.py`, `check_breadcrumbs.py` |
| `slow-tests.yml` (nightly) | `pytest -m slow --junitxml` | `pytest-slow-baseline.json` | `scripts/check_pytest_baseline.py --baseline` |
| `frontend-typecheck.yml` | `pnpm run type-check:prod` and `type-check` | — (must be clean) | — |
| `path-references.yml` | `.claude/commands/_audit-validate.sh` | `.claude/commands/_audit-validate-baseline.txt` (empty) | — (exit code decides) |

The test step itself always exits 0; **the baseline step is what decides the
job**. Both test gates also fail on a missing report or 0 collected tests, so a
crashed runner cannot pass as green. Read a failing run's *baseline* step, not
the test step.

**When you fix a listed failure, regenerate the baseline**, or `--strict-stale`
fails the job. Build a pytest baseline from the **CI junit artifact**
(`python scripts/check_pytest_baseline.py <junit.xml> --update`), not a local
run: a different interpreter or dependency set reports spurious failures. The
frontend baseline is regenerated locally, and `check-installed-deps.mjs`
refuses to write it unless the installed jsdom/vitest match the lockfile:

```bash
cd auralis-web/frontend && pnpm run test:ci && pnpm run test:baseline:update
```

Do not add a `version:` input to `pnpm/action-setup`: every `package.json` here
declares `packageManager`, and supplying both makes the action hard-error before
it installs anything. Backend CI must stay on Python 3.14 — on 3.13 the
codebase's PEP 649 deferred annotations fail at import and the suite collects
zero tests.

## Codebase Map

```
auralis/                          Core Python audio engine
├── core/                         Processing pipeline
│   ├── hybrid_processor.py         HybridProcessor — the app's DSP pipeline (streams and jobs)
│   ├── processing/                 Mode processors (adaptive, continuous, hybrid); ContinuousMode
│   │                                 renders the track-level plan, `adaptive` is the only preset
│   ├── config/                     Processing configuration (UnifiedConfig)
│   ├── simple_mastering.py,        OFFLINE CLI mastering (auto_master.py) with its own
│   │   mastering_*.py, stages/,      stage pipeline — not on the app's audio path
│   │   dsp/
│   └── recording_type_detector.py  OFFLINE scripts only (rate_track, update_profile); not on the
│                                     app's audio path — kept on purpose, see #4873 / #5780
├── dsp/                          Signal processing
│   ├── basic.py                    DSP primitives
│   ├── eq/                         Psychoacoustic EQ (psychoacoustic_eq.py)
├── analysis/                     Audio analysis (largest module, 76 files)
│   ├── fingerprint/                25D fingerprinting system (audio_fingerprint_analyzer,
│   │   ├── metrics/                  rust_fingerprint, windowed_compute, schema, distance,
│   │                                 similarity, knn_graph, normalizer)
│   ├── quality_assessors/          BaseAssessor + utilities (the assessors live in quality/)
│   ├── ml/                         RuleBasedGenreClassifier (linear, not a neural net)
│   └── quality/                    Quality assessment (loudness, distortion, DR)
├── player/                       Python playback engine. The app's audible output is the
│   │                               renderer's WebSocket stream, not this player's buffer
│   ├── enhanced_audio_player.py    AudioPlayer, composed of mixins (host hooks: see Patterns)
│   ├── gapless_playback_engine.py  Gapless playback
│   ├── queue_controller.py         Queue management
│   └── realtime/                   Real-time processing (RealtimeProcessor, AutoMasterProcessor)
├── library/                      SQLite library (~/.auralis/library.db)
│   ├── database.py                 LibraryDatabase (engine, migration, sessions, scan slots)
│                                     Startup stores it under the globals key `library_database`
│                                     (renamed in #5162; it used to name the class #4915 deleted)
│   ├── repositories/               12 repos + base.py (BaseRepository) + factory.py
│   │                                 (track, album, artist, playlist, genre, stats,
│   │                                 fingerprint, fingerprint_scheduler, fingerprint_stats,
│   │                                 settings, similarity_graph, processing_job)
│   ├── scanner/                    Folder scanning (a package, not a module)
│   └── migration_manager.py        DB migrations (schema version: __db_schema_version__)
├── io/                           Audio I/O
│   ├── unified_loader.py           Unified loading (FFmpeg, SoundFile)
│   └── results.py                  Output formats (pcm16, pcm24)
├── optimization/                 Performance — LIVE, not test-only (#5142)
│   ├── performance_optimizer.py    get_performance_optimizer(); hybrid_processor.py
│   │                                 calls hybrid_setup.apply_module_optimizations() at
│   │                                 import, which wraps AdaptiveMode.process for
│   │                                 PROFILING ONLY, never memoization (#4524)
│   └── profiling/
│                                   (parallel/ + parallel_processor.py deleted #4565;
│                                    NO rust_integration.py — see #5168)
├── services/                     Background services (fingerprint, artwork)
├── learning/                     Reference-cloud seeder (the preference engine was removed, #5763)
└── utils/                        Logging, helpers, validation, atomic writes

auralis-web/
├── backend/                      FastAPI REST + WebSocket (:8765)
│   ├── main.py                     App entry point
│   ├── routers/                    20 registered routers (player, library, tracks,
│   │                                 albums, artists, playlists, enhancement,
│   │                                 metadata, artwork, files, system, settings,
│   │                                 cache, similarity, similarity_graph, library_scan,
│   │                                 fingerprint_status, fingerprint_queue,
│   │                                 processing, health)
│   ├── core/                       Engine-facing layer. NOT top-level (#4627):
│   │   ├── processing_engine.py      Audio processing orchestration
│   │   ├── chunked_processor.py      ChunkedAudioProcessor: 15s chunks rendered w/
│   │   │                               context from one whole-track plan; chunk 0
│   │   │                               emits 15s, later chunks 10s NON-overlapping
│   │   │                               segments (no crossfade)
│   │   ├── audio_stream_controller.py  WebSocket audio streaming (raw float32 PCM frames)
│   │   ├── stream_*.py               normal/enhanced/seek streaming paths
│   │   ├── chunk_boundaries.py       Sole chunk-geometry authority
│   │   ├── mastering_target_service.py  Per-track fingerprint/plan cache: analysis is
│   │   │                               whole-track, chunks only render the plan
│   │   └── executors.py              Four thread pools: stream, I/O, job, transport (#5086)
│   ├── schemas/                    Request/response schemas (by domain)
│   └── services/, config/          Service layer, startup/config
└── frontend/                     React 18 + TypeScript + Vite + Redux
    └── src/
        ├── components/               UI components
        ├── hooks/                    Domain hooks (player, library, enhancement,
        │                               websocket, api, app, audio, fingerprint, shared)
        ├── store/                    Redux state management
        ├── design-system/            Design tokens (single source of truth)
        ├── services/                 API clients
        └── test/                     Test utilities

vendor/auralis-dsp/               Rust DSP via PyO3 (25D fingerprint only, #5764)
desktop/                          Electron wrapper
tests/                            ~8,600 test functions (1,095 files) across 16 subdirs (auralis, backend,
                                    integration, boundaries, concurrency, security, load_stress, regression...)
docs/                             13 topic dirs; start at docs/README.md (living docs only —
                                    point-in-time material is in docs/archive/)
```

Structural counts above (analysis file count, router count, test file/function
counts, docs topic-dir count) and the matching table in
`.claude/commands/_audit-common.md` are two hand-maintained copies of the same
numbers and will drift apart again if only one is edited. Run
`python scripts/check_doc_counts.py` to recompute both from the live tree
before updating either file, and update both together (#4982).

## Architecture Flow

```
User → FastAPI (REST + WebSocket :8765) → Backend Services
         → LibraryDatabase (SQLite) → HybridProcessor (DSP pipeline)
         → ChunkedAudioProcessor (15s w/ context → 10s non-overlapping; chunk 0 is 15s)
         → float32 PCM over WS → React (Redux) → Web Audio (AudioWorklet)
```

## Critical Invariants

**Audio processing** — sample count preservation is critical for gapless playback:
```python
assert len(output) == len(input)              # Never change sample count
assert isinstance(output, np.ndarray)         # Always NumPy, never lists
assert output.dtype in [np.float32, np.float64]
output = audio.copy()                         # Never modify in-place
```

**Player state**: position ≤ duration, queue index valid, state changes atomic (RLock).
**Database**: thread-safe pooling (`pool_pre_ping=True`), no N+1 (`selectinload()`), all access via repositories.

**Detached ORM instances** — repositories `expunge()` everything they return, so
any relationship a query did not eager-load raises `DetachedInstanceError` when
`to_dict()` touches it. Two rules, both required:
- the repository's read paths carry `selectinload(Model.rel)` (define the option
  tuple once at module scope so a new read path cannot silently omit it);
- `to_dict()` reads relationships through `_safe_collection()` / `_safe_scalar()`
  in `library/models/_helpers.py`, which degrade to `[]` / `None` and log a WARNING
  naming the missing eager-load.

`refresh()` expires an instance without re-applying query options, so
post-commit paths must touch the relationship while still attached.

**Chunk geometry**: `CHUNK_DURATION` / `INTERVAL` / `OVERLAP` / `CONTEXT` come
only from `backend/core/chunk_boundaries.py`; `content_chunk_count()` is the sole
chunk-counting authority (overlap-aware — not `ceil(duration / CHUNK_DURATION)`).
Its one twin there is `normal_chunk_count()`, for the no-overlap normal stream.
Cached chunk files are 16-bit PCM WAV, not float32.

## Patterns

**Python backend**: Routers auto-included via `include_router()`. All handlers `async def`. Errors via `HTTPException`. Shared state protected with `threading.RLock()`.

**React frontend**: `@/` absolute imports only. Colors via `import { tokens } from '@/design-system'`. Components < 300 lines. Tests use `vi.*` (Vitest), `render` from `@/test/test-utils`.

**Audio DSP**: Load metadata (sample rate, channels) BEFORE processing. Vectorize with NumPy (chunks, not samples). Copy before modify.

**Mixin host hooks**: A split mixin that calls a method its composed host provides types it as a bare class-level annotation (`load_file: Callable[[str], bool]` with a `# Provided by X.` comment — see `player_queue_navigation_mixin.py`), never as a `raise NotImplementedError` method: a runtime stub occupies the MRO ahead of sibling mixins and reads as fake debt (#6235).

## Principles

1. **DRY** — Improve existing code, never duplicate. Use utilities for shared logic.
2. **Modular** — < 300 lines per module, single responsibility.
3. **No variants** — No "Enhanced"/"V2"/"Advanced" copies. Refactor in-place.
   The rule is about *copies that coexist with their base*. `Streamlined*`
   (`StreamlinedCacheManager`, `StreamlinedCacheWorker`), `UnifiedConfig` and
   `unified_loader` keep those names although the multi-tier buffer, `Config`/
   `LimiterConfig` and the non-unified loaders they replaced are gone (#5829):
   they are the only implementation and the proper names — do not re-flag them,
   and do not add a second class next to one.
4. **Repository pattern** — All DB via `auralis/library/repositories/`, never raw SQL.
5. **Deferrals are greppable** — Write a deferred decision as `# TODO(#NNNN):`
   with a real issue number, not as prose ("For now, …", "Temporarily …").
   Prose deferrals are invisible to any marker sweep, so `/audit-tech-debt` has
   to fall back to a high-recall prose grep that cannot distinguish a deferral
   from an ordinary sentence (#4564). Genuine marker debt in shipped code —
   `auralis/`, `auralis-web/`, `vendor/` — is **3** (2026-11-23: #5484,
   #5098, #6721 — #5098 and the air-band deferral were prose until
   #6599/#6600; #6356 merged the EQ laws and handed that marker to #6721),
   each citing an OPEN issue; `tests/` holds **0** (2026-11-22: the two #6715
   markers went with the 1-hour processing tests they skipped). A
   marker citing a closed issue is itself a finding (the `TODO(#5537)` in
   `py_bindings.rs` was re-pointed at #5738, which then deleted the code). #5152 turned the prose
   "Retiring it is tracked separately" into a `TODO(#5295)` that `134c74ae`
   later retired with the dead dynamics path — the rule working end to end.
   Keep both figures honest by linking the issue instead of leaving a bare
   `TODO`.
   The scope matters: that "0" was quoted repo-wide for weeks while every
   genuine marker in the tree sat in `tests/`, uncounted (#5143), so
   `/audit-tech-debt` now reports the two censuses as separate lines.

## Git

Branch from `master`. Prefixes: `feature/`, `fix/`, `refactor/`, `docs/`. Commit:
`type: description`. Before PR, run the **scoped** tests for what you touched plus
`mypy` / `type-check` — the full suite is a CI job, not an inner loop.

Commits to `master` do not auto-push. `git log` / `git status` can shift mid-session:
work is done in this repo from parallel terminals, so re-check rather than assuming
staleness. Commit each logical unit as soon as its scoped tests pass.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 8765 in use | `lsof -ti:8765 \| xargs kill -9` |
| Frontend tests OOM | `pnpm run test:memory` (2GB heap) |
| Database locked | Kill python, delete `~/.auralis/library.db` |
| Rust module missing, or `/api/ready` stuck at 503 | `cd vendor/auralis-dsp && maturin develop --uv --release` |
| `maturin`: "Failed to find pip" | Add `--uv`; a uv venv has no pip |
| pytest run never finishes | Scope the run; for a whole-suite run `--ignore` `test_system_api.py` / `test_thread_safety.py` as the nightly does, or add `--timeout=60` |
| CI red in <20s | Setup failure, not tests — check `pnpm/action-setup` / Python version before reading test output |

## Reference Docs

- [Documentation hub](docs/README.md) — index of every living doc: architecture, the six
  subsystem deep-dives (DSP, fingerprinting, player, library, backend, frontend), guides.
- [Product requirements](docs/prd/README.md) — PRD index and template for milestone and workflow changes.
- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) and
  [TEST_EXECUTION_GUIDE.md](docs/development/TEST_EXECUTION_GUIDE.md)
- [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)
- [FIRST_TIME_SETUP.md](FIRST_TIME_SETUP.md)

Living docs are held to the path-reference gate: a backticked path must exist (name deleted
code in *italics*), cite `<file>.py::<Symbol>` never `<file>.py:<line>`, and every markdown link must
resolve. A new living doc goes in `living_docs` in `.claude/commands/_audit-validate.sh`.
