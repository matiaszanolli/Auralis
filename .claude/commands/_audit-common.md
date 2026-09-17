---
description: "Shared audit protocol — project layout, methodology, dedup, finding format. Referenced by all audit skills."
---

# Common Audit Protocol — Auralis

**Do not invoke this file directly.** It is referenced by all specialized audit commands.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`.

```
Audio Engine:        auralis/                                Core Python audio engine
Core Pipeline:       auralis/core/                           hybrid_processor.py + hybrid_processor_singleton.py + hybrid/ (dynamics_manager.py, preference_manager.py), simple_mastering.py + mastering_*.py (chunk_loop, prepare, process_chunk, notch_context, diagnostics, config, presets), mastering_branches/ (continuous only — see note below), processing/ (continuous_space.py, continuous_mode.py + continuous_*.py helpers, adaptive_mode.py, hybrid_mode.py, parameter_generator*.py, target_derivation.py, delta_eq.py, base/), processors/ (reference_mode.py), stages/ (13 named DSP stages), analysis/ (incl. spectrum_mapper/), dsp/, utils/, recording_type_detector.py
Core Config:         auralis/core/config/                    UnifiedConfig package (unified_config.py, factory.py, settings.py, preset_profiles.py — 'adaptive' is its only entry since 2026-09-13, genre_profiles.py) — a same-named auralis/core/config.py once existed but was dead code (a package directory always shadows a same-named module file in Python's import system) and was deleted in #4918
DSP:                 auralis/dsp/                            basic.py, advanced_dynamics.py, eq/ (psychoacoustic_eq.py, parallel_eq_processor/), dynamics/, utils/
Player:              auralis/player/                         enhanced_audio_player.py (class AudioPlayer — there is no EnhancedAudioPlayer class; it is composed from player_*_mixin.py + fingerprint_loader_mixin.py), gapless_playback_engine.py, queue_controller.py, playback_controller.py, integration_manager.py, audio_file_manager.py, config.py, realtime/ (processor.py, auto_master.py, gain_smoother.py, level_matcher.py, performance_monitor.py), components/
Library:             auralis/library/                        database.py (LibraryDatabase — the sole composition root: engine, pragmas, migration, session factory, scan slots, shutdown), scanner/ (package), models/ (ORM package), migrations/ (SQL, through v017_to_v018), migration_manager.py (+ migration_engine.py, migration_steps.py, migration_backup.py, migration_lock.py — the fcntl/msvcrt file lock and the same-process threading.Lock both live in migration_lock.py), metadata_editor/, sidecar_manager.py, artwork.py, fingerprint_quantizer.py, path_key.py, resource_monitor.py, scan_models.py, constants.py, utils/. The LibraryManager facade and its cache layer were deleted in #4915 — see Retired Architecture below.
Repositories:        auralis/library/repositories/           13 repos + base.py (BaseRepository) + factory.py (RepositoryFactory): track, album, artist, playlist, genre, stats, fingerprint, fingerprint_scheduler, fingerprint_stats, queue_history, settings, similarity_graph, processing_job. Three are split across helper files — track_repository_{lifecycle,lookup,maintenance,mutation,search}.py, playlist_{crud,membership,ordering,query}_mixin.py, fingerprint_{crud,query,similarity,upsert}_mixin.py + fingerprint_shared.py — so "13" counts repositories, not files
Analysis:            auralis/analysis/                       55 files; fingerprint/ (25D), ml/, quality/, quality_assessors/, plus top-level loudness_meter.py, dynamic_range.py, phase_correlation.py, spectrum_operations.py, mastering_fingerprint.py, mastering_profile.py, adaptive_mastering_engine.py
Audio I/O:           auralis/io/                             unified_loader.py, loader.py, loaders/, formats.py, processing.py, saver.py, results.py (pcm16/pcm24)
Optimization:        auralis/optimization/                   acceleration/simd_accelerator.py, caching/smart_cache.py, memory/memory_pool.py, profiling/performance_profiler.py, config.py, performance_optimizer.py. LIVE ENGINE CODE — audit at full severity (#5142). auralis/core/hybrid_processor.py calls apply_module_optimizations() unconditionally at its own module-import time (grep the symbol — line numbers drift); #5463 split that function's body, plus the get_performance_optimizer import it needs, out into the sibling auralis/core/hybrid_setup.py, but the call site stayed in hybrid_processor.py, so importing the main DSP pipeline still constructs the PerformanceOptimizer singleton and wraps AdaptiveMode.process in a profiling decorator that then runs on every real mastering call. performance_optimizer.py's imports pull in SIMDAccelerator, SmartCache, PerformanceConfig, MemoryPool and PerformanceProfiler, so every module listed above is transitively live. The parallel_processor.py + parallel/ cluster it used to anchor WAS dead and was deleted in #4565 — do not over-generalize that deletion to the rest of the package, which is what the retracted "no production code imports this package, cap severity accordingly" instruction did. hybrid_processor.py and hybrid_setup.py are the two production importers (#5463 split the one sole importer into this pair — do not describe either alone as "the sole importer"). There is NO rust_integration.py, and nothing imports one any more: the dead auralis/dsp/utils/spectral.py branch that did was removed in #5168 (3288441d). scripts/check_optimization_importers.py enforces this row.
Services:            auralis/services/                       artwork_service.py, fingerprint_extractor.py, fingerprint_queue.py (+ fingerprint_queue_manager.py lifecycle, fingerprint_queue_scaling.py adaptive sizing, fingerprint_worker.py execution), resizable_semaphore.py
Learning:            auralis/learning/                       preference_engine.py, reference_library.py, reference_seeder.py, components/
CLI:                 auralis/cli/                            fetch_artwork.py
Utils:               auralis/utils/                          logging.py, helpers.py, atomic_write.py, audio_validation.py, artwork_security.py, checker.py, queue/

Backend:             auralis-web/backend/                    FastAPI :8765
Backend Entry:       auralis-web/backend/main.py             Thin entry — builds the lifespan, then delegates to config/. StaticFiles mount + `--dev` switch live here.
Backend App Wiring:  auralis-web/backend/config/             app.py (create_app), middleware/ (package, one module per middleware: CORS wiring + RateLimit + SecurityHeaders + NoCache + OriginCheck), routes.py (registers all 20 routers), startup.py (lifespan), origins.py (loopback origin policy), background_workers.py, globals.py, limits.py
Backend Routers:     auralis-web/backend/routers/            26 .py files = 20 registered routers + helpers (dependencies.py, errors.py, pagination.py, serializers.py, similarity_common.py)
Backend Streaming:   auralis-web/backend/core/               54 modules in four families plus singletons. chunk_*: chunked_processor.py is a coordinator (#4245) over chunk_render / chunk_streaming / chunk_batch / chunk_metadata / chunk_path_cache / chunk_processor_init / chunk_content_profile / chunk_fingerprint_registry, alongside chunk_boundaries.py (chunk-constant SoT), chunk_cache_manager.py, chunk_mastering.py, chunk_operations.py (render-with-context + trim), chunk_crossfade.py (no production caller — see Retired Architecture). stream_*: enhanced (+ enhanced_chunks pump, which owns the look-ahead task), normal (+ normal_chunks), seek (+ seek_chunks), protocol, messages, chunk_ops, fingerprint, track_resolution. job_*: processing_engine.py is a coordinator (#4250) over job_lifecycle / job_execution / job_config / job_progress / job_finalize / job_cleanup / job_error_mapping, plus job_models.py and job_worker.py. streamlined_*: worker, tiers, processor_cache. Singletons: audio_stream_controller.py, executors.py (streaming + I/O thread pools, #5086), cache_cleanup.py (one lifecycle boundary for every cache tier, #5257), processor_pool.py, processor_factory.py, state_manager.py, proactive_buffer.py, audio_processing_pipeline.py, mastering_target_service.py, level_manager.py, seekable_source.py, file_signature.py, thumbnail_cache.py, env_config.py, encoding/
Backend Cache:       auralis-web/backend/cache/              manager.py, monitoring.py — the streamlined cache surface behind routers/cache_streamlined.py. Distinct from the chunk cache in core/ and the thumbnail cache in core/thumbnail_cache.py; all three are separate caches with separate invalidation rules.
Backend WebSocket:   auralis-web/backend/ws_handlers/        connection.py, context.py, messages.py, playback_commands.py, playback_control.py
                     auralis-web/backend/websocket/          websocket_protocol.py, websocket_security.py, outbound_messages.py (typed broadcast contracts; imports schemas.EnhancementPresetLiteral)
Backend Security:    auralis-web/backend/security/           path_security.py (path containment); rate limiting + security headers live in the config/middleware/ package
Backend Schemas:     auralis-web/backend/schemas/                package, by domain (enhancement, websocket, library, request_bounds, system, mastering)
Backend Services:    auralis-web/backend/services/           library_auto_scanner.py, queue_service.py, queue_enrichment.py, queue_protocols.py, playback_service.py, playback_event_sequencer.py (process-wide ordering of discrete playback WS events), navigation_service.py, recommendation_service.py, similarity_autofit_worker.py, artwork_downloader.py, errors.py
Backend Analysis:    auralis-web/backend/analysis/           fingerprint_generator.py, fingerprint_queue.py
Backend Encoding:    auralis-web/backend/core/encoding/      wav_encoder.py (class-based `WAVEncoder`, raises `WAVEncoderError`) + atomic_io.py. SOLE implementation. A second, functional-style auralis-web/backend/encoding/ package existed until #5147; its encode_to_wav() had zero production callers and survived only to host `WAVEncoderError`, reached via a bare `from encoding.wav_encoder import ...` that resolved only because pytest.ini/uvicorn put auralis-web/backend on sys.path. Both the class and the package are gone — this is no longer a duplication hotspot, and there is no "legacy copy" to check.

Frontend:            auralis-web/frontend/src/               React 18 + TS + Vite + Redux + MUI
Frontend Components: auralis-web/frontend/src/components/
Frontend Hooks:      auralis-web/frontend/src/hooks/         api, app, audio, enhancement, fingerprint, library, player, shared, websocket
Frontend Contexts:   auralis-web/frontend/src/contexts/      ThemeContext.tsx, WebSocketContext.tsx, PlaybackSessionContext.tsx + playbackSessionContexts.ts (the single shared enhanced-audio streaming session) (WebSocketContext is globally auto-mocked by src/test/setup.ts — vi.unmock() to exercise the real one). There is NO EnhancementContext.
Frontend Store:      auralis-web/frontend/src/store/         slices/, selectors/, middleware/
Frontend Design:     auralis-web/frontend/src/design-system/ Design tokens (single source of truth)
Frontend Services:   auralis-web/frontend/src/services/      API clients + api/, audio/ subdirs (the fingerprint/ subdir went with FingerprintCache in #5215); payload mapping in src/api/transformers/
Frontend Types:      auralis-web/frontend/src/types/         api.ts, domain.ts, websocket.ts, ws/
Frontend Test Utils: auralis-web/frontend/src/test/          setup.ts, test-utils.tsx, mocks/; specs also live in src/__tests__/ and src/tests/

Rust DSP:            vendor/auralis-dsp/                     PyO3 module, 19 src/*.rs. Exposes 11 functions via py_bindings.rs: hpss, yin, chroma_cqt, detect_tempo, envelope_follow, compress, limit, compute_fingerprint, apply_multiband_eq, detect_onsets, process_chunks. rhythm.rs/tempo.rs/onset_detector.rs were ported in when the standalone fingerprint-server was deleted (#4533).
Desktop:             desktop/                                Electron wrapper
Scripts:             scripts/                                Dev/release tooling — check_pytest_baseline.py, check_doc_counts.py (structural counts in this file + CLAUDE.md), check_optimization_importers.py (#5142 gate), check_weak_assertions.py, validate_release_metadata.py, run_all_tests.py, development/
Tests:               tests/                                  ~6,759 test functions (611 files) across 18 dirs
Audit Reports:       docs/audits/                            Generated audit reports
Local Issue Cache:   .claude/issues/                         Issue snapshots (per audit-publish / fix-issue)
Specialist Agents:   .claude/agents/                         dsp, backend, frontend, library specialists
```

Counts above were re-derived from the live tree when this file was last updated. If a finding depends on an exact number, recompute it rather than quoting this table.

`CLAUDE.md`'s Codebase Map keeps its own independent copy of the analysis
file count, router count, test file/function counts, and docs topic-dir
count — the two are hand-maintained and drift apart if only one is edited.
Run `python scripts/check_doc_counts.py` to recompute both from the live
tree and update both files together (#4982).

## Retired Architecture — Do Not Report Against

Findings that assume any of the following describe code that no longer exists. Verify against the live tree before reporting; a "missing" piece here is intentional, not a bug.

| Retired | Replaced by | Notes |
|---------|-------------|-------|
| Categorical mastering branches — a classifier selecting a *quiet* / *dynamic_loud* / *compressed_loud* branch | A single continuous path: `auralis/core/mastering_branches/continuous.py` (`ContinuousMasteringBranch`), driven by `auralis/core/processing/continuous_space.py` | The branch classifier and its three per-category modules were deleted. Mastering parameters are now generated continuously from 3D `ProcessingCoordinates` (spectral_balance, dynamic_range, energy_level) derived from the 25D fingerprint. Do **not** report "missing branch classification", "no category dispatch", or a stage that fails to special-case a category. Discrete presets were deliberately replaced by continuous parameter generation. |
| Standalone `fingerprint-server` service | `vendor/auralis-dsp/` (in-process Rust) | Deleted in #4533; rhythm/tempo/onset code was ported into the PyO3 module. There is no separate server process, port, or HTTP hop to audit. |
| `EnhancementContext` (frontend) | `useEnhancementControl()` local state | Never existed as a context. See the Frontend Contexts row above. |
| Engine-side parallel chunk processing — *auralis/optimization/parallel_processor.py* and the *parallel/* package | Chunking happens in two live places instead: `auralis/core/mastering_chunk_loop.py` (engine, sequential with carried context) and `auralis-web/backend/core/chunked_processor.py` + `processor_pool.py` (backend, concurrent) | Deleted in #4565 as an unreachable cluster. Do **not** report "parallel processor missing crossfade / chunk copies / reassembly order" — audit the two live chunk paths instead. Only this cluster was dead: the rest of `auralis/optimization/` is live engine code reached from `auralis/core/hybrid_processor.py` at import time — see the Optimization row in the Project Layout table above, and audit it at full severity (#5142). |
| `LibraryManager` (*auralis/library/manager.py*) and the *auralis/library/caching/* cache layer | `LibraryDatabase` in `auralis/library/database.py` + `repositories/` | Deleted in #4915. #5162 then renamed the backend globals key to `library_database` and rewrote the present-tense docstrings, so the name no longer appears as a live identifier anywhere in production code — a grep for the old spelling now returns nothing outside `tests/` and the docs #5031 tracks. What remains are past-tense historical references in comments, not live constructions. The caching package was left behind as an empty stub and was removed in #5148; there is no caching layer under `auralis/library/` to look for. A finding that says "LibraryManager does X" is stale by construction; re-target it at `LibraryDatabase` or the relevant repository. |
| Legacy *auralis/core/config.py* dataclasses shadowed by the `auralis/core/config/` package | `auralis/core/config/` (UnifiedConfig, factory, settings, preset/genre profiles) | Deleted in #4918 — a package directory always shadows a same-named module file, so it had been dead for a long time. There is no "config duality" left to check; do not report parameters as defined in two places on this basis. |
| Discrete enhancement presets — *gentle*, *warm*, *bright*, *punchy*, *live* | `'adaptive'` only: `VALID_PRESETS` / `EnhancementPresetLiteral` in `auralis-web/backend/schemas/enhancement.py`, `EnhancementPreset` in `auralis-web/frontend/src/types/domain.ts` | **User directive, 2026-09-13** (`c195ac80` engine/backend, `ae9d28e3` frontend) — deleted from engine tables, API literals and UI, not hidden. Do **not** report "missing presets", a one-item preset control, or preset shortcut keys 2-5 doing nothing. **Do** report any surface that still accepts or emits a removed name, or a local preset mirror that disagrees with `VALID_PRESETS` (see the preset row in Sibling Detection). Two deliberate survivors: `auralis/core/analysis/spectrum_mapper/preset_anchors.py` holds content-calibration anchor points, not a user menu, and the Player component test keeps `'warm'` as a pass-through sentinel. |
| Boundary crossfade in the emitted chunk stream | Each chunk is rendered with context and trimmed to a non-overlapping `CHUNK_INTERVAL` segment (`auralis-web/backend/core/chunk_operations.py`, `auralis-web/backend/core/stream_chunk_ops.py`), so segments tile the timeline exactly | Removed across #2750, #3514 and #4642; `tests/backend/test_audio_stream_crossfade.py` pins it. `apply_crossfade_between_chunks` in `auralis-web/backend/core/chunk_crossfade.py` survives with **no production caller** — only a `noqa: F401` re-export from `chunked_processor.py`. Its curve is equal-**gain** sin²/cos² (#3878), not equal-power; do not "fix" it to bare sin/cos. Do **not** report "missing crossfade at chunk seams" — audit seams as tiling (no gap, no overlap, no repeated samples). `OVERLAP_DURATION` still exists because `content_chunk_count()` uses it for chunk-count geometry. |
| Modules deleted as unreachable: *core/stream_prefetch.py* and `_prefetch_next_track` (#3879), *auralis-web/backend/monitoring/* (#4766), *auralis/core/personal_preferences.py*, *auralis/learning/reference_analyzer.py* and *auralis/analysis/content_aware_analyzer.py* (#4592), *auralis/utils/preview_creator.py* (#4277), the *auralis/player/realtime_processor.py* shim (#4334), *auralis/dsp/realtime_adaptive_eq/* and *auralis/core/hybrid/realtime_manager.py* (#4873), frontend *src/performance/* (#4696), *services/fingerprint/FingerprintCache.ts* (#5215), and the in-memory PCM chunk cache *core/chunk_cache.py* (`SimpleChunkCache`, degraded-mode only; #5492) | Nothing — each had zero production callers | Deleted rather than wired up. Their absence is not a finding; a reappearance, or a new import of an old path, is. |

Corollary for the DSP/engine audits: regression tests now assert **continuous** invariants (monotonicity across the parameter space, no plateaus, smooth transitions) rather than per-category expected behavior. A test that no longer checks a category is up to date, not a coverage gap.

## Test Baselines — Use the Tracked Files, Not a Worktree Diff

Both suites carry a large pre-existing failure baseline, so a raw failure is **not** evidence of a regression. As of #4562 / #4640 the baselines are checked in and CI-enforced, which replaces the old "compare against a clean worktree" advice for most cases.

| Suite | Baseline | Check | CI |
|-------|----------|-------|-----|
| Frontend (vitest) | `auralis-web/frontend/test-baseline.json` — an explicit list of known-failing specs (108 entries as of `80a6266e`, 2026-08-26 — count the file, don't quote this) | `pnpm run test:ci` then `pnpm run test:baseline` | `.github/workflows/frontend-test.yml` |
| Backend (pytest) | `pytest-baseline.json` at the repo root — tracked, 157 `failures` entries as of `3e78c75d` (2026-09-03); first regenerated 2026-08-19 in `7c03249e` | `python scripts/check_pytest_baseline.py pytest-results.xml --strict-stale` | `.github/workflows/backend-tests.yml` |

Rules:
- **Read the baseline file before reporting any failing test.** If the spec is listed, it is known — do not file it.
- Both gates are *ratchets*: the baseline may shrink, never grow. A newly-failing test not in the baseline is a genuine regression and worth a finding.
- Regenerate rather than hand-edit: `pnpm run test:baseline:update`.
- CI **does** now run vitest and pytest. Any audit note claiming "no CI runs the tests" is out of date.
- `backend-tests.yml` is currently **red on every run**, and that is not the same as "the gate is broken" (#4974). The baseline file exists and the pytest step runs the selected suite; it is the *baseline-comparison* step that fails, on failures absent from the list — or, since #5091, on a baselined entry that now passes. Read that step, not the pytest step. Do **not** report "the backend gate has never worked / the baseline is missing" — that was true through 2026-07 and is not now. #5091 (69 entries whose tests now pass, silently re-permitted) is now CLOSED: `check_pytest_baseline.py --strict-stale` is wired into `backend-tests.yml` and fails the job on any stale entry, not just on new unlisted failures. Do not re-report "the ratchet can't detect stale entries" — it now can and does.
- A worktree comparison (`git worktree add`, **never** `git stash`) is still the fallback when a baseline file is missing or you need to attribute a failure to a specific commit.

## Severity Framework

See `_audit-severity.md` for the unified severity scale (CRITICAL / HIGH / MEDIUM / LOW), special-rule minimum-severity table, and decision tree.

## Methodology

- Be skeptical. Assume there are bugs even if the code "looks fine."
- For each claim, re-read the code path to confirm before including it.
- Prefer evidence from concrete code paths (call sites, data structures, configs) over assumptions.
- After making a finding, attempt to disprove it. Only include findings you cannot disprove.
- Pay special attention to audio integrity — sample-count mismatches cause audible artifacts.
- Trace audio data through the full pipeline: load → analyze → process → stream → playback.

## Audio/Python Context Rules

- **NumPy ownership**: Always check whether a function returns a view or a copy. `arr[:]` is a view; `arr.copy()` is a copy.
- **dtype propagation**: Trace dtype through every stage. A silent `float64` cast can mask a downstream bug.
- **GIL across PyO3**: Rust DSP must release the GIL during long compute or it serializes Python callers.
- **Lock ordering**: Player RLock → Library Session is the only safe order. Reverse it and you deadlock.
- **Async vs threads**: FastAPI handlers are `async def`; the DSP/player run on threads. `await` on a sync method is a bug.
- **WebSocket lifetime**: Connections survive backend reloads in `--dev` mode; treat reconnect as the common case.

## Context Management Rules

- **Max 1500 lines per Read** — use `offset` and `limit` to paginate larger files.
- **Grep before Read** — search for the specific pattern first, then read only relevant sections.
- **Incremental writes** — append findings to the report as you go; do not hold everything in memory.
- **One dimension at a time** — complete and write up one dimension before starting the next.

## Path-Reference Convention

Backticked file/dir paths in any `audit-*.md` skill (or this file) **must resolve against the live repository tree**. The validate gate at `.claude/commands/_audit-validate.sh` enforces this and is the structural fix for stale-path drift after refactors.

- Backticks = "this path exists right now". The gate fails the audit if it doesn't.
- Forward-looking refs (a file that doesn't yet exist) or backward-looking refs (a file that was deleted) **must not** use backticks — write them as plain text or italics.
- Trailing `:NN` or `:NN-NN` line ranges are stripped before existence check (line numbers may drift; the file must still exist).
- **Bare basenames are checked too** (e.g. `chunked_processor.py` with no directory). They resolve by basename against the tracked tree. This closed the hole that let long-deleted files (a `wav_streaming` router, a `self_tuner` service) sit in these skills unnoticed — shorthand goes stale exactly like a full path does.
- **Directory refs are checked inside `.claude/**`**: a backticked token ending in `/` (e.g. `auralis/library/repositories/`) must name a directory that still holds tracked files. Before this check existed, *animations/* and *auralis/library/caching/* survived in the specialist agents long after their deletion. The wider docs are not covered yet.
- Placeholder tokens containing `<` or `>` (per-finding format templates) are skipped.
- Run `.claude/commands/_audit-validate.sh` before committing edits to any audit skill.

**Two scopes (#5144).** The gate is red-by-default over the whole docs tree —
it found 310 stale refs the day #4984 widened it — so it is split into a strict
half and a ratchet half, and its exit code says which failed:

| Exit | Scope | Meaning |
|---|---|---|
| 0 | — | Strict clean, ratchet at or below baseline. |
| 1 | `.claude/**`, `CLAUDE.md`, `README.md`, `auralis-web/backend/WEBSOCKET_API.md`, `docs/architecture/`, `docs/subsystems/`, `docs/README.md` | A stale ref in the authoritative set. Always a regression. |
| 2 | the rest of the current `docs/` tree | A ref not in `.claude/commands/_audit-validate-baseline.txt`. Also a regression. |

`.github/workflows/path-references.yml` enforces both on every push and PR.
The baseline is a **shrink-only ratchet** like `pytest-baseline.json`: fix a
listed ref and regenerate with `_audit-validate.sh --update-baseline`, but
never use that flag to absorb a new failure. A docs file leaves the ratchet and
joins the strict list by being cleaned up and relisted in the script — that is
the intended direction of travel.

## Specialist Agents

For complex investigations, the orchestrator audits (`audit-engine`, `audit-backend`, `audit-frontend`, `audit-integration`) may delegate to specialists in `.claude/agents/`:

| Specialist | Domain |
|------------|--------|
| `dsp-specialist` | `auralis/core/`, `auralis/dsp/`, `vendor/auralis-dsp/`, signal flow, audio invariants |
| `backend-specialist` | `auralis-web/backend/` — routers, streaming, WebSocket, schemas |
| `frontend-specialist` | `auralis-web/frontend/` — components, hooks, Redux, design tokens |
| `library-specialist` | `auralis/library/` — 13 repositories (+ `BaseRepository`), migrations, SQLite, scanner |

Invoke via the **Agent** tool with `subagent_type: <name>` (the tool formerly called Task). Dimension/flow fan-out agents use `subagent_type: general-purpose`.

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels > /tmp/audit/issues.json`
2. Search for keywords from your finding in existing issue titles.
3. Scan `docs/audits/` for prior reports covering the same issue.
4. Scan `.claude/issues/` for local snapshots of prior fixes.
5. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip — do NOT re-report.
   - **CLOSED**: Verify the fix is still in place. If regressed, report as "Regression of #NNN".
6. If no match: Report as NEW.

## Sibling Detection

When a bug pattern exists, check ALL siblings before declaring scope. Common sibling groups in Auralis:

| Pattern | Where to grep |
|---------|---------------|
| DSP stage missing `.copy()` | All files under `auralis/dsp/` and `auralis/core/` (incl. `auralis/core/hybrid/`, `auralis/core/stages/`, `auralis/core/processors/`, `auralis/core/dsp/`, `auralis/core/processing/`) |
| Named mastering stage inconsistency | All 13 stages under `auralis/core/stages/` (air_enhancement, bass_enhancement, clarity_boost, harmonic_exciter, hf_budget, loudness_maximizer, mid_warmth, presence_enhancement, resonance_notches, safety_limiter, stereo_expansion, sub_bass_control, transient_shaper) — each must honor the same copy/sample-count/dtype contract |
| Discontinuity in continuous parameter space | `auralis/core/processing/continuous_space.py` and every consumer of `ProcessingCoordinates` — any clamp, plateau, or `if` threshold that reintroduces a categorical step |
| Repository raw SQL | All 13 repos under `auralis/library/repositories/` (each extends `BaseRepository` in `base.py`; also check `factory.py`) |
| Cache key missing an invalidation input | The three independent caches: `auralis-web/backend/core/chunk_cache_manager.py` + `auralis-web/backend/core/chunk_path_cache.py` (keyed via `auralis-web/backend/core/file_signature.py`), `auralis-web/backend/core/thumbnail_cache.py` (content-addressed on source mtime/size), `auralis-web/backend/cache/manager.py`, whose shared lifecycle boundary is `auralis-web/backend/core/cache_cleanup.py` (#5257). A key that omits mtime/size serves stale data after an edit; one that includes too much never evicts. |
| Router missing input validation | All 20 registered route handlers under `auralis-web/backend/routers/` (derive the live list from `auralis-web/backend/config/routes.py`, not from a hardcoded count) |
| Unvalidated filesystem path | Every call site that should route through `auralis-web/backend/security/path_security.py` |
| WebSocket message not idempotent | All handlers under `auralis-web/backend/ws_handlers/` |
| Chunk constant hardcoded | Any literal that bypasses `auralis-web/backend/core/chunk_boundaries.py` |
| Hook missing cleanup | All files under `auralis-web/frontend/src/hooks/` |
| Component > 300 lines | All files under `auralis-web/frontend/src/components/` |
| Service without lifecycle | All files under `auralis/services/` and `auralis-web/backend/services/` |
| Coordinator split into siblings that share its state | `auralis-web/backend/core/chunked_processor.py` + the `chunk_*` siblings, `auralis-web/backend/core/processing_engine.py` + the `job_*` siblings, `auralis-web/backend/core/audio_stream_controller.py` + `stream_chunk_ops.py` / `stream_fingerprint.py`, `auralis/player/enhanced_audio_player.py` + the `player_*_mixin.py` files. Each sibling takes the coordinator instance and reads/writes its attributes, so a lock or invariant fixed in the coordinator must be checked in every sibling. |
| Enhancement preset list mirrored instead of imported | `auralis-web/backend/schemas/enhancement.py` (`VALID_PRESETS`, the source), `auralis-web/backend/core/proactive_buffer.py` (`AVAILABLE_PRESETS`), `auralis-web/backend/websocket/outbound_messages.py`, `auralis-web/frontend/src/types/domain.ts`, `auralis-web/frontend/src/types/ws/enhancement.ts`, `auralis-web/frontend/src/store/slices/playerSlice.ts`, `auralis-web/frontend/src/hooks/player/usePlayerStateSync.ts`, `auralis-web/frontend/src/hooks/enhancement/useEnhancementControl.ts` — all must say `'adaptive'` only |
| Per-chunk work on the wrong executor | Every `asyncio.to_thread` / `run_in_executor` site in `auralis-web/backend/core/` — per-chunk DSP and chunk reads belong on `run_in_stream_executor` in `executors.py` (#5086); per-stream setup and repository calls belong on the default I/O pool. A hot-path call on plain `to_thread` queues behind library-scan work and trips `CHUNK_PROCESS_TIMEOUT` on queueing delay alone. |

Use a single `grep -rn <pattern> <dir>/` and report all siblings in the SAME finding (do not file N separate issues).

## Base Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: <audit area>
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet or exact call path demonstrating the issue
- **Impact**: What breaks, when, blast radius
- **Siblings**: Other locations with the same pattern (if any)
- **Related**: Links to related findings or issues
- **Suggested Fix**: Brief direction (1-3 sentences)
```

Specialized audit commands add extra fields (e.g., `Trigger Conditions`, `Flow`, `Changed File`) — see each command for details.

## Domain Labels

Severity: `critical`, `high`, `medium`, `low`
Domain: `audio-integrity`, `dsp`, `player`, `backend`, `frontend`, `library`, `security`, `concurrency`, `performance`, `websocket`, `streaming`, `fingerprint`, `deprecation`, `tech-debt`
Type: `bug`, `enhancement`, `maintenance`

## Report Finalization

1. Save your report to: `docs/audits/AUDIT_<TYPE>_<TODAY>.md` (YYYY-MM-DD format).
2. Do NOT create GitHub issues directly during the audit.
3. Inform the user the report is ready and suggest:
   ```
   /audit-publish docs/audits/AUDIT_<TYPE>_<TODAY>.md
   ```
