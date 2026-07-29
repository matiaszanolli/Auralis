# Technical Debt Audit — Auralis — 2026-07-29

**Scope**: accumulated technical debt across the Python engine, FastAPI backend, React frontend, test suite, and project documentation.
**Method**: 7 parallel dimension agents, findings merged post-hoc.
**Status**: MERGE COMPLETE — assembled from the 7 surviving dimension files after the coordinator crashed on an API 500. No new source analysis was performed during the merge; every finding below is carried forward verbatim from a dimension file.

---

## Methodology Note — Grep Baselines Inflate Debt (READ FIRST)

A prior audit-tooling review (2026-07-25) established that **tech-debt grep baselines systematically overstate the real problem**. Raw counts of TODO/FIXME markers, "duplicated" blocks, and magic numbers are inflated by:

- markers that are informational, not actionable;
- "duplication" that is coincidental structural similarity across unrelated domains;
- "magic numbers" that are locally obvious constants (array indices, `0`/`1`/`2`, sample-rate literals in tests).

Consequently, in this report:

- **Any count a dimension agent did not individually verify is labelled an UNVERIFIED GREP COUNT.** It is a search-hit tally, not confirmed debt.
- **A smaller verified list is more valuable than a large unverified one.** Findings below that carry file:line evidence and a stated verification procedure are the actionable output; bulk counts are context only.
- **Refutations are first-class results.** Where a dimension agent tested a seed hypothesis and found it FALSE, that correction is preserved and marked `REFUTED`. Several of this run's most valuable results are refutations of claims made by the audit tooling itself.

### Known-deliberate — explicitly NOT debt

The following were confirmed as intentional design decisions and must not be filed as debt:

- Single-user localhost Electron desktop app (no multi-user / remote / Docker scenarios).
- Rust `numpy-rs` pinned at 0.23 (deliberate; forward-compat via abi3 flag).
- `pytest` pinned `==9.0.1` (deliberate; newer pytest removes a hook signature `tests/conftest.py` needs).
- `filepath` deliberately never sent to clients (#3205).
- The engine-queue vs state-manager split (#4374).

---

## Executive Summary

**25 new findings** (0 CRITICAL, 0 HIGH, 9 MEDIUM, 16 LOW) across 6 of 7 dimensions — Dimension 1
(stale markers) found **zero genuine marker debt**, a clean result worth noting on its own since
marker-grep debt is usually assumed rather than verified. A further **5 candidate findings were
identified and correctly NOT double-counted**: 2 were independently re-derived by this audit but
already filed today by the backend audit (TD2-4/TD2-5, TD2-6), and 3 overlap existing tracked
issues and were either skipped or re-filed only with corrected evidence (TD3-2, TD3-3).

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 9 |
| LOW | 16 |
| **Total (new)** | **25** |

### The single biggest structural debt item

**TD2-3 — roughly 4,800 lines of the engine's "sophisticated" processing code are unreachable
from the shipped app.** This independently corroborates what three separate dimensions of this
session's engine audit already concluded from the other direction (18 of that audit's 40 findings
were on code with zero production callers): the 13-stage `stages/` pipeline, `optimization/parallel/`,
the `AdaptiveLimiter` chain, and `RecordingTypeDetector` do not ship — everything a user actually
hears goes through the simpler `ContinuousMode` chain instead. Two independent audits, using
different methods (call-graph tracing vs. dead-code sweep), landing on the same structural
conclusion is strong corroboration. This is a "decide, then either wire it up or delete it"
decision, not a bug to patch — see TD2-3's own write-up for the full inventory.

### The most valuable class of finding: tests that cannot fail

Dimension 6 (Test Hygiene) confirmed by *running* tests rather than trusting grep, and the
resulting findings are more serious than ordinary missing-coverage gaps: TD6-1 (8 regression
tests for closed HIGH #2076 have been erroring on a removed attribute since a July 19 commit),
TD6-2 (~53 backend API tests assert `status_code in [2xx, 5xx]`, unable to distinguish success
from a server crash), TD6-3 (3 "critical invariant" pagination tests are wired to a permanently-
empty fixture and can only ever skip), and TD6-5 (13 sites convert real crashes — including the
exact bug classes their own docstrings name — into silent `pytest.skip`). **Tests that cannot
fail are worse than absent tests: they actively certify broken code as working**, which is very
likely part of *why* several "closed" issues elsewhere in this session's audits turned out not to
have actually worked (see the backend and integration audits' repeated "regression of a closed
fix" findings).

### Doc rot in the audit tooling itself

Dimension 7 found that the audit skill files are themselves stale: `_audit-common.md` falsely
claims the backend pytest baseline is "checked in and CI-enforced" (TD7-1 — it never has been;
see the backend audit's BE9-01), and both `_audit-common.md` and `audit-backend.md` assert a
false "two live `WAVEncoderError` classes" duplication hazard that does not exist (TD7-2). Every
future audit that trusts these files inherits both errors until they are corrected.

### Methodology note

Per the mandatory grep-baseline-inflation warning (see top of this report), every finding above
carries individually-verified file:line evidence rather than a raw marker/duplication count.
Where a dimension refuted its own seed hypothesis (e.g. Dimension 6 confirming several failures
are loud `AttributeError`s rather than silent Mock-swallowed assertions), that refutation is
preserved in the dimension's own section rather than discarded — it is a first-class result.

---

## Dimension 1 — Stale Markers (TODO / FIXME / HACK / XXX)

**Auditor**: orchestrator (handled directly — this dimension is small enough not to warrant a subagent)
**Depth**: deep · **Limit**: none

## Result: ZERO genuine marker debt. No findings filed.

### Verification performed (not a grep-count claim)

1. **Strict marker sweep** — comment-anchored, case-insensitive, all four source languages:
   ```
   grep -RIniE '(#|//|/\*)\s*(todo|fixme|hack|xxx|tbd|wip)\b' \
        auralis auralis-web/backend auralis-web/frontend/src vendor/auralis-dsp/src
   ```
   → **0 hits.** Not 0-after-filtering; literally no comment in the tree opens with a deferred-work marker.

2. **Skill-prescribed baseline greps** (Phase 1 `baseline.txt`) independently return 0 for both
   Python and TS/TSX. The 2026-07-25 report recorded 1 (py) / 4 (ts) raw hits, all false positives
   (`spacingXXXLarge`, `migration_vXXX_to_vYYY.sql`). Those false positives are now gone too — the
   `spacingXXXLarge` token and the `vXXX` migration filename reference no longer match, so the raw
   count and the genuine count have converged at 0.

3. **Widened soft-marker sweep** — words that carry deferred-work intent without the conventional
   marker syntax (`TBD`, `WIP`, `placeholder`, `for now`, `temporar*`), 102 raw hits across all four
   languages. **Every hit was read in context.** Breakdown:
   - ~95 are literal domain vocabulary, not debt: temp-file lifecycle (`ffmpeg_loader.py`,
     `cache/adapter.py`, `processing_engine.py`), UI placeholder artwork/text
     (`MediaCardArtwork.tsx`, `SearchBar.tsx`, `EmptyState.styles.ts`), the `lufs=-100.0`
     placeholder-row sentinel documented in `fingerprint_stats_repository.py` and
     `fingerprint_scheduler_repository.py`, and HTTP 503 "temporarily unavailable" prose.
   - 3 are genuine deferred work but are **already tracked OPEN**, so they are suppressed per the
     dedup protocol rather than re-filed:
     - `auralis/library/scanner/scanner.py:375-382` — `_update_library_stats()` is a reachable
       no-op whose body is `# This would update the LibraryStats table / # For now, just log`
       → **Existing: #4243**.
     - `auralis-web/frontend/src/hooks/fingerprint/useFingerprintCache.ts:102-125` — "For now,
       we'll simulate the worker in the main thread" → **Existing: #4239**.
     - `auralis/library/sidecar_manager.py:140-141` — "Optionally verify checksum (expensive) /
       For now, size + mtime is sufficient" — this is a *documented deliberate trade-off* with a
       stated rationale, not a deferred task. Not filed.
   - 1 borderline: `ArtistHeader.tsx:81` `{/* Additional context - currently placeholder, can be
     expanded with backend data */}` renders the literal string `Artist` under the artist name.
     Cosmetic, self-documenting, zero change-cost amplification. Not filed (would be noise).

### Interpretation — why this metric is now dead

The marker count has been 0 for two consecutive audits. It is no longer a useful debt proxy for this
repo: deferred work here surfaces as *unwired code* (see Dim 2) and *tests that cannot fail* (see
Dim 6), not as annotated comments. Future tech-debt audits should keep the sweep (it is cheap) but
should not treat a zero as evidence of low debt — the 2026-07-29 suite found the largest structural
debt item in the codebase (an entire unreachable engine pipeline) in code carrying **no markers at
all**.

Recommendation for the skill: Dimension 1 should be demoted to a Phase-1 baseline check rather than
a full dimension agent, and the freed budget moved to Dim 2 / Dim 6.

## Dimension 2 — Dead Code & Unused Surface

Project root: /mnt/data/src/matchering. HEAD 09004fa2. Status: COMPLETE.

**Findings filed as NEW/Existing**: TD2-1 through TD2-8 (8 entries; TD2-4/5/6 are explicit dedup notes rather than new findings — see each). No CRITICAL/HIGH — all LOW per the tech-debt default, none met a promotion trigger.

---

### TD2-1: `auralis-web/backend/monitoring/` package (946 LOC) is entirely unwired — zero production importers
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/backend/monitoring/memory_monitor.py:1-361`, `auralis-web/backend/monitoring/metrics_collector.py:1-575`, `auralis-web/backend/monitoring/__init__.py:1-10`
- **Status**: NEW
- **Age**: `metrics_collector.py` last touched 2026-07-14 (`13e821ca`); `memory_monitor.py` last touched 2026-02-21 (`8a8bd5a4`)
- **Effort**: medium (decide keep-and-wire vs delete; either way touches startup wiring or a clean deletion + test removal)
- **Description**: The package defines `MemoryPressureMonitor` + `DegradationManager` (`memory_monitor.py`) and `MetricsCollector` + `HealthChecker` + `PerformanceMetrics` (`metrics_collector.py`) — a full memory-pressure-driven quality-degradation system and a metrics/health-check collector. Neither class is imported anywhere in `auralis-web/backend/` outside the package itself. This is attribution-carried from a lead surfaced in the same audit suite (engine/backend dimensions today); independently re-verified below.
- **Evidence**:
  - `grep -rn "MemoryPressureMonitor\|DegradationManager\|MetricsCollector\|HealthChecker\|PerformanceMetrics" --include="*.py" /mnt/data/src/matchering` → only definitions inside `monitoring/*.py`, plus one test file (`tests/backend/test_memory_monitor.py:20: from monitoring.memory_monitor import DegradationManager, MemoryPressureMonitor, MemoryStatus`).
  - `auralis-web/backend/config/startup.py`, `config/app.py`, `config/background_workers.py`, and every file under `routers/` were grepped for `monitor`/`Metrics`/`Degradation` — zero hits.
  - A superficially similar hit, `auralis-web/backend/cache/__init__.py:35 from .monitoring import (CacheAlert, CacheMetrics, CacheMonitor, HealthStatus)`, is a **different, unrelated module** — `auralis-web/backend/cache/monitoring.py` (cache-tier alerting), a sibling package that happens to share the name `monitoring`. It is live (imported by `cache/__init__.py`, consumed by `tests/backend/test_cache_integration_b2.py`) and must not be confused with the dead top-level `monitoring/` package. This distinction is easy to get wrong on a plain grep for the string "monitoring" — worth flagging explicitly since it's the kind of false-positive the methodology warning calls out.
  - `metrics_collector.py` (575 LOC, more than half the package) has **zero** test references anywhere in `tests/` — not even a unit test exercises it.
  - `memory_monitor.py` is referenced only by its own dedicated test (`tests/backend/test_memory_monitor.py`, 408 lines, heavily mocked) and by an unrelated same-named pytest fixture in `tests/stress/conftest.py:25` (`memory_monitor()` fixture — just a `psutil.Process()` wrapper, not an import of this module; confirmed by reading it).
- **Impact**: The app ships with no runtime memory-pressure degradation and no metrics collection despite having fully built, unit-tested-looking code for both — a maintainer skimming `tests/backend/test_memory_monitor.py` passing green would reasonably assume the feature is live. 946 LOC of surface area to keep in sync (or accidentally import and get surprised it's inert) for zero runtime benefit today.
- **Siblings**: None — this is the only backend package where the entire directory is production-orphaned; other dead-code findings in this audit are function/class-level, not whole-package.
- **Related**: Cross-referenced in `docs/audits/AUDIT_ENGINE_2026-07-29.md` / `AUDIT_BACKEND_2026-07-29.md` per today's suite (lead attribution) — re-verified independently here, not lifted.
- **Suggested Fix**: Either wire `MemoryPressureMonitor`/`DegradationManager` into `config/background_workers.py` (a background task polling memory and degrading chunk quality, matching the docstring's intent) and `MetricsCollector`/`HealthChecker` into a `/system` health route, or delete the package plus `tests/backend/test_memory_monitor.py` if the feature is not planned. Given CLAUDE.md's desktop/localhost-only framing, a lightweight wire-in (single background task) is probably lower effort than maintaining dead code.

---

### TD2-2: `auralis/dsp/stages.py::main()` — re-exported as `auralis.dsp.main`, zero real callers; its one "test" never actually imports it
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/dsp/stages.py:27-` (`main()`, the whole file's only function); re-export at `auralis/dsp/__init__.py:13` (`from .stages import main`)
- **Status**: NEW (checked #4592 first per instructions — that issue covers 4 *different* modules: `auralis/learning/reference_analyzer.py`, `auralis/core/personal_preferences.py`, `auralis/analysis/parallel_spectrum_analyzer.py`, `auralis/analysis/content_aware_analyzer.py`. `auralis/dsp/stages.py` is not among them, so this is not covered by #4592.)
- **Age**: `2ff696c9` 2026-02-13 (last touch, `git log --follow`)
- **Effort**: small (delete the file + its `__init__.py` re-export + the dead test method)
- **Description**: `auralis/dsp/stages.py` is a "Matchering 2.0"-lineage reference-matching pipeline (LUFS matching, RMS matching, spectral preservation, soft clipping) exposed as the sole export of the `auralis.dsp` package (`auralis/dsp/__init__.py:13, __all__ = ["main"]`). It is a **name collision with the unrelated, actually-13-stage `auralis/core/stages/` package** audited separately in this suite's engine dimension — grepping for "stages" without disambiguating hits both. No production code calls `auralis.dsp.main` or imports `auralis.dsp.stages` directly.
- **Evidence**:
  - `grep -rn "from auralis\.dsp import main\|dsp\.main(\|from \.\.dsp import main\|from \.dsp import main"` across `auralis/`, `auralis-web/`, `desktop/`, `scripts/`, `tests/` → **zero hits**. All `import main` hits found by a broader grep are the unrelated `auralis-web/backend/main.py` FastAPI entry point imported by test files (`test_system_api.py`, `test_files_api.py`, etc.) — a name coincidence, not a caller of this module.
  - The lead's cited "sole reference," `tests/auralis/core/test_core.py:365-374` (`test_dsp_stages_functionality`), does `from auralis.dsp.stages import (MasteringStage, PreprocessingStage, ProcessingStage)` inside a `try/except ImportError: pytest.skip(...)` block. **None of those three names exist in `stages.py`** (`grep -n "class \|^def " auralis/dsp/stages.py` shows only `def main`). This test therefore `ImportError`s and unconditionally skips on every run — it does not exercise `main()` at all, and never has. So the module's reachability is not merely "one test importer," it is **zero successful imports anywhere**, ever.
- **Impact**: Dead reference-matching implementation (soft-clip, LUFS/RMS matching) sits behind the `auralis.dsp` package's only re-export, misleading anyone who does `from auralis.dsp import main` expecting it to be the pipeline entry point CLAUDE.md's codebase map describes it as ("`dsp/stages.py` DSP pipeline entry (main())") — that comment is itself now stale documentation (cross-ref Dim 7).
- **Siblings**: None — distinct from `auralis/core/stages/` (13-stage pipeline, covered in the engine audit / TD2-3 below).
- **Related**: Distinct from `#4592` (verified above, does not cover this file). Cross-ref Dim 7 for the stale CLAUDE.md description of `dsp/stages.py` as "the" pipeline entry.
- **Suggested Fix**: Delete `auralis/dsp/stages.py`, its `__init__.py` re-export, and the dead `test_dsp_stages_functionality` test method (it has been silently skipping, not passing). If loudness/RMS/spectral reference-matching is still wanted as a standalone dev tool, it belongs alongside `auto_master.py` at the root, not exported as the `auralis.dsp` package's public API.

---

### TD2-3: THE BIG ONE — ~4,800 LOC of the "sophisticated" engine is unreachable from the shipped app; full inventory + live-path proof
- **Severity**: LOW (per tech-debt severity guidance — this is a reachability/structure finding, not a correctness bug; the engine audit already covers the correctness angle for the same clusters)
- **Dimension**: Dead Code & Unused Surface
- **Location**: see inventory table below
- **Status**: Partially NEW, partially `Existing: #4565` (see table) — this finding's contribution is the **consolidated cross-cluster inventory and independently re-verified call graph**, not a new discovery of any single cluster (all four clusters were surfaced by `docs/audits/AUDIT_ENGINE_2026-07-29.md` ENG-D2-3 / ENG-D5-2 / ENG-D5-3 / ENG-D6-4, attributed per the task brief). I re-traced every edge myself rather than citing the engine report; see Evidence.
- **Age**: N/A (structural, accreted across many commits — see per-cluster `Related` issue history in the engine audit)
- **Effort**: large (architectural decision required before any deletion — see Suggested Fix)
- **Description**: I independently traced the actual live audio path from the shipped backend entry point to the DSP primitives, and independently re-verified (fresh greps, not copied from the engine report) which engine modules sit on it. The result matches the engine audit's conclusion: a simpler, 5-stage `ContinuousMode` chain is what every user-audible byte goes through; four substantial, well-engineered subsystems sit completely off that path with no other production caller.

**Live path (verified today, HEAD `09004fa2`)**:
```
auralis-web/backend/core/audio_processing_pipeline.py:199/221/228  processor.process(audio)
  → auralis/core/hybrid_processor.py:214 HybridProcessor.process()
    → :286 self._process_adaptive_mode(target_audio, results)      [use_continuous_space defaults True, unified_config.py:154]
      → :336-338 self.continuous_mode.process(target_audio, self.eq_processor, fixed_params=fixed_params)
        → auralis/core/processing/continuous_mode.py                 ContinuousMode: input gain → 5-shelf psychoacoustic EQ
                                                                       (WOLA via dsp/eq/psychoacoustic_eq.py:318 process_realtime_chunk)
                                                                       → broadband compression/expansion (processing/base/compression_expansion.py)
                                                                       → stereo width (processing/base/stereo_width_processor.py)
                                                                       → normalization
    → :360-364 processed = self.brick_wall_limiter.process(processed)   [dsp/dynamics/brick_wall_limiter.py via create_brick_wall_limiter]
```
None of the four clusters below appear anywhere in that call chain.

**Inventory (module/cluster → LOC → sole callers → verdict)**:

| Cluster | Files | LOC | Sole non-test caller(s) | Verdict |
|---|---|---:|---|---|
| 13-stage mastering pipeline | `auralis/core/stages/*.py` (13 files) | 1,173 | `auralis/core/simple_mastering.py:24,37` (`from .stages import ...`) only | **DEAD** on shipped path |
| `SimpleMasteringPipeline` chain | `simple_mastering.py` 355, `mastering_process_chunk.py` 160, `mastering_chunk_loop.py` 235, `mastering_prepare.py` 232, `mastering_branches/{base,continuous,__init__,soft_clip_params}.py` 430, `mastering_config.py` 491, `mastering_diagnostics.py` 125, `mastering_notch_context.py` 142 | 2,170 | root-level `auto_master.py` only (`from auralis.core.simple_mastering import (...)`) — a standalone dev/offline CLI script, not wired into `auralis-web/backend/`, any router, `desktop/`'s Electron main, or any `package.json` script (verified: `grep -rln "auto_master" desktop/ auralis-web/frontend/package.json` → 0 hits) | **DEAD** on shipped path |
| Realtime `AdaptiveLimiter` chain | `auralis/dsp/dynamics/limiter.py` (`AdaptiveLimiter`, whole file) 277, `auralis/dsp/realtime_adaptive_eq/*.py` 657, `auralis/core/processing/realtime_dsp_pipeline.py` 90 | 1,024 | `HybridProcessor.process_realtime_chunk()` (`hybrid_processor.py:400`) is the only caller of `RealtimeDSPPipeline.process_chunk`, which is the only caller of `DynamicsProcessor.process()` (→ `AdaptiveLimiter`) and `RealtimeAdaptiveEQ`. `process_realtime_chunk` itself has **zero callers** outside tests (`grep -rn "process_realtime_chunk\b" auralis auralis-web desktop` → only the definition + a docstring in `realtime_eq.py:118` that says outright *"process_realtime_chunk is called from tests only. Real playback..."*). Not to be confused with the *different, live* `PsychoacousticEQ.process_realtime_chunk` (`dsp/eq/psychoacoustic_eq.py:318`), called from the live WOLA path in `eq_processor.py:212` — same method name, unrelated class, easy to conflate on a plain grep. | **DEAD** on shipped path |
| `RecordingTypeDetector` | `auralis/core/recording_type_detector.py` (whole module) | 476 | Three standalone offline scripts only: `scripts/update_profile.py`, `scripts/rate_track.py`, `scripts/analyze_feedback.py` — not imported by `HybridProcessor`, `ContinuousMode`, or any router | **DEAD** on shipped path (consistent with the retired-categorical architecture per `_audit-common.md` — this module predates the continuous-space rewrite) |
| `auralis/optimization/parallel/` package + shim | `parallel/{audio_processor,band_processor,fft_processor,feature_extractor,decorators,config,__init__}.py` 781, `optimization/parallel_processor.py` (compat shim) 37 | 818 | **Existing: #4565** (OPEN) — already tracked with the same conclusion; re-verified here (unchanged since #4565 was filed) only to complete the cross-cluster total, not re-filed | **DEAD**, already tracked |
| **Total newly-inventoried dead surface (excl. #4565)** | | **4,843** | | ~8.8% of `auralis/`'s 54,995 LOC |
| **Grand total incl. #4565's already-tracked 818** | | **5,661** | | ~10.3% of `auralis/` |

- **Evidence**: Every "sole caller" cell above was produced by a fresh `grep -rn` run today against `auralis/`, `auralis-web/`, `desktop/`, `scripts/`, and `auto_master.py` (not copied from the engine report), specifically:
  - `grep -rn "from \.stages import\|from \.\.core\.stages import\|from auralis\.core\.stages import" auralis auralis-web desktop scripts auto_master.py` → only `auralis/core/simple_mastering.py:24,37`.
  - `grep -rn "from \.mastering_branches\|mastering_branches import" ...` → only `auralis/core/mastering_process_chunk.py:25`.
  - `grep -rln "SimpleMasteringPipeline\|create_simple_mastering_pipeline\|simple_mastering" .` → the internal chain + `auto_master.py` + test files only; `mastering_config.py`/`mastering_diagnostics.py`/`mastering_notch_context.py` only *mention* `SimpleMasteringPipeline` in docstrings (verified by reading each), all three exist purely to serve the dead chain (extracted from `simple_mastering.py` per #4072).
  - `grep -rn "process_realtime_chunk\b" auralis auralis-web desktop` → definitions + docstrings only, no call site.
  - `self.dynamics_processor.settings.enable_limiter = False` (`hybrid_processor.py:99`) confirms even the shared `DynamicsProcessor` instance used elsewhere by `DynamicsManager` (`get_info`/`set_mode`/`reset` accessors only — never `.process()`) has its limiter branch explicitly disabled; the only code path that calls `DynamicsProcessor.process()` at all is `RealtimeDSPPipeline.process_chunk:80`.
  - `grep -rln "RecordingTypeDetector\|recording_type_detector" auralis auralis-web desktop scripts` → the 3 scripts above, nothing else.
  - Confirmed `auralis/player/` (the real-time playback path, separate from the offline mastering path) does not import `core.stages`, `mastering_branches`, or `simple_mastering` at all (`grep -rln ... auralis/player` → 0 hits); its own real-time mastering (`auralis/player/realtime/auto_master.py` — an `AutoMasterProcessor`, a same-named but *different* file from the root `auto_master.py` script) uses `dsp/dynamics/AdaptiveCompressor` + `LowMidTransientEnhancer` directly, a third independent implementation.
- **Impact**: Nearly 5,700 LOC — nine module-equivalents by the project's own <300-line rule — carries real engineering history (sub-bass parallel mixing, per-band EQ mapping, resonance-notch Nyquist clamping, oversample/downsample limiting, categorical recording-type classification) that a user of the shipped Electron app can never hear or trigger. Every future DSP audit, `mypy` pass, or contributor reading `auralis/core/` has to first figure out which quarter of the package is real before reasoning about behavior — that classification cost is the debt. It also means the project's own severity/effort estimates for bugs found inside these clusters (by other dimensions today) need the "no production caller" caveat to avoid over-prioritizing fixes to code nothing runs.
- **Siblings**: None beyond what's tabulated — this finding intentionally consolidates all four clusters rather than filing them separately, per the task's instruction to produce one inventory.
- **Related**: `docs/audits/AUDIT_ENGINE_2026-07-29.md` ENG-D2-3 (stages/mastering chain), ENG-D5-2/ENG-D5-3 (optimization/parallel, `Existing: #4565`), ENG-D1-4/5/6 (AdaptiveLimiter reachability caveats), ENG-D6-4 (RecordingTypeDetector). Also related but out of scope for this table per the lead's framing: ENG-D7-3 (`QueueTemplateRepository`, a library-layer instance of the same "built, wired into its factory, zero callers" pattern) and ENG-D6-3 (`ParallelSpectrumAnalyzer`, tracked under `#4592`).
- **Suggested Fix**: This is one architectural decision, not four separate fixes — the engine audit's own prioritized fix order (item 8) says the same thing and I agree after independent verification: for each cluster, either (a) wire it into the shipped path if the richer processing is meant to reach users (e.g., replace `ContinuousMode`'s 5-stage chain with the 13-stage `stages/` pipeline, or enable `process_realtime_chunk` for actual low-latency streaming), or (b) delete it and, if the offline/CLI use case (`auto_master.py`, `scripts/*.py`) is still wanted, keep only the minimal subset those scripts need and drop the rest. Doing this once, top-down, is cheaper than the current state where three independent dimensions (this audit, `AUDIT_ENGINE_2026-07-29.md`, and by extension any future correctness audit) keep re-discovering the same unreachable 4,800 LOC and re-deriving its severity caveats from scratch.

---

### TD2-4 / TD2-5: Orphan `schemas.py` models + duplicate `PaginationParams` — independently re-derived, already filed today by the backend audit; not re-reported
- **Status**: **Not filed as new findings — dedup match.** I independently investigated both leads (12+ orphan Pydantic models in `schemas.py` including the `CacheStatsResponse` shadowing, and the two disagreeing `PaginationParams` classes) using fresh greps and got results that match `docs/audits/AUDIT_BACKEND_2026-07-29.md` almost line-for-line:
  - **Orphan `schemas.py` models** → `Related: AUDIT_BACKEND_2026-07-29 BE5B-N1` ("15 Pydantic models in `schemas.py` are orphans — including a typed cache-stats family that the live cache router shadows with an untyped local copy", Status: NEW). My independent count landed at 12 orphans + the separately-tracked `Existing: #3891` cache-stats family (4 models) = 16, one more than BE5B-N1's 15 — the difference is `PaginationParams`, which BE5B-N1 folds into its own count of 15 while I split it out into the `PaginationParams`-specific finding below; the underlying evidence set is otherwise identical (same 12 class names, same `WebSocketMessageType`/`WeightedProfileResponse` correctly-excluded false positives would apply). BE5B-N1's "Schema Consistency" framing already recommends deletion, so the debt framing here adds nothing new.
  - **Duplicate `PaginationParams`** → `Related: AUDIT_BACKEND_2026-07-29 BE5B-N2` ("Two live classes named `PaginationParams` disagree about the maximum page size (500 vs 200), and neither is what the routes enforce", Status: NEW). Identical root cause and identical two locations (`schemas.py:265-269`, `routers/pagination.py:95-121`). My own sweep additionally found the inline `Query(..., le=N)` bound varies more widely than BE5B-N2's single cited example (`playlists.py:91-92`, `le=200`) — I found `le=100` (`player.py:535`, `similarity.py:109`), `le=1000` (`processing_api.py:388`), and `le=10000` (`fingerprint_queue.py:136`) alongside the more common `le=200` (`albums.py:45`, `artists.py:116`, `tracks.py:41,73`). This is a marginal widening of scope, not a different finding — noted as an addendum to BE5B-N2 rather than re-filed.
- **Suggested Fix**: See BE5B-N1 / BE5B-N2 in `AUDIT_BACKEND_2026-07-29.md` for the full fix direction (delete the dead classes; for the cache family, verify field-for-field against `StreamlinedCacheManager.get_stats()` before pointing the router at the typed model). If BE5B-N2 is actioned, also normalize the wider `le=` inconsistency noted above (100/200/1000/10000) rather than stopping at the one router it cites.

---

### TD2-6: Frontend orphan contracts (`AlbumDetailApiResponse`, `CacheAwareAPIClient.getChunk()`) — independently re-derived, already filed today; not re-reported
- **Status**: **Not filed as new findings — dedup match.** Both pieces of this lead were independently re-verified and match findings already filed today in this same suite:
  - **`AlbumDetailApiResponse`** (`auralis-web/frontend/src/api/transformers/types.ts:145-147`, `export interface AlbumDetailApiResponse extends AlbumApiResponse { tracks: TrackApiResponse[] }`) — confirmed zero references anywhere in `auralis-web/frontend/src` outside its own declaration (`grep -rn "AlbumDetailApiResponse" auralis-web/frontend/src` → 1 hit, the definition), unlike its sibling `PlaylistDetailApiResponse` which has a real consumer (`playlistTransformer.ts:43 transformPlaylistDetail`). Confirmed the backend never returns this combined shape: `GET /api/albums/{album_id}` (`routers/albums.py:89`, via `serialize_album_detail`) and `GET /api/albums/{album_id}/tracks` (`routers/albums.py:118`) are two separate calls, never merged into one `{...album, tracks}` payload. → `Related: AUDIT_FRONTEND_2026-07-29 T4-02` and `AUDIT_BACKEND_2026-07-29 BE5-N3`, both Status NEW, both already recommend deletion. The correctness framing (T4-02 additionally shows the type has *also* drifted to the wrong case convention — snake_case vs the real camelCase payload) is strictly more complete than a debt-only "it's unused" framing, so nothing to add.
  - **`CacheAwareAPIClient.getChunk()` / `cache/endpoints.py`** — confirmed `auralis-web/backend/cache/endpoints.py` (344 lines) defines `CacheAwareEndpoint`/`create_cache_aware_handler`/etc. but contains **zero** `@router.` decorators or `APIRouter()` instantiation (`grep -n "@router\.\|APIRouter(" cache/endpoints.py` → no hits) — it mounts no route at all despite living in a `routers`-adjacent-looking location; its only importer is `cache/__init__.py`'s re-export, itself not consumed by `config/routes.py` or any router. On the frontend, `CacheAwareAPIClient.getChunk()` (`services/api/standardizedAPIClient.ts:419`) has exactly one caller anywhere: its own test (`standardizedAPIClient.test.ts:412`). → `Related: AUDIT_BACKEND_2026-07-29 BE1-7` and `BE5B-N7` (merged finding), both Status NEW, already proposing to delete both sides of the contract together.
- **Suggested Fix**: See `AUDIT_FRONTEND_2026-07-29.md` T4-02, `AUDIT_BACKEND_2026-07-29.md` BE5-N3 / BE1-7 / BE5B-N7 for the full fix direction.

---

### TD2-7: 2 newly-stale `# type: ignore` comments (mypy `--warn-unused-ignores`) beyond the already-tracked one
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis/dsp/dynamics/vectorized_envelope.py:145` (`@jit(nopython=True, cache=True)  # type: ignore[untyped-decorator]`), `auralis/analysis/dynamic_range.py:146` (`return max(0.0, dr_value)  # type: ignore[return-value]  # DR cannot be negative`)
- **Status**: NEW for these two. A third hit, `auralis/analysis/mastering_profile.py:26` (`import yaml  # type: ignore[import-untyped]`), is **`Existing: #4397`** (OPEN, filed as "the only unused ignore" at the time) — not re-filed.
- **Age**: not individually determined; the baseline (84 `type: ignore` sites repo-wide) is unchanged since `/tmp/audit/tech-debt/baseline.txt` was captured today, and the project memory notes the prior audit (2026-07-25) found only 1 stale ignore, consistent with these two being newly stale rather than a pre-existing miss.
- **Effort**: trivial (delete the two comments; verify `mypy` stays clean without them)
- **Description**: Ran `mypy --warn-unused-ignores --ignore-missing-imports` (as `CLAUDE.md` documents) against all 38 files in the tree containing a `type: ignore` comment. It reported exactly 3 `[unused-ignore]` hits. One (`mastering_profile.py:26`) is already tracked by `#4397`. The other two are new:
  - `vectorized_envelope.py:145` — the `@jit(nopython=True, cache=True)` decorator no longer needs `# type: ignore[untyped-decorator]`; numba's installed stub/typeshed must have picked up a typed decorator signature since this was added.
  - `dynamic_range.py:146` — `# type: ignore[return-value]` on a `max(0.0, dr_value)` return is now redundant; the surrounding type annotations already make this a valid `float` return without suppression.
- **Evidence**: `timeout 150 mypy --warn-unused-ignores --ignore-missing-imports <38 files with "type: ignore">` → `vectorized_envelope.py:145: error: Unused "type: ignore" comment [unused-ignore]`, `mastering_profile.py:26: error: ...` (Existing #4397), `dynamic_range.py:146: error: ...`. Only 3 of 84 total `type: ignore` sites are stale — consistent with the methodology warning that raw counts overstate debt; the other 81 remain load-bearing.
- **Impact**: Trivial — a stale suppression comment invites a future contributor to assume a type error is intentionally silenced when mypy would pass without it.
- **Siblings**: None beyond the third (#4397) already tracked.
- **Related**: `Existing: #4397` (the third stale ignore, `mastering_profile.py:26`, already filed).
- **Suggested Fix**: Delete both comments; re-run `mypy --ignore-missing-imports` on the two files to confirm no new errors surface without the suppression.

---

### TD2-8: 6 unused imports (ruff F401) — one overlapping a partially-stale open issue
- **Severity**: LOW
- **Dimension**: Dead Code & Unused Surface
- **Location**: `auralis-web/backend/config/startup.py:286` (`SettingsRepository`), `:288` (`LibraryScanner`); `auralis-web/backend/core/chunked_processor.py:49` (`apply_crossfade_between_chunks`); `auralis-web/backend/services/queue_service.py:16` (`TrackInfo`); `auralis/analysis/fingerprint/windowed_compute.py:126` (`os`, inside a function-local `import tempfile, os`); `auralis/io/unified_loader.py:24` (`check_ffmpeg`)
- **Status**: Mostly NEW. `startup.py`'s `LibraryScanner` import is **`Existing: #4012`** (OPEN, "asyncio and LibraryScanner unused imports in config/startup.py") — still an accurate description of that one import, though the line number has drifted (84 → 288, the file has grown) and the *other* half of #4012 (`import asyncio` at line 17) is now **stale/resolved**: `asyncio.Task[Any]` type annotations at `startup.py:171,194` now use it, so ruff correctly does not flag it. `SettingsRepository` at the adjacent line 286 is a new, second unused import in the same probe-import block, not covered by #4012's text.
- **Age**: not individually determined
- **Effort**: trivial (all 6 are `ruff --fix`-eligible mechanical deletions)
- **Description**: `ruff check --select F401,F811 auralis auralis-web/backend` (run via a pyenv-managed interpreter with ruff installed, since the project `.venv` doesn't carry ruff/vulture — flagged for completeness, not a repo problem) returned exactly 6 unused-import findings, no F811 redefinitions. One notable case: `chunked_processor.py:49`'s `from core.chunk_crossfade import apply_crossfade_between_chunks` is a deliberate backward-compat re-export per its own comment ("re-exported so existing imports keep working", #4245) — but unused *within* `chunked_processor.py` itself, so ruff flags it correctly; whether anything still imports it *from* `chunked_processor` (rather than from `chunk_crossfade` directly) wasn't verified here and would determine whether it's safe to delete outright or must stay as the compat shim it claims to be. This same file/function name also appears in `Existing: #3879` ("`_prefetch_next_track`, `_process_chunk_with_hybrid_processor`, ... `apply_crossfade_between_chunks` module-level — all dead code", OPEN) — spot-checking that issue's other two named symbols (`_process_chunk_with_hybrid_processor`, `next_track_prefetched`) found **neither exists in the current tree anymore** (they've since been removed/refactored away), so #3879 is now partially stale and worth a re-triage rather than trusting it as-is; not independently re-verified further here as it falls outside this consolidated finding's scope.
- **Evidence**: `PYENV_VERSION=3.11.11 pyenv exec ruff check --select F401,F811 --no-cache auralis auralis-web/backend` → 6 errors, all F401, locations as listed above (verbatim ruff output retained in the audit working notes).
- **Impact**: Negligible runtime cost; each is a small readability/onboarding tax (an unused import implies a dependency or code path that isn't actually there).
- **Siblings**: None beyond what's listed — this is the single consolidated unused-import finding per the audit's guidance to avoid a long tail of near-identical entries.
- **Related**: `Existing: #4012` (partially stale — see Description). `Existing: #3879` (partially stale — 2 of its 3 named dead-code symbols no longer exist in the tree; flagging for re-triage, not re-verifying in full here since it's tangential to this consolidated import-focused finding).
- **Suggested Fix**: Delete all 6 unused imports (`ruff check --select F401,F811 --fix` handles this mechanically); separately, re-triage `#3879` since two of its three cited symbols appear to have already been removed.

---

## Dimension 3 — Logic Duplication

(in progress)

## Preliminary: WAV encoder doc-rot resolution (target group 1)

`_audit-common.md`'s claim of "two live `WAVEncoderError` classes" is **FALSE as of HEAD (09004fa2)**.
`grep -rn "class WAVEncoderError"` across `auralis-web/backend/` returns exactly **one** hit:
`auralis-web/backend/encoding/wav_encoder.py:31`. `auralis-web/backend/core/encoding/wav_encoder.py`
defines a `WAVEncoder` *class* (no relation, different name) that raises plain `ValueError`/`OSError`,
not a `WAVEncoderError`. This is doc-rot — noted for Dim 7, not filed here.

However, reading both files in full surfaced a **real, distinct duplication** one level down: see TD3-1.

---

### TD3-1: Two independent "encode-WAV-and-atomically-save-a-chunk" pipelines in `chunked_processor.py`, one missing the finite-audio guard the other has

- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/core/chunked_processor.py:569-586` (in `process_chunk()`) vs `auralis-web/backend/core/chunked_processor.py:712,783-791` (in `get_wav_chunk_path()`); guard source: `auralis-web/backend/core/encoding/wav_encoder.py:126-134` (`WAVEncoder.encode_and_save`) vs `auralis-web/backend/encoding/wav_encoder.py:35-80` (`encode_to_wav`)
- **Status**: NEW
- **Age**: guard added in `a8687a0c` (2025-12-05, "Complete backend service-oriented architecture refactoring Phases 3-5") when `WAVEncoder` class was introduced; the plain-function `encode_to_wav` predates it (`fc3330a4`) and was never given the same guard in the 8 months since
- **Effort**: small (<=2h)
- **Description**: `ChunkedProcessor` has two call paths that both do the identical 4-step sequence — `_process_chunk_core()` → `ChunkOperations.extract_chunk_segment()` → encode extracted audio as WAV PCM_16 → atomically persist to the chunk cache path — but through two unrelated encoder implementations that were never consolidated:
  1. `process_chunk()` (chunked_processor.py:575) calls `self._wav_encoder.encode_and_save_from_path()`, the `WAVEncoder` class from `core/encoding/wav_encoder.py`, whose `encode_and_save()` validates `isinstance(audio, np.ndarray)`, rejects empty arrays, and rejects non-finite (NaN/Inf) samples with `ValueError` before writing, then uses `atomic_save_audio()` + `auralis.io.saver.save()`.
  2. `get_wav_chunk_path()` (chunked_processor.py:712, encode at 785-791) — the method whose own docstring calls it "the PRIMARY output method for the unified architecture" and which is what `routers/enhancement.py:188` actually calls on every enhanced-playback request — instead does an inline `from encoding.wav_encoder import WAVEncoderError, encode_to_wav` and calls the plain function `encode_to_wav()`, which only casts to float32 and `np.clip(audio, -1.0, 1.0)` — **no `isfinite` check, no empty-array check** — then writes bytes via a separately hand-rolled `atomic_write_bytes()`.
  A fix applied to one guard (e.g. the Dec-2025 NaN/Inf/empty validation) was never mirrored to the other, and nothing forces them to stay in sync since they are structurally different call shapes (class method vs. module function, `Path`-based `encode_and_save_from_path` vs. bytes-based `encode_to_wav` + `atomic_write_bytes`).
- **Evidence**:
  ```python
  # core/encoding/wav_encoder.py:127-134 (used only by process_chunk())
  if audio.size == 0:
      raise ValueError("Cannot encode empty audio array")
  if not np.isfinite(audio).all():
      raise ValueError("Audio contains non-finite values (NaN/Inf)")
  ```
  ```python
  # encoding/wav_encoder.py:53-59 (used by get_wav_chunk_path(), the "PRIMARY" path)
  if audio.dtype != np.float32:
      audio = audio.astype(np.float32, copy=True)
  audio = np.clip(audio, -1.0, 1.0)   # no isfinite/empty check anywhere in this function
  ```
- **Impact**: If DSP processing ever produces NaN/Inf (a class of bug this same audit's DSP dimension checks for), `process_chunk()` fails loudly with `ValueError` and the caller can retry/report, while `get_wav_chunk_path()` — the path actually wired to the enhancement-playback router — silently writes a WAV containing NaN/Inf samples (soundfile's PCM_16 write does not raise on NaN input) to a cache file that then gets served to the browser and reused for every future cache hit until `CACHE_VERSION` is bumped. This is exactly the "one copy dropped a guard the sibling has" pattern called out for DSP scaffolding, just one layer up (encode/persist rather than transform).
- **Siblings**: none beyond the two described (verified via `grep -rn "encode_and_save\|encode_to_wav" auralis-web/backend/core/chunked_processor.py`) — this is a 2-way duplication, not N-way.
- **Related**: Distinct from the `_audit-common.md` "two `WAVEncoderError` classes" claim, which is doc-rot (only one class exists) — see preliminary note above (Dim 7 territory). Not the same finding as fix #4576 (atomic-write-on-crash), which both paths already independently picked up.
- **Suggested Fix**: Pick one encode+persist primitive and route both call sites through it. Simplest: have `get_wav_chunk_path()` call `self._wav_encoder.encode_and_save()` (writing to `wav_chunk_path` directly) instead of the free-function `encode_to_wav()` + manual `atomic_write_bytes()`, so the isfinite/empty-array guard applies uniformly and there is exactly one atomic-write implementation (`atomic_save_audio`) instead of two (`atomic_save_audio` and `atomic_write_bytes`).

---

### TD3-2 (DEDUP — not filed as new): `BaseRepository._session_scope()` exists but 89 of 110 session-opening call sites across the 14 repositories still hand-roll `get_session()`/`try`/`finally: session.close()`

- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis/library/repositories/base.py:37-53` (the helper) vs 89 hand-rolled call sites in 12 of 14 repository files (see Siblings)
- **Status**: **Existing: #4604** ("BaseRepository._session_scope() adoption stalled at 2/14 repos — #4294's follow-up pass was never tracked", OPEN, filed 2026-07-25) — per dedup protocol this is SKIPPED as a new filing; kept below only because independent re-verification corrects the call-site arithmetic that both project memory and the likely issue body get wrong (see next bullet). Also supersedes/confirms closed #4294 ("111 call sites") and closed #4017 is the original boilerplate report.
- **Age**: `_session_scope()` was added recently relative to the repositories themselves (repositories date to the Phase 3-5 refactor, `a8687a0c`, 2025-12-05); `_session_scope` postdates that and has only ever been adopted in 2 of 14 files
- **Effort**: medium (<=1 day) for a full sweep; small per-file
- **Description**: `BaseRepository._session_scope()` is a context manager that opens a session via the configured factory and guarantees `session.close()` in a `finally` block — exactly the boilerplate every repository method needs. It is used in only 2 files (`fingerprint_repository.py`, 9 uses; `track_repository.py`, 12 uses — both partially, they also still have hand-rolled sites) out of 14. The other 12 files exclusively hand-roll `session = self.get_session(); try: ...; finally: session.close()` (frequently with an `except Exception: session.rollback()` layer duplicated verbatim each time). The read-only variant of this pattern (query → check-not-found → `session.expunge(x)` → `return x`) is copy-pasted near-verbatim across at least 7 `get_by_id`-style methods (`album_repository.py:32`, `artist_repository.py:21`, `genre_repository.py:33`, `queue_template_repository.py:66`, `track_repository.py:285` (already migrated to `_session_scope`), `playlist_repository.py:124`, plus `get_by_title`/`get_all` variants in the same files) — a fix to the lifecycle boilerplate (e.g. adding session-pool instrumentation, a retry policy, or migrating to async sessions — exactly the stated purpose of centralizing this in `base.py`'s own docstring) requires touching all 89 sites individually today.
- **Evidence**:
  ```python
  # auralis/library/repositories/album_repository.py:32-40 — hand-rolled, could be _session_scope
  def get_by_id(self, album_id: int) -> Album | None:
      """Get album by ID with relationships loaded"""
      session = self.get_session()
      try:
          album = session.execute(
              select(Album)
              .options(joinedload(Album.artist), selectinload(Album.tracks))
              .where(Album.id == album_id)
          ).scalars().unique().first()
  # ... finally: session.close()

  # auralis/library/repositories/track_repository.py:285-289 — the SAME shape, already migrated
  def get_by_id(self, track_id: int) -> Track | None:
      """Get track by ID with relationships loaded"""
      with self._session_scope() as session:
          track = session.execute(
              select(Track).options(*_track_eager_options()).where(Track.id == track_id)
          ).scalars().unique().first()
  ```
- **Impact**: Not a correctness bug today — checked all 89 hand-rolled sites programmatically (scan each method body up to its next `def`) and every one correctly pairs its `try` with a `finally: session.close()`; only one site (`queue_history_repository.py:124`, `undo()`) has a bare `try/finally` with no `except/rollback`, but `_session_scope()` itself does not provide rollback either (its own docstring: "Callers remain responsible for commit()/rollback() semantics") so this is not a capability the helper would have added — it is a separate, pre-existing question for another dimension, not cited as part of this duplication finding. The real cost is change-cost: `base.py`'s own docstring states the intent ("Centralising that here means a session-lifecycle change ... is a one-file edit instead of a per-repository sweep") but 89 of 110 call sites bypass that guarantee, so the stated goal is not actually met.
- **Siblings**: `grep -c "self\.get_session()" auralis/library/repositories/*.py` (excluding base.py): album_repository.py=9, artist_repository.py=6, fingerprint_repository.py=7, fingerprint_scheduler_repository.py=2, fingerprint_stats_repository.py=4, genre_repository.py=8, playlist_repository.py=10, queue_history_repository.py=5, queue_repository.py=4, queue_template_repository.py=12, settings_repository.py=5, similarity_graph_repository.py=7, stats_repository.py=1, track_repository.py=9 (total 89). `_session_scope(` is used only in fingerprint_repository.py (9) and track_repository.py (12) (total 21). 89+21=110, matching memory's "~110" figure as the *total*, not the unmigrated count.
- **Related**: Project memory `doc-facts-reconciled` / repository-pattern note (#4017 introduced `_session_scope`). Distinct from any transaction-correctness finding (queue_history_repository.py `undo()` missing explicit rollback) — that belongs to a concurrency/correctness dimension, noted here only as a "checked, not the same issue."
- **Suggested Fix**: Sweep the 89 call sites to `with self._session_scope() as session:`, keeping any existing `try/except/rollback` nested inside the `with` block for write paths (the helper's docstring already documents this usage). Do it file-by-file (album, artist, genre, playlist, queue_template, similarity_graph, settings, queue, queue_history, fingerprint_scheduler, fingerprint_stats, stats) since each is an independent, low-risk mechanical change with its own test coverage to verify.

---

### TD3-3 (DEDUP — overlaps existing #3892, refiled with corrected artifact): `routers/pagination.py` (`PaginatedResponse`/`PaginationParams`) is imported by zero routers — all 4 paginated list endpoints hand-roll the identical `has_more` formula and response shape

- **Severity**: LOW
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/pagination.py:20-122` (the unused helper) vs `auralis-web/backend/routers/albums.py:77-84`, `auralis-web/backend/routers/artists.py:166-173`, `auralis-web/backend/routers/tracks.py:58-64` and `:80-86` (two endpoints in the same file), `auralis-web/backend/routers/playlists.py:117-126`
- **Status**: **Existing (overlapping): #3892** ("Three coexisting pagination response shapes — `schemas.PaginatedResponse` is dead code, ad-hoc shapes circulate in library/albums/playlists", OPEN, 2026-05-28). #3892's *specific named artifact* is now stale/doc-rot: `grep -n "class PaginatedResponse" auralis-web/backend/schemas.py` finds nothing — `schemas.py` has no `PaginatedResponse` at all anymore (only `PaginationParams`/`CursorPaginationParams`), and nothing references `schemas.PaginatedResponse`. The dead-code artifact that actually exists today is `routers/pagination.py::PaginatedResponse` (a different module, not `schemas.py`), and the bypass list is one endpoint wider than #3892's (`artists.py` and `tracks.py`, not just library/albums/playlists). Filed here for the corrected evidence trail; not double-counted as a second new issue — treat as confirmation + correction of #3892, not a new debt item.
- **Age**: `pagination.py` module docstring itself claims "eliminates the duplication ... that appears in 6+ router response models" — the consolidation was written but never wired up; not tied to one commit, verified structurally instead (`grep -rln "pagination import\|PaginatedResponse\|PaginationParams" auralis-web/backend/routers/*.py` matches only `pagination.py` itself)
- **Effort**: small (<=2h)
- **Description**: `routers/pagination.py` defines `PaginatedResponse.create()` (computes `has_more` once, in one place) and `PaginationParams` (the `DEFAULT_LIMIT=50`/`MAX_LIMIT=200`/`MIN_LIMIT=1` constants). Every router that actually paginates a list — `albums.py`, `artists.py`, `tracks.py` (two endpoints: `get_tracks` and `get_favorite_tracks`), `playlists.py` — reimplements the exact same three things independently instead of importing the helper: (1) the `has_more = (offset + len(items)) < total` formula, verbatim, 5 times; (2) the `limit`/`offset`/`total`/`has_more` response dict shape, verbatim, 5 times; (3) the `Query(50, ge=1, le=200)` / `Query(0, ge=0)` magic numbers instead of referencing `PaginationParams.DEFAULT_LIMIT`/`MAX_LIMIT`. A fix to the `has_more` semantics (e.g. the #4554 fix note visible in `playlists.py`'s own docstring, "`total` is a real COUNT rather than the length of the page") had to be — and in the future would have to be — applied by hand in up to 5 places instead of once in `PaginatedResponse.create()`.
- **Evidence**:
  ```python
  # albums.py:77        artists.py:166                      tracks.py:58 and :80        playlists.py:126
  has_more = (offset + len(albums)) < total
  has_more = (offset + len(artist_responses)) < total
  has_more = (offset + len(tracks)) < total     # x2, identical, same file
  "has_more": (offset + len(serialized)) < total,
  ```
  vs. the unused helper already providing exactly this:
  ```python
  # pagination.py:86-92
  return cls(items=items, total=total, offset=offset, limit=limit,
             has_more=(offset + len(items)) < total)
  ```
- **Impact**: Low — the formula is simple and all 5 copies are currently consistent with each other, so there is no live divergent-bug-fix case today. The cost is entirely in change-cost: any future change to pagination semantics (e.g. switching to cursor-based paging, or fixing an off-by-one) is a 5-site manual sweep instead of a 1-file edit, and the existing `pagination.py` module is dead code that a future reader will reasonably (but incorrectly) assume is in use.
- **Siblings**: All 4 files/5 endpoints listed above are the complete set — confirmed via `grep -rn "has_more" auralis-web/backend/routers/*.py`, which returns only these 5 call sites plus the definitions inside `pagination.py` itself.
- **Related**: Not the same as any `sync-contracts` schema mismatch; this is pure server-side logic duplication. `playlists.py`'s own docstring cites `#4554` as the commit that added the limit/offset convention to that endpoint to match albums/artists/tracks — i.e. the convention itself is being deliberately kept consistent by hand across files already, which is the strongest sign this should be centralized now rather than continuing to be copy-pasted forward.
- **Suggested Fix**: Have the 4 routers return `PaginatedResponse.create(items=..., total=total, limit=limit, offset=offset)` (or its `.model_dump()` if the route contract needs a plain dict) instead of hand-building the response dict, and replace the repeated `Query(50, ge=1, le=200)`/`Query(0, ge=0)` literals with `Query(PaginationParams.DEFAULT_LIMIT, ge=PaginationParams.MIN_LIMIT, le=PaginationParams.MAX_LIMIT)`. If the response *shape* genuinely cannot be a shared Pydantic model (e.g. `ArtistsListResponse` needs bespoke fields), at minimum reuse `PaginatedResponse.create()`'s `has_more` value rather than recomputing the formula.

---

### TD3-4: `artists.py` hand-derives `album_count`/`track_count` inline instead of calling `serialize_artist()` — and missed the Mock-safety fix that `serialize_artist()` received

- **Severity**: MEDIUM
- **Dimension**: Logic Duplication
- **Location**: `auralis-web/backend/routers/artists.py:142-162` (inline `ArtistResponse` construction) vs `auralis-web/backend/routers/serializers.py:264-290` (`serialize_artist()`/`serialize_artists()`)
- **Status**: NEW
- **Age**: fix commit `5d5784a9` (2026-07-18, #4306) hardened `serialize_artist()`'s `len()` calls with `try/except TypeError` for Mock-safety; `artists.py`'s equivalent inline logic was never touched by that commit and still has the unguarded form
- **Effort**: trivial (<=30min)
- **Description**: `serializers.py` provides `serialize_artist()`, which derives `album_count = len(artist.albums)` and `track_count = len(artist.tracks)` from the ORM relationships (guarded with `hasattr(...) and artist.albums` then, since #4306, `try/except TypeError` to survive unconfigured Mocks in tests). `routers/artists.py`'s `get_artists` endpoint (the actual `/api/artists` list handler) never imports or calls this — it independently loops over the fetched artists and builds `ArtistResponse` objects with its own inline derivation: `album_count=len(artist.albums) if artist.albums else 0` / `track_count=len(artist.tracks) if artist.tracks else 0`, with no `try/except TypeError`. The commit that added the Mock-safety guard to `serialize_artist()` (5d5784a9) explicitly states in its own message "unlike serialize_album/serialize_artist which artists.py/albums.py already call" — that belief is **incorrect for artists.py**: `grep -n "serialize" auralis-web/backend/routers/artists.py` returns zero calls into `serializers.py`, and `git log --follow -p` confirms `artists.py` has never imported it. So the count-derivation logic was written twice (once in the serializer, once inline in the router), and a targeted bug fix landed in only one copy.
- **Evidence**:
  ```python
  # serializers.py:276-285 (serialize_artist, fixed by #4306)
  if hasattr(artist, 'albums') and artist.albums:
      try:
          artist_dict['album_count'] = len(artist.albums)
      except TypeError:
          pass
  if hasattr(artist, 'tracks') and artist.tracks:
      try:
          artist_dict['track_count'] = len(artist.tracks)
      except TypeError:
          pass
  ```
  ```python
  # artists.py:156-157 (inline, never received the #4306 guard)
  album_count=len(artist.albums) if artist.albums else 0,
  track_count=len(artist.tracks) if artist.tracks else 0,
  ```
- **Impact**: In production `artist.albums`/`artist.tracks` are real SQLAlchemy `InstrumentedList` relationships and are always sized, so this does not crash live traffic today — the practical exposure is to future unit tests that mock an `Artist` without configuring `.albums`/`.tracks` (unconfigured `Mock()` attributes are truthy but not `len()`-able), which would raise `TypeError` in `artists.py`'s handler while the equivalent `playlists.py`/`albums.py` handlers (already routed through their serializers) would not. This is exactly the kind of latent test-fragility gap #4306 was written to close, just not closed here.
- **Siblings**: `albums.py` and `playlists.py` both call through `serializers.py` (`serialize_albums`/`serialize_album_detail`, `serialize_playlists`/`serialize_playlist`) — confirmed via `grep -rln "from .serializers import" auralis-web/backend/routers/*.py`. `artists.py` is the one router of the 4 with a serializable list response that does not.
- **Related**: Commit `5d5784a9` (#4306) — this finding is the gap that commit's own message misidentified as already closed.
- **Suggested Fix**: Replace the manual `ArtistResponse(...)` field-by-field construction in `artists.py`'s `get_artists` with `serialize_artist(artist)` (mapping its dict output into `ArtistResponse`), or at minimum wrap the two `len()` calls in the same `try/except TypeError` `serialize_artist()` already uses, so the guard doesn't have to be independently rediscovered a third time.

---

## Target group 4: DSP pre/post-amble in `auralis/core/stages/` and `auralis/dsp/` — RE-VERIFIED, still holds

Re-checked the 2026-07-25 finding ("shared `no_op` guard structurally intact, no sibling omits `.copy()`") after the 128 intervening commits. **Still holds — 0 new findings.**

- `auralis/core/stages/__init__.py:16-31` defines the shared `no_op(audio) -> (audio.copy(), None)` helper with an explicit docstring naming exactly which stage is deliberately exempt (`safety_limiter.apply()`, terminal limiter, bare-`ndarray` contract) and why (`#4298`).
- `grep -n "no_op(audio)\|def apply" auralis/core/stages/*.py`: all 11 tuple-contract stages (air_enhancement, bass_enhancement, clarity_boost, harmonic_exciter, mid_warmth, presence_enhancement, resonance_notches, stereo_expansion, sub_bass_control, transient_shaper, and their bypass branches) route every early-return through `no_op(audio)` — 18 call sites, matching the docstring's own count.
- `safety_limiter.py:35` still does its own `return audio.copy()` on the bypass path (`current_peak <= ceiling`), consistent with its documented exemption.
- `loudness_maximizer.py` has no bypass path at all — by design ("no recording labels, activation thresholds, or content-dependent bypasses", per its own module docstring, consistent with the continuous-parameter-space architecture) — so it correctly has no `no_op` call to omit.
- `grep -n "audio +=\|audio -=\|audio \*=\|audio /=\|audio\[.*\] ="` across all 13 stage files: zero hits — no in-place mutation anywhere in the family.
- `auralis/dsp/stages.py` (the DSP pipeline `main()` entry point) and `auralis/dsp/__init__.py` contain no direct audio-copy logic to check — they are orchestration/dispatch only, not transform sites.
- `hf_budget.py` is correctly excluded from the `no_op`-sharing `__init__.py` import list — it exports `hf_lift_factor()`, a scalar multiplier helper consumed by `mastering_branches/continuous.py`, not a tuple-contract `apply()` stage; this is not an omission.

## Target group 5: `stream_*.py`/`chunk_*.py` families and `mastering_*.py` family — examined, no new finding filed

- `auralis-web/backend/core/stream_normal.py`, `stream_enhanced.py`, `stream_seek.py` are structurally similar (each streams WAV/PCM chunks over the same WebSocket protocol) but are **deliberately, visibly kept in sync**: cross-referenced their embedded issue-number trail (`grep -on "#[0-9]\{4\}"` per file) and found the concurrency/lifecycle fixes shared across all three (`#2185` semaphore cap, `#2493` per-task stream-type var, `#3493` cancelled-task drain, `#4329` permit-leak-on-cancel, `#4659` completion-reason handling, `#3511` disconnect-as-normal-exit, `#2302`/`#4345` path validation) are present in all three files, and comments explicitly say "mirrors the enhanced path" / "matching the enhanced path (stream_seek.py)" when a fix in one was ported to another (e.g. `#4560`'s server-side seek-trim). No divergent-fix case found on spot-check. This reads as actively-maintained parallel implementations, not neglected copy-paste — did not file a finding; flagging as examined in case a deeper pass (more time budget) turns up a stale case this sampling missed.
- `auralis/core/mastering_chunk_loop.py`, `mastering_prepare.py`, `mastering_process_chunk.py`, `mastering_diagnostics.py`, `mastering_notch_context.py` are NOT duplicates of each other — their docstrings identify them as the god-file-split output of `#4071`/`#4072` (each extracted a distinct, non-overlapping responsibility from `simple_mastering.py`'s `_master_file_impl`). Consistent with project memory's "godfile-split-4071-4072" note. No finding.

## Target group 6: `auralis-web/frontend/src/hooks/` — examined, no new finding filed

- `hooks/shared/useStandardizedAPI.ts`'s own docstring records that its generic fetch-on-mount hook was already migrated to `hooks/api/useRestAPI.ts` and its unused pagination/batch surface already deleted ("streamlining #7") — i.e. this specific consolidation was already done in an earlier pass.
- Spot-checked hooks with local `loading`/`error` state (`useAlbumFingerprint.ts`, `useTrackFingerprint.ts`, etc.): these use `@tanstack/react-query`'s `useQuery`, whose `isLoading`/`error` are library-provided, not a hand-rolled state machine — not duplication, this is the correct idiomatic pattern repeated because it's correct each time, not because it's copy-pasted.
- WebSocket subscribe/cleanup: `hooks/websocket/useWebSocketMessages.ts` is the shared subscribe+cleanup hook (7 confirmed callers). Three hooks bypass it with direct `wsContext.subscribe()` calls — `useAudioStreamingCore.ts` (4 subscriptions), `useEnhancedSeek.ts`, `useFingerprintStatus.ts` — but `useAudioStreamingCore.ts`'s bypass is deliberately engineered (heavily commented `#3588`/`#2532`/`#4563` ref-indirection design, and the file itself is already the single "choke point" shared by `usePlayEnhanced`/`usePlayNormal`/etc., per its own comments) rather than an accidental duplicate. Did not find a clean, named consolidation-target gap here worth filing — this would need a deeper per-hook read than time allowed to confirm as a real (not speculative) finding, so it is intentionally left out per the methodology warning rather than padded in.

---

## Summary

| ID | Title | Severity | Status |
|---|---|---|---|
| TD3-1 | Two encode+persist WAV pipelines in `chunked_processor.py`, one missing the finite-audio guard | MEDIUM | NEW |
| TD3-2 | `_session_scope()` adoption stalled (89/110 hand-rolled) | LOW | Existing: #4604 (dedup, not filed) |
| TD3-3 | `routers/pagination.py` unused, 4 routers hand-roll `has_more` | LOW | Existing (overlapping): #3892 (dedup, not filed; corrected artifact) |
| TD3-4 | `artists.py` duplicates `serialize_artist()`'s count logic, missed its Mock-safety fix | MEDIUM | NEW |

**Net new, non-duplicate findings filed: 2** (TD3-1, TD3-4). Two additional items (TD3-2, TD3-3) were independently re-derived, confirmed still true, and used to correct stale numbers/artifacts in an existing open issue and project memory, but are NOT counted as new debt per the dedup protocol.

## Dimension 4 — Magic Numbers & Hardcoded Constants

## Findings

### TD4-1: `ChunkOperations` re-hardcodes the chunk-boundaries SoT as default parameters in 4 signatures
- **Severity**: LOW
- **Dimension**: Magic Numbers & Hardcoded Constants
- **Location**: `auralis-web/backend/core/chunk_operations.py:44-46` (`load_chunk_from_file`), `:161-163` (`extract_chunk_segment`), `:349` (`calculate_total_chunks`), `:373-374` (`get_chunk_time_range`)
- **Status**: NEW
- **Age**: `4825d4ff` 2025-12-16 (file creation) — unchanged since
- **Effort**: trivial (<=30min)
- **Description**: `auralis-web/backend/core/chunk_boundaries.py` is the documented "SINGLE SOURCE OF TRUTH" for `CHUNK_DURATION=15.0`/`CHUNK_INTERVAL=10.0`/`OVERLAP_DURATION=5.0`. `chunk_operations.py` — whose own docstring says it exists to "prevent duplication and ensure consistency" — re-states those same three values as bare literal defaults on 4 separate function signatures instead of importing and defaulting to the constants: `chunk_duration: int = 15`, `chunk_interval: int = 10`, `overlap_duration: int = 5`, `context_duration = 5.0` (line 87, inline body literal, not even a parameter).
- **Evidence**:
  ```python
  # chunk_operations.py:44-46
  chunk_duration: int = 15,
  chunk_interval: int = 10,
  overlap_duration: int = 5,
  ...
  # chunk_operations.py:87
  context_duration = 5.0 if with_context else 0.0
  ```
  Verified every current call site (production: `chunked_processor.py:351-353,566-568,776-778` — all three pass `CHUNK_DURATION`/`CHUNK_INTERVAL`/`OVERLAP_DURATION` explicitly imported from `chunk_boundaries.py`; tests: `tests/backend/test_chunk_count_no_silence_padding.py`, `test_extract_chunk_segment_overlap.py`, `test_chunk_operations_fallback_dtype.py`, `test_trim_context_short_tracks.py` — all pass the same three explicitly). **No call site relies on the defaults today** — this is latent, not live, so it does not meet the HIGH "would silently truncate/overflow audio" promotion bar.
- **Impact**: If `chunk_boundaries.py`'s geometry is ever retuned (the one deliberate SoT for this), these 4 defaults do not follow and silently diverge for any *new* caller (or a future test) that omits the keyword args — e.g. `get_chunk_time_range` (line 371) is currently **unreferenced anywhere in the repo** (dead code — flag to Dim 2/8 owner, not re-filed here), so it is exactly the kind of call site a future author could resurrect and get away without noticing the values are now stale copies.
- **Siblings**: `context_duration = 5.0` inline literal at line 87 (same value, no parameter at all — even harder to override consistently).
- **Related**: Same "duplicate-instead-of-import" pattern as CLOSED #4620/TD4-1 from `AUDIT_TECH_DEBT_2026-07-25` (that one was `cache/manager.py::_calculate_total_chunks` re-deriving `content_chunk_count`'s *formula*; this one is `chunk_operations.py` re-deriving the *constants themselves* as defaults). That prior finding was fixed in `3e61731b` (#4620) by delegating to `content_chunk_count` — this finding is the sibling case in the same file the fix commit did not touch.
- **Suggested Fix**: `from core.chunk_boundaries import CHUNK_DURATION, CHUNK_INTERVAL, OVERLAP_DURATION, CONTEXT_DURATION` at the top of `chunk_operations.py` and default the 4 signatures to those names instead of bare literals (e.g. `chunk_duration: float = CHUNK_DURATION`). Delete the now-dead `get_chunk_time_range` separately (out of scope for this dimension).

### TD4-2: `auralis/core/config.py`'s "legacy" `Config`/`LimiterConfig` are not a live second source of truth — they are UNREACHABLE dead code shadowed by the `auralis/core/config/` package, and this audit suite's own doc says otherwise
- **Severity**: MEDIUM
- **Dimension**: Magic Numbers & Hardcoded Constants
- **Location**: `auralis/core/config.py:1-96` (whole file); shadowing package at `auralis/core/config/__init__.py`
- **Status**: NEW — corrects a stale claim, not a regression of a numbered issue
- **Age**: `config.py` last substantively touched `4104ea2d` ("Project refactor into Auralis player", pre-Auralis-fork era); only isort/typing-modernization commits since (`4e6c06fa`, `2ff696c9`)
- **Effort**: trivial (<=30min) — delete the file, or (if kept as a historical reference) rename it so it can't masquerade as an importable module
- **Description**: This audit's task brief (and `.claude/commands/_audit-common.md`'s own Project Layout table, which every audit in this suite reads) states `auralis/core/config.py` is *"Legacy dataclass configs (LimiterConfig etc.) — still live, distinct from the package above"*. That claim is **false as written**: in CPython's import system a regular package directory (`auralis/core/config/`, with `__init__.py`) and a same-named module file (`auralis/core/config.py`) cannot coexist as two independently-reachable things — `import auralis.core.config` (and every relative `from .config import ...` from a sibling file under `auralis/core/`) resolves **only** to the package. I verified this directly: `import auralis.core.config as c` → `c.__file__` is `auralis/core/config/__init__.py`; `hasattr(c, 'Config')` is `False`; `hasattr(c, 'UnifiedConfig')` is `True`. `config.py`'s `Config`/`LimiterConfig` classes have **zero possible importers** anywhere in the tree — I grepped for `from .config import Config`, `core.config import Config`, and bare `Config(` construction outside the package and found none. The file is orphaned, not "legacy-but-live."
- **Evidence**:
  ```
  $ python -c "import auralis.core.config as c; print(c.__file__, hasattr(c,'Config'), hasattr(c,'UnifiedConfig'))"
  /mnt/data/src/matchering/auralis/core/config/__init__.py False True
  ```
  Values inside the dead file do numerically agree with the live package today — `internal_sample_rate=44100`, `fft_size=4096`, `allow_equality=False`, and `LimiterConfig`'s 8 fields (`attack=1`, `hold=1`, `release=3000`, `attack_filter_coefficient=-2`, `hold_filter_order=1`, `hold_filter_coefficient=7`, `release_filter_order=1`, `release_filter_coefficient=800`) all match `auralis/core/config/unified_config.py:30-36` and `auralis/core/config/settings.py:18-25` byte-for-byte — so there is no live divergence today, but the *mechanism* the task asked me to check ("a value defined in both is itself a finding") is present, and the actual finding is sharper than divergence: the "second definition" already misled a real audit.
- **Impact**: `docs/audits/AUDIT_TECH_DEBT_2026-07-25.md:576` (TD4-2's own "Siblings" line) cites `auralis/core/config.py:61`'s `internal_sample_rate: int = 44100` as *"the legitimate configured default [that] should stay"* when recommending 40 DSP `sample_rate=44100` defaults be made required — but that citation points at dead, unreachable code, not a real configured default. Any future maintainer who edits `config.py` expecting to change a live default (e.g. bumps `fft_size` there to "fix" something) will silently change nothing while believing they configured the engine. This meets the promotion table's "stale doc/audit baseline that has misled an audit in the last 90 days" → MEDIUM floor, since it demonstrably misled the tech-debt audit 4 days ago.
- **Siblings**: None found — checked whether any other `auralis/**/config.py` + `auralis/**/config/` pair coexists the same way (`find auralis -name config.py` vs sibling `config/` dirs); no other collision exists in the tree.
- **Related**: TD4-2 in `AUDIT_TECH_DEBT_2026-07-25.md` (the one that cited the dead file), and `_audit-common.md`'s Project Layout table row `Core Config: ... auralis/core/config.py Legacy dataclass configs (LimiterConfig etc.) — still live, distinct from the package above` (Dim 7 doc-rot owner should also correct this row).
- **Suggested Fix**: Delete `auralis/core/config.py` (its `Config`/`LimiterConfig` classes have no callers and the package's `UnifiedConfig`/`LimiterConfig` in `settings.py` are the real, live, tested definitions) and correct the Project Layout row in `_audit-common.md` in the same change so this doesn't mislead the next audit.

### TD4-3: `sample_rate=44100` default re-verification after 128 commits — recount 46→48, HIGH promotion did NOT fire
- **Severity**: LOW (verification note, not a new bug)
- **Dimension**: Magic Numbers & Hardcoded Constants
- **Location**: 48 sites across `auralis/` and `auralis-web/backend/` (full list re-derived below); 2 sites are new since the 2026-07-25 audit: `auralis/analysis/quality/mastering_evaluation.py:22` (`MasteringEvaluator.__init__`, added in `52659172` "Implement closed-loop mastering evaluation framework") and `auralis/core/processing/base/stereo_width_processor.py:59` (pre-existing file, pattern just wasn't hit by the prior grep's exact wording)
- **Status**: NEW verification (re-derives/updates prior audit's TD4-2, does not replace it — that finding is about defaults-as-a-class, still open, LOW, unchanged)
- **Effort**: N/A (informational recount)
- **Description**: Diffed the exact grep (`sample_rate\s*:?\s*(int)?\s*=\s*44100`) against `git show 499a2101` (the commit the 2026-07-25 report was generated from) vs current `HEAD`. Count moved 46→48 (the 2026-07-25 report's own text said "40" as a rounded/illustrative count, not the full 46 the same regex actually returns at that commit — so the 40→48 delta partly reflects a stricter recount, not 8 new sites; only 2 sites are genuinely new).
- **Evidence**: Traced both new sites to their call sites:
  - `MasteringEvaluator(...)` is constructed at `auralis/core/processing/continuous_mode.py:380` (`sample_rate=self.config.internal_sample_rate`, explicit) and `auralis/analysis/quality/mastering_file_evaluation.py:63` (`sample_rate=sample_rate` read from `sf.SoundFile(...).samplerate`, explicit — this is the file-evaluation entry point, so it directly sees whatever rate the file actually is, e.g. 48k/96k, and passes it through).
  - `adjust_stereo_width_multiband(...)`, the function `stereo_width_processor.py` wraps, is called at `auralis/core/stages/stereo_expansion.py:102` (`sample_rate` positional, from stage context) and `auralis/core/processing/continuous_mode.py:611` (`self.config.internal_sample_rate`, explicit) — again no reliance on the default.
- **Impact**: The HIGH promotion trigger ("hardcoded rate/chunk/buffer constant that would silently truncate/overflow audio under documented use") **did NOT fire** — confirmed for the 2 new sites and spot-re-checked 6 of the pre-existing 46 (`spectral_centroid`, `tempo_estimate`, `calculate_loudness_units`, `content_analyzer.py`, `feature_extractor.py`, `psychoacoustic_eq.py` construction site) — all still pass an explicit rate at their real call sites. No caller anywhere in `auralis-web/backend/` (the layer that actually sees file-native sample rates from uploads/library scans) omits `sample_rate`.
- **Siblings**: Full current 48-site list (for the next audit's diff base) saved nowhere persistent by me per read-only constraints — re-derivable via `grep -rIn -E 'sample_rate\s*:?\s*(int)?\s*=\s*44100' auralis auralis-web/backend`.
- **Related**: Supersedes-by-recount (not fixes) `AUDIT_TECH_DEBT_2026-07-25.md` TD4-2, whose own "Suggested Fix" (cite `config.py:61` as "the legitimate configured default") is corrected by TD4-2 above (this report) — that citation was pointing at dead code.
- **Suggested Fix**: No action needed beyond TD4-2's existing suggestion (make the ~30 module-level DSP call-through helpers require `sample_rate` positionally so `mypy` catches any future omission) — still valid, still not urgent since nothing relies on the default today.

### TD4-4: Stream-semaphore acquire timeout (`5.0`s) duplicated bare in 3 streaming modules, unlike its sibling constants in the same file
- **Severity**: LOW
- **Dimension**: Magic Numbers & Hardcoded Constants
- **Location**: `auralis-web/backend/core/stream_normal.py:65`, `auralis-web/backend/core/stream_seek.py:79`, `auralis-web/backend/core/stream_enhanced.py:71`
- **Status**: NEW
- **Age**: pattern present since `#2185` fix era; unchanged in the 128 commits since the last audit (`git log -3` on all 3 files shows only unrelated recent touches)
- **Effort**: trivial (<=30min)
- **Description**: All three streaming entry points (normal/seek/enhanced playback) do `await asyncio.wait_for(controller._stream_semaphore.acquire(), timeout=5.0)` guarding the same `MAX_CONCURRENT_STREAMS` cap, with the identical surrounding comment `# Limit concurrent streams to prevent unbounded memory growth (#2185)`. `audio_stream_controller.py` — the module that owns the semaphore — already has the right convention for exactly this kind of value: `MAX_CONCURRENT_STREAMS` (line 117, env-overridable via `AURALIS_MAX_CONCURRENT_STREAMS`, documented in `CONFIG.md`) and `CHUNK_PROCESS_TIMEOUT: float = 30.0` (line 130) are both named module constants. The `5.0` acquire timeout is the one value in this cluster that didn't get promoted the same way, so it now exists as 3 independent bare literals instead of 1 named constant with 3 importers.
- **Evidence**: identical snippet in all three files:
  ```python
  # Limit concurrent streams to prevent unbounded memory growth (#2185)
  try:
      await asyncio.wait_for(controller._stream_semaphore.acquire(), timeout=5.0)
  ```
- **Impact**: A future tuning pass (e.g. raising the semaphore-wait tolerance under slower disks, or lowering it to fail faster under load) requires editing 3 files in lockstep with no compiler/test signal if one is missed — exactly the "duplicated logic, one gets updated, other doesn't" shape, just not yet manifested as a bug since all 3 currently agree.
- **Siblings**: All 3 sites are the complete set — grepped `_stream_semaphore.acquire(` across the repo, no 4th call site exists.
- **Related**: None on file; distinct from `MAX_CONCURRENT_STREAMS`/`CHUNK_PROCESS_TIMEOUT` which are already correctly centralized in the same module.
- **Suggested Fix**: Add `STREAM_ACQUIRE_TIMEOUT_SECONDS: float = 5.0` next to `CHUNK_PROCESS_TIMEOUT` in `audio_stream_controller.py` and import it in the 3 call sites, matching the existing convention in the same file.

## Checked, found clean (no finding filed)

- **Chunk-constant bypass, general sweep**: grepped all of `auralis-web/backend/` for `CHUNK_DURATION`/`CHUNK_INTERVAL`/`OVERLAP_DURATION`/`CONTEXT_DURATION`/`content_chunk_count` outside `chunk_boundaries.py`. Every one of `chunked_processor.py`, `chunk_operations.py` (its *delegating* method, `calculate_total_chunks`), `stream_normal.py`, `cache/manager.py`, `cache/__init__.py` imports the real constants/function. The one naive `ceil(total_frames / interval_samples)` outside the SoT (`stream_normal.py:166`) was already verified correct and non-duplicative by the 2026-07-25 audit (zero-overlap unenhanced path, documented at `stream_normal.py:161-163`) — re-confirmed by reading it again; not re-filed.
- **`cache/manager.py::_calculate_total_chunks`**: CLOSED #4620 (`3e61731b`) fixed the prior audit's TD4-1 — verified the fix is still in place (`cache/manager.py:191` is now a one-line delegation to `content_chunk_count`). No regression.
- **Backend request/upload limits**: `auralis-web/backend/config/limits.py` (`MAX_UPLOAD_BYTES`, `MAX_UPLOAD_FILES`, #4033) is correctly centralized and imported by both `routers/files.py` and `routers/processing_api.py` — no bypass found.
- **Frame-byte budget**: `cache/manager.py:45-49` already names `_NOMINAL_SAMPLE_RATE`/`_NOMINAL_CHANNELS`/`_PCM16_BYTES_PER_SAMPLE` as module constants; no sibling site duplicates the PCM16 byte-budget arithmetic with bare literals.
- **FFT/window/hop sizes**: `auralis/dsp/eq/psychoacoustic_eq.py` (`fft_size=4096`), `auralis/dsp/realtime_adaptive_eq/settings.py`+`factory.py` (`buffer_size=1024`, consistent between the two), and `realtime_eq.py`'s `fft_size=settings.buffer_size * 2` (a derived value, not a duplicated literal) are the only real hits under `auralis/dsp/`. `auralis/analysis/fingerprint/` does not use `hop_length`/`n_fft`/`window_size` naming at all (Rust DSP owns FFT internals via PyO3, out of scope for this Python-side check). No cross-module disagreement found — this checklist item came back clean.
- **Frontend hardcoded colors**: The known lead ("324 references / 103 files reading dark-only `tokens.colors.*`") is already filed as `D5-01` in `docs/audits/AUDIT_FRONTEND_2026-07-29.md` — confirmed by reading that finding; not re-filed here (`Related`, not `NEW`). Independently re-swept `auralis-web/frontend/src` for raw `#hex`/`rgb(` literals outside `design-system/`: the overwhelming majority of grep hits (~250 of ~262) are false positives — the naive `#[0-9a-fA-F]{3,8}` pattern also matches GitHub issue references in comments (`#3642`, `#4297`, etc.), a direct instance of the methodology warning's grep-inflation trap. The small number of genuine literal-color hits (`index.tsx:25-26,54` — a last-resort pre-React crash-fallback HTML string; `store/middleware/loggerMiddleware.ts:62-66,214,220` — dev-only Redux action-log console colors) are single-purpose, non-visual-design-system surfaces with no siblings and no user-facing reach; not filed.

## Dimension 5 — Stub & Placeholder Implementations

Project root: /mnt/data/src/matchering. HEAD 09004fa2. (in progress)

## Pre-verified facts re-checked (no new findings from these)

1. **`NotImplementedError` in `duplicate_detector.py`** — VERIFIED as a documented, caller-handled
   contract, NOT a stub. `DuplicateDetector.find_duplicates(directories=None)` raises `NotImplementedError`
   only when constructed without a `library_manager` (`duplicate_detector.py:98-103`). Traced every
   caller repo-wide: `LibraryScanner.find_duplicates` (`scanner.py:364-374`) is a thin pass-through, and
   `LibraryScanner.find_duplicates` itself has **zero callers anywhere in `auralis-web/backend/` or any
   router** (`grep -rn "find_duplicates" auralis-web` → 0 hits; `library_scan.py`/`library.py` routers
   never mention duplicate detection). The only callers of `find_duplicates` at all are
   `tests/auralis/library/test_duplicate_detector_whole_library.py` (which deliberately exercises the
   `NotImplementedError` path). The `except NotImplementedError: raise` at `duplicate_detector.py:83-84`
   re-raises rather than swallowing — it exists only to stop the generic `except Exception` below it from
   catching and masking the contract violation, which is correct defensive code, not a bug. **Not
   reachable from any shipped route. Filing nothing.**
2. **Bare `...` bodies** — VERIFIED all inside `typing.Protocol` class definitions: `playback_service.py`
   (`AudioPlayer`, `PlayerStateManager`, `ConnectionManager` Protocols, lines 18-62),
   `queue_protocols.py` (`QueueManager`, `AudioPlayerWithQueue`, lines 22-81),
   `recommendation_service.py` (`BroadcastManager`, line 20). Each Protocol is used purely as a
   structural type hint for duck-typed concrete classes (e.g. `EnhancedAudioPlayer` satisfies
   `AudioPlayer`/`AudioPlayerWithQueue` structurally; `ConnectionManager` (websockets) is the real
   connection manager). None of these Protocols has zero implementers — the concrete classes they
   describe are all live (the real player, the real connection manager, the real queue service).
   **Confirmed dismissal, not a stub. Filing nothing.**

---

### TD5-1: Auto-reference-selection silently no-ops on almost every real invocation — tuple-unpack of a `list[Track]`, swallowed by a broad `except`
- **Severity**: MEDIUM
- **Dimension**: Stub & Placeholder Implementations
- **Location**: `auralis/player/integration_manager.py:296` (bug), `:281-312` (`_auto_select_reference`, the whole method whose success path this breaks), `:267-268` (call site), `auralis/library/repositories/track_repository.py:637-687` (`find_similar`, the method whose return type is being misused)
- **Status**: NEW
- **Age**: `b9f6d05a5` 2025-12-12 (git blame on the buggy line)
- **Effort**: trivial (one-line fix: `references = repos.tracks.find_similar(track, limit=3)`)
- **Description**: `TrackRepository.find_similar()` is typed and documented to return `list[Track]` (verified
  by reading the full method body, `track_repository.py:637-687`: it builds `similar_tracks: list[Track]`
  and `return result` where `result = similar_tracks[:limit]` — a flat list, never a tuple). But its only
  in-engine caller, `IntegrationManager._auto_select_reference()`, destructures it as a 2-tuple:
  ```python
  references, _ = repos.tracks.find_similar(track, limit=3)
  ```
  Unpacking a list into `a, b = list_result` only succeeds when the list has **exactly 2 elements**. With
  `limit=3`, `find_similar` can return 0, 1, 2, or 3 tracks depending on how many artist/genre matches
  exist — it returns exactly 2 only by coincidence. In every other case (0, 1, or 3 matches — the common
  cases for both a track with no library-mates and a track with several) the line raises
  `ValueError: not enough values to unpack` or `too many values to unpack`, which is caught by the
  broad `except Exception as e: warning(f"Auto reference selection failed: {e}")` three lines below
  (`:311-312`). The feature is wired into the default-`True` `auto_reference_selection` flag
  (`integration_manager.py:85`) and fires on every `load_track_from_library()` call — which is reachable
  from a shipped route (`auralis-web/backend/routers/player.py:399`,
  `audio_player.load_track_from_library, request.track_id`, via
  `EnhancedAudioPlayer.load_track_from_library` → `IntegrationManager.load_track_from_library` →
  `_auto_select_reference`). So this is not a rare edge case: auto-reference-selection is effectively a
  no-op on the live player pipeline almost every time it runs, but the call site
  (`if self.auto_reference_selection: self._auto_select_reference(track)`) and the surrounding code
  behave as if the feature does something — nothing in the logs distinguishes "no similar tracks were
  found" from "the unpacking crashed," both produce the same generic warning string.
- **Evidence**:
  ```
  # track_repository.py:637-687 (return type, verified by reading the whole method)
  def find_similar(self, track: Track, limit: int = 5) -> list[Track]:
      ...
      result = similar_tracks[:limit]
      for t in set(result):
          session.expunge(t)
      return result

  # integration_manager.py:294-296
  # Find and try similar tracks as references
  repos = self._get_repos()
  references, _ = repos.tracks.find_similar(track, limit=3)   # <-- unpacks a list as a 2-tuple

  # integration_manager.py:311-312
  except Exception as e:
      warning(f"Auto reference selection failed: {e}")

  # auralis-web/backend/routers/player.py:399 — the shipped route that reaches this code
  audio_player.load_track_from_library, request.track_id
  ```
  Reachability chain confirmed: `routers/player.py:399` → `EnhancedAudioPlayer.load_track_from_library`
  (`enhanced_audio_player.py:274-294`) → `IntegrationManager.load_track_from_library`
  (`integration_manager.py:235-279`, which calls `_auto_select_reference` at `:268` when the
  default-`True` flag is set) → the buggy destructuring at `:296`.
- **Impact**: A documented player feature ("auto-select a suitable reference track based on similar
  library tracks") silently does nothing on the vast majority of track loads, and the failure is
  indistinguishable in logs from the legitimate "no suitable reference found" case (`:309`) — both look
  like ordinary, expected warnings. Anyone debugging "why doesn't auto-reference ever pick a track"
  would have to read past the broad `except` to find the real cause; the code reads as fully implemented
  and wired end-to-end (repository query → filter → load), which is exactly the "no-op behind a call site
  that believes it does something" shape called out for this dimension (cf. `HybridProcessor.close()`,
  already filed).
- **Siblings**: None found — `auralis/library/manager.py:201,275-278` (the deprecated `LibraryManager`
  facade's `get_recommendations`/internal `find_similar` passthrough) calls the *same* `find_similar`
  correctly (`return self.tracks.find_similar(track, limit)`, no destructuring), so the bug is isolated
  to this one call site in `integration_manager.py`.
- **Related**: Correctness angle overlaps `/audit-engine` (this is fundamentally a type-mismatch bug, not
  a written-as-a-stub placeholder) — noting here because the *observable effect* (a fully-wired-looking
  feature that never actually delivers its result) is squarely the pattern this dimension was asked to
  hunt, matching the brief's `HybridProcessor.close()` example shape. Not found in
  `AUDIT_ENGINE_2026-07-29.md`, `AUDIT_BACKEND_2026-07-29.md`, or `AUDIT_INTEGRATION_2026-07-29.md` (checked
  by grep for `auto_select_reference`/`find_similar`/`integration_manager.py` — only one unrelated hit in
  the integration report, a different `find_similar` on the fingerprint-similarity class). Not in
  `issues_all.json` either (`#2072` and `#3706` are unrelated `find_similar` issues — an N+1 query fix and
  a similarity prefilter fallback, both already closed/different code path).
- **Suggested Fix**: Change `integration_manager.py:296` to `references = repos.tracks.find_similar(track, limit=3)` (drop the tuple unpack). One-line fix; add a regression test asserting `_auto_select_reference` actually loads a reference when 0, 1, or 3+ similar tracks exist (the exact-2 case is the only one current behavior accidentally covers).

---

## Dedup notes (checked, not re-filed)

- **`GET /api/audio/formats` hardcoded format list** (`auralis-web/backend/routers/files.py:273-289`) —
  squarely a Dimension 5 "route returning hardcoded data" match (a literal `{"input_formats": [...]}`
  dict that omits 5 of 11 formats `auralis/io/formats.py`'s declared single source of truth actually
  accepts). Already filed today as `AUDIT_BACKEND_2026-07-29.md` **BE5B-N6** (Status: NEW, Severity LOW,
  same root cause, same evidence). Not re-filed here.
- **Known #4243 sibling check**: grepped `auralis/library/scanner/` and `auralis-web/backend/services/`
  for other "log-only, comment says 'this would'" no-op methods matching
  `scanner.py:375-382 _update_library_stats()` (Existing: #4243, OPEN, not re-filed). Found none —
  the only other `pass`-only bodies in those directories
  (`scanner.py:99-105 _release_scan_slot_safe`, `library_auto_scanner.py:126-136 stop()`) are legitimate
  exception-swallowing for tolerated `AttributeError`/`CancelledError`/`TimeoutError`, not stubs.
- **`useFingerprintCache.ts` mock fingerprint** (Existing: #4239, OPEN) — re-verified the DEV-only guard
  is intact and has NOT regressed: `simulateFingerprinting()` (`useFingerprintCache.ts:114-123`) still
  checks `if (!import.meta.env.DEV) { setError('Client-side fingerprinting not available'); return; }`
  before generating any mock data, so production builds cannot reach the fake-fingerprint path.
- **`AddToPlaylistMenu.tsx` "Coming soon!" reference** — the file's own header comment
  ("Fixes #4240 — this action previously showed a 'Coming soon!' toast with no API call") describes a
  **past, already-fixed** state; the current component does a real `getPlaylists()` fetch and a real
  `onAddToPlaylist()` call. Not a live stub. Confirmed the sibling `handleBulkRemove` in
  `useBatchOperations.ts:100-104` is likewise already fixed per the same #4240 — its "no backend deletion
  route yet" branch is deliberately hidden from non-favourites contexts so it is unreachable rather than a
  silent no-op, per its own comment.
- **`auralis-web/backend/services/learning_system.py`** (`LearningSystem`, `AdaptiveWeightTuner`,
  `AffinityRuleLearner`, 484 LOC) — fully-implemented, real logic (not a stub: `get_overall_accuracy()`
  etc. do genuine division-based computation, the `return 0.0` sites are legitimate empty-history guards).
  However, its *only* importer anywhere in the tree is `auralis-web/backend/monitoring/metrics_collector.py`
  — which Dimension 2's `TD2-1` already established is itself entirely unwired (zero production
  importers). So this module is transitively dead code behind an already-dead package. This is a
  Dimension 2 (dead code) concern, not a Dimension 5 (stub) one, since the code is real and correct, just
  unreachable — noted here only as an addendum to `TD2-1`'s scope, not filed as a new Dimension 5 finding.
- **`auralis/dsp/eq/masking.py::MaskingThresholdCalculator.calculate_masking`** ("Simplified masking
  calculation" comment) — verified reachable from the live WOLA/psychoacoustic-EQ path
  (`psychoacoustic_eq.py:98,177`, part of Dim2's confirmed live chain). Read the full method: it performs
  genuine FFT-bin-range slicing and a real `20*log10(peak)-20` threshold calculation per critical band —
  an honestly-labeled simplification of a full psychoacoustic model, not empty/fake data. This is an
  algorithmic-approximation quality question for `/audit-engine`, not a Dimension 5 stub.

---

## Summary

**1 NEW finding** (`TD5-1`, MEDIUM), plus the two pre-verified facts confirmed as negative results, plus
six dedup/dismissal notes recorded above so a future pass doesn't re-walk the same ground.

## Dimension 6 — Test Hygiene

Agent: Dim 6 (Test Hygiene). HEAD 09004fa2.

Findings: 5 confirmed (2 MEDIUM, 3 LOW) + 1 documented clean regression-check (no finding).

---

### TD6-1: Regression suite for closed HIGH #2076 (WebSocket TOCTOU) has been permanently erroring since 2026-07-19 on a removed attribute
- **Severity**: MEDIUM
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_audio_stream_lifecycle.py:261,333,457`; `tests/backend/test_stream_disconnect_toctou.py:155,193,229,269,320,359`
- **Status**: NEW (root cause distinct from any tracked issue — see below)
- **Age**: commit `8e6fae6f` "refactor(backend): remove write-only dead active_streams registry (#4362)", 2026-07-19 — 10 days before this audit, ~50 commits ago
- **Effort**: trivial (<=30min) — delete the assertions/tests or restore an equivalent invariant check
- **Description**: Commit `8e6fae6f` (closing #4362, itself a LOW finding that `active_streams` was a "write-only dead registry" never read by production code) deleted the `active_streams` attribute and its 6 write-sites from `AudioStreamController` and the three `stream_*` submodules. It did **not** update the two test files that assert against it. Every test that touches `ctrl.active_streams` / `controller.active_streams` now raises `AttributeError: 'AudioStreamController' object has no attribute 'active_streams'` (or, for one test, silently observes an always-empty list via a stale local variable). This is the **entire dedicated regression suite for closed HIGH issue #2076** ("WebSocket stream loop TOCTOU race") — `test_stream_disconnect_toctou.py`'s own docstring says it "fixes #2076" and lists `active_streams` lifecycle as its two headline invariants.
- **Evidence**: Ran the affected tests directly (scoped, not the whole file):
  ```
  $ python -m pytest tests/backend/test_audio_stream_lifecycle.py -k test_cleanup_on_success -vv
  FAILED ...test_cleanup_on_success - AttributeError: 'AudioStreamController' object has no attribute 'active_streams'
  FAILED ...test_cleanup_on_success - AttributeError: 'AudioStreamController' object has no attribute 'active_streams'

  $ python -m pytest tests/backend/test_stream_disconnect_toctou.py -k active_streams -vv
  FAILED test_active_streams_set_during_enhanced_stream - AssertionError: active_streams should be set before streaming begins (assert False where False = any([]))
  FAILED test_active_streams_empty_after_enhanced_stream_completes - AttributeError: ...no attribute 'active_streams'
  FAILED test_active_streams_empty_after_enhanced_stream_exception - AttributeError: ...no attribute 'active_streams'
  ```
  `git log --all -S"active_streams" -- auralis-web/backend/core/audio_stream_controller.py` shows the attribute was removed in `8e6fae6f` and never existed anywhere else (`grep -rn active_streams auralis/ auralis-web/backend/` → 0 hits, confirming the commit message's own claim).
  Note this is **not** the SEED-1 hypothesis (a `Mock` swallowing the assertion via `__contains__` making it a tautological pass) — `ctrl`/`controller` in every one of these tests is a real `AudioStreamController` instance, not a Mock, so the missing attribute raises immediately. The seed's mechanism was wrong but the underlying finding (the regression suite is dead) is confirmed by a different mechanism: it fails loudly, not silently — worse in a way, because it's one of 341 already-failing backend tests, so its specific failure reason (an orphaned rename, not a real regression) is invisible in that count and nobody has connected it back to #4362/#2076.
- **Impact**: If the TOCTOU race the tests were written to catch (#2076) ever regresses, these 8 tests will not tell anyone — they already fail unconditionally regardless of controller behavior, so a real regression and a non-regression are indistinguishable in CI output. The suite has provided zero regression coverage for #2076 for 10 days/~50 commits.
- **Siblings**: 3 tests in `test_audio_stream_lifecycle.py` (`test_cleanup_on_success` x2 classes, `test_chunk_failure_cleans_up`), 5 in `test_stream_disconnect_toctou.py` (`test_active_streams_set_during_enhanced_stream`, `test_active_streams_empty_after_enhanced_stream_completes`, `test_active_streams_empty_after_enhanced_stream_exception`, `test_active_stream_cleared_after_seek_stream`, `test_active_stream_cleared_after_seek_exception`) — 8 total.
- **Related**: #4362 (CLOSED LOW, removed the attribute), #2076 (CLOSED HIGH, the race these tests exist to guard), #3182 (CLOSED HIGH, added the lock later removed), #3179 (CLOSED LOW, keying complaint). These 8 failures are presumably already counted inside the "341 failing backend tests" figure in `AUDIT_BACKEND_2026-07-29.md` — that audit owns the raw failure count; this finding is specifically that the failures represent a *dead regression suite for a closed HIGH issue*, which is Dim 6's promotion trigger.
- **Suggested Fix**: Either (a) delete the now-meaningless `active_streams` assertions/tests since #4362 established there's no reader to protect, replacing #2076 coverage with an assertion against the real cancellation registry (`system.py`'s `_active_streaming_tasks`, per the #4362 commit message), or (b) if `active_streams`-equivalent per-stream bookkeeping is still conceptually load-bearing for TOCTOU verification, restore a minimal readable attribute. Either way, someone must consciously decide what #2076 regression coverage looks like post-#4362 — right now it's an accidental hole.

---

### TD6-2: `assert status_code in [2xx, 5xx]` + `if status_code == 200: <only real assertions>` pattern makes ~53 backend API tests unable to fail on a server crash
- **Severity**: MEDIUM
- **Dimension**: Test Hygiene
- **Location**: 53 assertion sites across 7 files (full breakdown below); representative: `tests/backend/test_artists_api.py:84-93`
- **Status**: NEW
- **Age**: pattern dates to "Phase 5C: Dual-Mode Backend Testing" / "Phase 5B.1" per file docstrings (predates this audit window; not independently git-blamed per-line given the volume, but the docstring in `test_artists_api.py` puts the migration to this pattern at the conftest.py fixture migration, well before HEAD)
- **Effort**: medium (<=1day) to fix the worst offenders (test_artists_api.py, test_albums_api.py, test_main_api.py); large (>1day) to fix all 7 files properly (requires making the fixtures deterministic so tests can assert a single expected status)
- **Description**: A systemic pattern across the backend API test suite: `assert response.status_code in [200, 500, 503]` (or similar lists mixing a 2xx with one or more 5xx), frequently followed by `if response.status_code == 200: <the only assertions that inspect the response body>`. Confirmed by reading `tests/backend/test_artists_api.py:79-147` (`TestGetArtists` — 7 of 7 tests in the class use this exact shape) that when the endpoint returns 500/503 (route crash, DB not initialized, etc.), the test executes ZERO assertions on behavior and still passes. Ran `test_get_artists_default_pagination` directly — it currently passes via the 200 branch, confirming the mechanism is live, not theoretical. The comment left in the code even says the quiet part out loud: `# 503 if library not initialized, 500 if DB issues, 200 if OK` — three completely different outcomes (including two failure modes) are treated as equally acceptable "pass" conditions with no assertion distinguishing which occurred beyond the trivial membership check.
- **Evidence**:
  ```python
  # tests/backend/test_artists_api.py:79-93
  def test_get_artists_default_pagination(self, client):
      """Test getting artists with default pagination"""
      response = client.get("/api/artists")
      # 503 if library not initialized, 500 if DB issues, 200 if OK
      assert response.status_code in [200, 500, 503]
      if response.status_code == 200:
          data = response.json()
          assert "artists" in data
          ...
  ```
  Verified this is not a one-off: same `if status_code == 200:` gating recurs in `test_main_api.py` (lines 59, 97, ...) and `test_albums_api.py` (lines 107, 122, 133, ...). Counted, via a script parsing every `status_code in [...]` list in `tests/` (193 total occurrences) for lists containing both a 2xx code and a 5xx code:
  ```
  13 tests/backend/test_player_api_comprehensive.py
  12 tests/backend/test_main_api.py
   9 tests/backend/test_artists_api.py
   9 tests/backend/test_albums_api.py
   5 tests/backend/test_similarity_api_new.py
   4 tests/backend/test_metadata_api.py
   1 tests/backend/test_library_api_comprehensive.py
  53 TOTAL
  ```
  (I checked the SEED's specific claim that `test_artwork_security.py` accepts a 500 in a security test — **that claim does not hold**: every `status_code` assertion in that file was read directly and none mixes a 2xx with a 5xx; the file's only list-form assertions are `in [403, 404]` and `in (400, 403, 404)`, both defensible auth/validation branches. That file is not part of this finding.)

  Note a second, slightly worse variant exists in `test_player_api_comprehensive.py` (13/13 sites): most have **no** follow-up body assertion at all — not even `test_artists_api.py`'s `if status_code == 200:` gating (only 2 of the ~13 sites in this file have any such gate; read lines 260-330 directly, e.g. `test_seek_valid_position`, `test_set_queue_with_tracks`). The bare `assert response.status_code in [200, 404, 500]` is the entire test body — success and 2 different failure modes are all simply "the test passed," full stop.
- **Impact**: A genuine regression that makes these endpoints 500 (e.g., an unhandled exception, a broken repository call, a bad migration) is invisible to CI in all 53 sites — the test suite reports green for a crashing route as long as the crash surfaces as one of the pre-listed codes. This is the same class of bug the dimension is chartered to find: passing tests that certify nothing about the specific behavior they claim to check (docstrings like "Test getting artists with default pagination" promise behavioral coverage the assertions don't deliver on the failure path).
- **Siblings**: All 53 sites share the identical shape; the worst-affected classes are `TestGetArtists` (test_artists_api.py, 7/7 tests in class), and the analogous album/main-api classes in test_albums_api.py / test_main_api.py which follow the same `if status_code == 200:` gate.
- **Related**: Distinct from AUDIT_BACKEND_2026-07-29's 341-failures count (these tests are currently passing, not failing) and distinct from BE9-01 (CI gate). This is purely an assertion-quality finding.
- **Suggested Fix**: For each site, either (a) make the test fixture deterministic (real in-memory DB/library fixture that always yields 200) and assert the single expected code, removing the 5xx from the acceptance list, or (b) if the endpoint's dependency truly can be legitimately absent in this test environment, split into two explicit tests — one that mocks the dependency present (asserts 200 + body shape) and one that mocks it absent (asserts the specific 503) — so every code path actually gets a behavioral assertion instead of being silently skipped.

---

### TD6-3: `test_album_pagination_completeness`/`_ordering`/`test_artist_pagination_completeness` are wired to a fixture that is unconditionally empty — they can never do anything but skip
- **Severity**: LOW (promoted from a pure "dead code" LOW; these guard no closed CRITICAL/HIGH issue, so the MEDIUM promotion trigger does not apply — see Related)
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_library_pagination_invariants.py:386-417` (`test_album_pagination_completeness`), `:420-442` (`test_album_pagination_ordering`), `:449-478` (`test_artist_pagination_completeness`)
- **Status**: NEW
- **Age**: not independently git-blamed (file predates HEAD by a wide margin; not a recent regression)
- **Effort**: trivial (<=30min) — swap the fixture parameter from `album_repo`/`artist_repo` to a populated one, or add album/artist rows to the `populated_db` fixture (currently it only inserts `Track` rows with `album=`/`artists=` string fields — worth checking whether `track_repo.add()` actually creates `Album`/`Artist` rows as a side effect; if it does, the fix is simply to reuse `populated_db` instead of the bare repo fixtures)
- **Description**: `album_repo` and `artist_repo` (lines 69-78) are built directly on the bare `test_db` fixture — an empty in-memory SQLite DB with tables created but zero rows. No fixture in this file ever inserts an `Album` or `Artist` row directly (only `populated_db` inserts `Track` rows, keyed by string `album`/`artists` fields passed to `track_repo.add()`). The three tests above call `album_repo.get_all(...)` / `artist_repo.get_all(...)` first to get `total`, find `total == 0`, and `pytest.skip(...)`. Since nothing ever populates these repos, `total` is unconditionally 0 on every run — the `pytest.skip` is not a conditional guard, it is unreachable-else-branch: the pagination/duplicate-detection logic below it (the entire stated purpose of the test) has a 0% execution rate.
- **Evidence**: Ran directly:
  ```
  $ python -m pytest tests/backend/test_library_pagination_invariants.py -k "album_pagination or artist_pagination_completeness" -rs -v
  test_album_pagination_completeness SKIPPED
  test_album_pagination_ordering SKIPPED
  test_artist_pagination_completeness SKIPPED
  SKIPPED [1] ...:397: No albums in test database
  SKIPPED [1] ...:428: No albums in test database
  SKIPPED [1] ...:458: No artists in test database
  ```
  Contrast with the SEED-3 hypothesis: I read `tests/auralis/test_audio_processing_invariants.py:98,119,162` in full (the file the seed flagged as containing the project's most important sample-count invariant) and found **no skip/return guard of any kind** — `grep -n "pytest.skip\|if not \|return$"` returns zero hits for those tests; they run unconditionally against synthetically generated (never-empty) sine-wave fixtures. **That specific seed claim is refuted** — the sample-count invariant is not a no-op. The mechanism the seed predicted (empty-fixture-guarded "CRITICAL INVARIANT" tests) is real, but only manifests in `test_library_pagination_invariants.py`, and only for the album/artist tests, not the file-level "CRITICAL INVARIANT"-labeled track test at line 129 (`test_pagination_returns_all_items_exactly_once`, which correctly uses the 100-row `populated_db` fixture and is not skip-guarded).
- **Impact**: Album/artist pagination has zero regression coverage from this file — a real off-by-one, duplicate, or missing-item bug in `AlbumRepository.get_all`/`ArtistRepository.get_all` pagination will never be caught here; the tests exist as documentation of intent only. Lower severity than TD6-1/TD6-2 because (a) it manifests as a visible SKIPPED in test output, not a false PASS, so it is at least honest about not running, and (b) it does not guard a closed CRITICAL/HIGH issue per `issues_all.json` (no album/artist-pagination-specific issue found).
- **Siblings**: The remaining `pytest.skip("No X in database")` guards later in the same file (lines 499 "No search results", 568 "No favorites", 608 "No recent tracks", 701/728 "No tracks in database", 795 "No popular tracks", 837 "Need at least 2 popular tracks") are all keyed off `populated_db` (100 real tracks), so `total == 0` is not the normal case for those — they are legitimate defensive guards for genuinely rare edge cases (e.g. `get_recent`/`get_popular` depending on whether earlier lines in the same test successfully recorded plays), not unconditional dead code, and are not included in this finding.
- **Related**: Distinct mechanism from, but same file as, TD6-1 (both are "test infrastructure drifted from what it's testing"). Not a promotion-eligible closed-CRITICAL/HIGH regression guard.
- **Suggested Fix**: Change the two album tests and the one artist test to take `populated_db` (or a new fixture that also creates `Album`/`Artist` rows) instead of the bare `album_repo`/`artist_repo`, so `total > 0` and the pagination/duplicate-detection assertions actually execute at least once.

---

### TD6-4: `useLibraryQuery`'s pagination/`fetchMore` tests validate the mock's canned response, not what the hook actually requested — an offset-not-advancing regression would still pass
- **Severity**: LOW (false-confidence mechanism confirmed and real, but the endpoint-routing/search-encoding paths in the same file ARE correctly covered — see Evidence — so this is a partial, not whole-suite, gap; does not meet any MEDIUM promotion trigger)
- **Dimension**: Test Hygiene
- **Location**: `auralis-web/frontend/src/hooks/library/__tests__/useLibraryQuery.test.ts` — `describe('pagination')` block lines 141-227, `describe('fetchMore (infinite scroll)')` block lines 229-~430
- **Status**: NEW
- **Age**: not individually git-blamed (large stable test file, `#4407` comment at line ~360 shows recent-ish maintenance in this exact section, so it is actively maintained, not abandoned)
- **Effort**: small (<=2h) to add `mockGet.mock.calls[N][0]` URL/param assertions to the ~7 tests in these two `describe` blocks
- **Description**: The seed hypothesis ("queue-hook tests mock `useRestAPI` wholesale and never assert the URL or request body") does **not** hold for the queue hooks I checked — see the refutation below — but the identical failure mode is real in a sibling file, `useLibraryQuery.test.ts`, specifically for pagination/infinite-scroll. Each test in the `pagination` and `fetchMore` blocks builds a `mockGet` that returns **hardcoded** `{items, total, offset, limit, hasMore}` payloads (via `mockResolvedValueOnce`/`mockResolvedValue`) and then asserts only on `result.current.*` (the hook's derived state) — never on what arguments `mockGet` was actually called with. Because the canned responses are keyed by *call order*, not by the request `mockGet` received, a hook bug that requests the same page twice, never advances `offset`, or drops the `limit` parameter would still produce the exact same test outcome, since the mock ignores its input and returns the next canned response regardless.
- **Evidence**:
  ```javascript
  // useLibraryQuery.test.ts:234-277 — "should append new items when fetchMore is called"
  const mockGet = vi.fn()
    .mockResolvedValueOnce({ items: firstPageTracks, total: 200, offset: 0, limit: 50, hasMore: true })
    .mockResolvedValueOnce({ items: secondPageTracks, total: 200, offset: 50, limit: 50, hasMore: true });
  ...
  await act(async () => { await result.current.fetchMore(); });
  expect(result.current.data).toEqual([...firstPageTracks, ...secondPageTracks]);
  // <- no assertion anywhere that fetchMore() called mockGet with offset=50
  ```
  Confirmed by reading the whole file (1271 lines) and grepping every URL-inspecting assertion: `grep -n "mock.calls\[" useLibraryQuery.test.ts` → only 7 hits total (lines 475, 504, 722, 752, 783, 1002, 1033), all in the `search`/`custom endpoint`/`resource-type routing` `describe` blocks — **zero** in the `pagination` (141-227) or `fetchMore` (229-430) blocks, which instead rely exclusively on `toHaveBeenCalledTimes` (call *count*, not call *arguments*: lines 323, 357) and `result.current.*` state checks.
  **Refuting the seed's specific claim about queue hooks**: I read `useQueueHistory.test.ts` in full — it asserts `expect(mockPost).toHaveBeenCalledWith('/api/player/queue/history', {operation: 'shuffle', state_snapshot: {...}, ...})` (line 157), i.e. exactly the URL+body check the seed predicted was missing. I also read `useQueueMutations.optimistic.test.ts` in full — it doesn't check mock call args at all, but instead asserts real Redux store state transitions before/after the mocked request resolves/rejects (optimistic update + rollback), which is a stronger behavioral check than a call-args assertion, not a weaker one. `usePlaybackQueue.test.ts` (1162 lines, 28 tests) has 38 `toHaveBeenCalledWith` assertions. None of the three queue-hook files exhibit the pattern the seed described.
- **Impact**: A regression in `fetchMore`'s offset-advancement logic (exactly the class of bug `#4407`, referenced two tests below this gap, already had to fix once) could reintroduce a duplicate-page or stuck-pagination bug while every test in this section stays green, because the tests never look at what was actually requested.
- **Siblings**: All 3 tests in the `fetchMore` block (`should append new items...`, `should not fetch more when already loading`, `should not fetch more when hasMore is false`) plus the 3 in `pagination` (`should track offset and limit correctly`, `should calculate hasMore correctly`, `should know when at end of results`) share the same gap.
- **Related**: `#4407` (referenced at line ~361 of the same file) is the exact bug class (hasMore/offset arithmetic) this gap would fail to catch if it recurred in the request-construction path rather than the response-arithmetic path.
- **Suggested Fix**: In each `fetchMore`/pagination test, add `expect(mockGet.mock.calls[1][0]).toContain('offset=50')` (or equivalent) after the second call, mirroring the pattern already used correctly in the file's `search`/`custom endpoint` tests just a few hundred lines away.

---

### Regression check (negative result): `tests/concurrency/test_thread_safety.py` xfail hygiene — PREVIOUSLY FIXED, NOT REGRESSED
- **Severity**: N/A — no finding, documenting a clean re-verification per SEED instructions
- **Dimension**: Test Hygiene
- **Location**: `tests/concurrency/test_thread_safety.py`
- **Status**: Existing: #4548 (CLOSED 2026-07-25, "MEDIUM - 13 strict xfails disable the entire thread-safety suite with no issue reference and no owner" — this is the same issue as the prior audit's TD6-1)
- **Description**: The prior tech-debt audit (2026-07-25, TD6-1) found 13 strict xfails in this file with placeholder reasons ("API compatibility - needs updates") and no issue reference. SEED_tests.md asked me to re-verify after 128 commits (READ only — this file hangs if executed as a whole; I did not run it). Read the whole file's marker lines via targeted grep: there are now only **7** `@pytest.mark.xfail` sites (not 13), and **every one** cites `#4548` with a specific, technically accurate, non-placeholder reason, e.g. `"AdaptiveCompressor.__init__ now requires a 'settings' argument; test still calls the old no-arg form (see #4548)"`. Spot-checked this specific claim against the real source: `auralis/dsp/dynamics/compressor.py:32` — `AdaptiveCompressor.__init__(self, settings: CompressorSettings, sample_rate: int)` — confirmed accurate, not a rubber-stamped excuse.
- **Evidence**: `grep -c "@pytest.mark.xfail" tests/concurrency/test_thread_safety.py` → 7; `grep "@pytest.mark.xfail" ... | grep -v "#4548"` → 0 results (all 7 cite the issue).
- **Impact**: None — this is confirmation the fix holds. Filing so the audit trail shows the check was performed rather than silently skipped.
- **Related**: #4548 (CLOSED MEDIUM). No promotion — this is the opposite of a regression.

---

### TD6-5: `try: <assertion> / except Exception: pytest.skip(...)` converts crashes (including the exact bug classes the test's own docstring names) into silent skips, across 13 sites in 6 boundary/integration files
- **Severity**: LOW (systemic pattern, but no single site is independently verified to currently guard a closed CRITICAL/HIGH issue — see Related; documenting per the dimension's false-confidence-adjacent framing rather than via a promotion trigger)
- **Dimension**: Test Hygiene
- **Location**: `tests/backend/test_boundary_max_min_values.py:188,215,233,254,419,578`; `tests/backend/test_boundary_exact_conditions.py:399,472,524`; `tests/backend/test_boundary_empty_single.py:543`; `tests/boundaries/test_chunked_processing_boundaries.py:786`; `tests/integration/test_api_workflows.py:812`; `tests/integration/test_repositories.py:258`
- **Status**: NEW
- **Age**: not individually git-blamed (widespread, stable pattern across the boundary-test suite; not a recent introduction)
- **Effort**: small (<=2h) per file to narrow `except Exception` to the specific expected exception type(s), or medium (<=1day) across all 6 files
- **Description**: A recurring shape in the boundary-test suite: a `try:` block containing the test's actual assertion(s) (the thing the test exists to check), followed by `except Exception as e: pytest.skip(f"<feature> not supported: {e}")`. Because the `except` clause catches the base `Exception` class rather than a specific expected exception (e.g. `NotImplementedError`, a specific `ValueError`), **any** unrelated crash inside `processor.process()` / `manager.add_track()` — a `ZeroDivisionError`, an `IndexError`, an `AttributeError` from a refactor, an actual regression in the exact invariant under test — is caught and reported as SKIPPED rather than FAILED. A skip reads as "environment/feature gap, not my problem" to a human scanning CI output; a regression hiding behind this pattern gets exactly that undeserved benefit of the doubt.
- **Evidence**: The clearest instance, `tests/backend/test_boundary_max_min_values.py:196-216` (`test_one_sample_audio`):
  ```python
  def test_one_sample_audio():
      """
      BOUNDARY: Audio with exactly 1 sample.
      Common bugs: Division by zero, buffer underrun.
      """
      ...
      audio = np.array([[0.5, 0.5]])
      try:
          result = processor.process(audio)
          # If supported, output is an ndarray preserving the sample count (#4049).
          assert isinstance(result, np.ndarray)
          assert len(result) == len(audio)
      except Exception as e:
          pytest.skip(f"1-sample audio not supported: {e}")
  ```
  The docstring literally names "Division by zero" as the bug class this test is meant to catch, then the `except Exception` clause is broad enough to catch a `ZeroDivisionError` and silently skip instead of failing — the opposite of the stated intent. Confirmed via a script matching `except Exception as \w+:` followed within 3 lines by `pytest.skip` across `tests/**/*.py`: 13 matches across exactly the 6 files listed above (script and counts re-run twice for verification: 13 both times). Contrast with the legitimate uses of the same `pytest.skip(f"...")` idiom elsewhere in the suite (`tests/edge_cases/test_resource_exhaustion.py:111,227`) which catch the **specific** `MemoryError`/`OverflowError` they're designed to tolerate, not bare `Exception` — those are not part of this finding.
- **Impact**: Reduces the boundary suite's ability to surface exactly the crash-class regressions (off-by-one, division-by-zero, buffer-underrun) it was written to catch at extreme input sizes (1-sample, 10-sample, sub-frame, very-long, max-title-length audio/library inputs). A future regression in `HybridProcessor.process()` at these edge sizes would present as a new SKIPPED test, not a new FAILED test, and is more likely to be dismissed during a CI review pass.
- **Siblings**: All 13 sites share the identical `try/except Exception/pytest.skip` shape; heaviest concentration in `test_boundary_max_min_values.py` (6 of 13) and `test_boundary_exact_conditions.py` (3 of 13).
- **Related**: `#4049` (CLOSED LOW, "31 tests with smoke-only assert X is not None assertions") is a different but adjacent test-hygiene debt class in the same boundary-test files (one of these very functions' comments cites it), not the same mechanism. No single site here is confirmed to currently guard a closed CRITICAL/HIGH regression, so the MEDIUM promotion trigger is not invoked; flagged at LOW as a systemic pattern per the dimension's remit to prioritize false-confidence mechanisms even where a formal promotion trigger doesn't strictly apply.
- **Suggested Fix**: Replace `except Exception` with the specific exception type each test is actually tolerant of (or, if truly nothing is known to be expected, use `pytest.mark.xfail(raises=..., strict=False)` instead of a runtime catch-all, so an unexpected exception type still fails loudly instead of being folded into "skip").

---

## Dimension 7 — Stale Documentation & Comments

Project root: /mnt/data/src/matchering. HEAD 09004fa2. Status: COMPLETE.

**Findings filed**: TD7-1 through TD7-8 (8 entries). 2 MEDIUM (TD7-1 SEED-A, TD7-2 SEED-B — both promoted per the "misled an audit in the last 90 days" trigger), 6 LOW. No HIGH/CRITICAL.

**Version drift (SEED-D) — checked, CLEAN, no finding filed**: `auralis/version.py` (`1.5.1`) matches `pyproject.toml:7`, `package.json:3`, `desktop/package.json:3`, `auralis-web/frontend/package.json:3`, `README.md` (correctly labeled "unreleased recovery milestone"), `docs/versions/VERSIONING_STRATEGY.md:7`, `docs/MASTER_ROADMAP.md:3,22`, and `docs/releases/CHANGELOG.md`'s `[Unreleased]` target. The only outlier, `mutants/pyproject.toml` (`version = "0.1.0"`, name `"matchering-player"`), is a `mutmut`-generated working copy — gitignored (`.gitignore:92`), untracked, not a maintained doc, out of scope. Version hygiene here is good; not padding this dimension with a non-finding.

---

### TD7-1: `_audit-common.md` "Test Baselines" section falsely claims the backend pytest baseline is "checked in and CI-enforced" — and is internally self-contradictory
- **Severity**: MEDIUM
- **Dimension**: Stale Documentation & Comments
- **Location**: `.claude/commands/_audit-common.md:78-92` (section "Test Baselines — Use the Tracked Files, Not a Worktree Diff")
- **Status**: NEW
- **Age**: unable to git-blame precisely without altering repo state assumptions; section references #4562/#4640 (recent, this-week commits per `git log`)
- **Effort**: trivial (<=30min) — rewrite one section, ~4 lines
- **Description**: Line 80 asserts "As of #4562 / #4640 the baselines are checked in and CI-enforced." Line 91 doubles down: "CI **does** now run vitest and pytest. Any audit note claiming 'no CI runs the tests' is out of date." But the very next table row (line 85) contradicts this in the same breath: "*pytest-baseline.json* at the repo root — generate it with `scripts/check_pytest_baseline.py` if absent (**it is not tracked yet**)." Verified independently:
  - `pytest-baseline.json` does not exist at repo root and is not in `git ls-files` (confirmed).
  - `.github/workflows/backend-tests.yml`'s final gating step is `python scripts/check_pytest_baseline.py pytest-results.xml`, which cannot succeed without the (nonexistent, untracked) baseline file.
  - `gh run list --workflow=backend-tests.yml --limit 100` → 99 failure / 1 cancelled / 0 success. The backend CI gate has never passed since it was added.
  - By contrast the frontend half of the same table (line 84) is accurate: `auralis-web/frontend/test-baseline.json` IS tracked, and `frontend-test.yml`'s recent runs include a success (2026-07-29T18:33Z). So the section is half-true, half-false, and asserts both in the same row.
- **Evidence**: `.claude/commands/_audit-common.md:80` vs `:85` vs `:91` (quoted above, verbatim).
- **Impact**: This is the shared protocol file (`_audit-common.md`) that every audit skill in the suite reads first. A false "CI enforces this, don't worry" claim misdirects any audit that (reasonably) trusts it into treating backend test failures as pre-baselined/expected rather than investigating the gate itself. This is exactly what happened in this suite: `AUDIT_BACKEND_2026-07-29 BE9-01` had to independently re-derive that the gate has never worked. The claim actively cost audit effort within the last 90 days (today), which is the literal MEDIUM promotion trigger ("Stale doc/audit baseline that has misled an audit in the last 90 days").
- **Siblings**: Grepped every `.claude/commands/*.md` for "baseline", "pytest-baseline", "checked in", "CI-enforced", "CI does". Only `_audit-common.md` makes the false claim. `audit-frontend.md:140` and `audit-regression.md:81` both reference this section but only restate the (true) frontend baseline mechanics / the (true) "generated by `scripts/check_pytest_baseline.py`" fact — neither repeats the false "checked in and CI-enforced" assertion. So this is a single-location finding, not a multi-sibling one; the false claim does not fan out beyond its origin.
- **Related**: `AUDIT_BACKEND_2026-07-29` BE9-01 (owns the CI-gate/correctness half: the gate `sys.exit(1)`s on `FileNotFoundError`, 341 tests failing on master). This finding is the documentation half only.
- **Suggested Fix**: Rewrite `_audit-common.md:80-92` to state plainly that the backend baseline is NOT checked in (unlike the frontend one), that the CI gate consequently cannot pass, and to point at BE9-01 for the underlying gate bug rather than asserting it works. Until `pytest-baseline.json` is generated and committed, restore the older "compare against a clean worktree" guidance for the backend suite specifically.

---

### TD7-2: `_audit-common.md` and `audit-backend.md` both assert a false "two live `WAVEncoderError` classes" duplication hazard
- **Severity**: MEDIUM
- **Dimension**: Stale Documentation & Comments
- **Location**: `.claude/commands/_audit-common.md:42`; `.claude/commands/audit-backend.md:34`
- **Status**: NEW
- **Effort**: trivial (<=30min)
- **Description**: `_audit-common.md:42` (Project Layout table, Backend Encoding row): "*auralis-web/backend/core/encoding/ wav_encoder.py (DIFFERENT content from the copy above) + atomic_io.py. **Two live `WAVEncoderError` classes exist**; an `except` on one will not catch the other. Treat as a known duplication hotspot.*" `audit-backend.md:34` repeats it near-verbatim: "*Two distinct `WAVEncoderError` classes result — check every `except WAVEncoderError` resolves to the class the raising path actually uses.*" Both are false. There is exactly one `WAVEncoderError` class in the entire backend tree.
- **Evidence**:
  ```
  grep -rn "class WAVEncoderError" auralis-web/backend/
    auralis-web/backend/encoding/wav_encoder.py:31:class WAVEncoderError(Exception):
  ```
  `auralis-web/backend/core/encoding/wav_encoder.py` defines only `class WAVEncoder` (line 24, the encoder itself) and raises stdlib `ValueError`/`OSError` on failure — it defines no custom exception class at all, let alone a second `WAVEncoderError`. Every actual consumer of `WAVEncoderError` (`core/chunked_processor.py:785,794`, `core/processing_engine.py:66-67`, `encoding/__init__.py:11,15`) imports the single class from `encoding.wav_encoder`. The "two classes, except-mismatch" hazard described in both skill files does not exist — the two `wav_encoder.py` files are a real duplication (different `WAVEncoder` implementations, one legacy pure-function style, one class-based), but not the specific exception-swallowing hazard claimed.
- **Impact**: Sends any backend/security/concurrency audit hunting for a phantom except-clause bug that cannot occur, wasting investigation time on a fabricated hazard while the real, narrower duplication (two different `WAVEncoder` implementations under different module paths) is under-described.
- **Siblings**: Exactly these two locations (`_audit-common.md:42`, `audit-backend.md:34`) — grepped all of `.claude/commands/*.md` for "WAVEncoderError" and "Two live"/"two distinct" phrasing; no other file repeats it.
- **Related**: `AUDIT_TECH_DEBT` Dimension 3 (Duplication) — TD3-1 covers the real, narrower duplication one level down (two different `WAVEncoder` classes/implementations). Do not restate that finding here; this finding is scoped to the false exception-class-count claim in the two skill files.
- **Suggested Fix**: In both files, replace the "two live `WAVEncoderError` classes" sentence with an accurate description: one `WAVEncoderError` class (`encoding/wav_encoder.py:31`), used correctly everywhere; the actual duplication is two different `WAVEncoder` *implementations* (legacy functional style in `encoding/`, class-based in `core/encoding/`) — point at TD3-1 for that.

---

### TD7-3: `CLAUDE.md` "Codebase Map" and `_audit-common.md` "Project Layout" quote mutually inconsistent structural counts, and both disagree with the live tree
- **Severity**: LOW
- **Dimension**: Stale Documentation & Comments
- **Location**: `CLAUDE.md` (Codebase Map section, `auralis/analysis/` and test-count lines); `.claude/commands/_audit-common.md` (Project Layout table, ~lines 20-60)
- **Status**: NEW
- **Effort**: trivial (<=30min) — update both to a single recomputed set of numbers, ideally with a comment pointing at the `find`/`grep` command used so the next audit can re-verify instead of hand-editing
- **Description**: Hand-verified a representative sample of the pre-computed SEED_counts.md table myself (not just trusted it):
  ```
  find auralis/analysis -name '*.py' | wc -l                                    → 56
  find auralis-web/backend/routers -name '*.py' | wc -l                          → 26
  grep -c 'app.include_router(' auralis-web/backend/config/routes.py (excluding
    the line-36 comment "their `include_router()` calls are")                   → 20
  find tests -name 'test_*.py' -o -name '*_test.py' | wc -l                      → 448
  grep -rn 'def test_' tests --include='*.py' | wc -l                           → 5,612 (SEED said ~5,610, consistent)
  find docs -mindepth 1 -maxdepth 1 -type d | wc -l                              → 19
  find docs -name '*.md' | wc -l                                                 → 507 (SEED said 506; off by one, negligible drift)
  ```
  Results confirm SEED_counts.md's table:
  | Metric | Live | `CLAUDE.md` | `_audit-common.md` |
  |---|---:|---:|---:|
  | `auralis/analysis/` .py files | 56 | 56 (correct) | 45 (STALE) |
  | Registered routers (`include_router` calls) | 20 | 19 (STALE) | 20 (correct) |
  | Test files (`test_*.py`/`*_test.py`) | 448 | 391 (STALE) | 501 (STALE) |
  | Test functions (`def test_*`) | ~5,612 | ~5,400 (STALE) | ~5,600 (correct) |
  | `docs/` topic dirs (depth 1) | 19 | 21 (STALE) | — (not quoted) |
  Neither file is uniformly more accurate than the other — each is right on some rows and wrong on others — so an audit or contributor cannot safely prefer one source over the other; both must be corrected independently, from the live tree, not from each other.
- **Evidence**: See commands and results above; also cross-checked against `/tmp/audit/tech-debt/SEED_counts.md` (orchestrator-precomputed, matches my independent recompute).
- **Impact**: These counts are cited as scene-setting context at the top of nearly every audit skill invocation in this suite (`_audit-common.md` is `READ THESE FIRST` for all 10 dimensions) and in `CLAUDE.md` (read on every session start per the harness). Wrong counts don't break anything directly, but they erode trust in the rest of the document's claims and have already produced this exact dimension's SEED-C lead — i.e., this class of drift has now cost audit cycles twice (2026-07-25 audit implicitly, and this one explicitly).
- **Siblings**: Both `CLAUDE.md` and `_audit-common.md` maintain **independent, duplicate copies** of the same "Codebase Map"/"Project Layout" structural summary. This is itself the root cause: two hand-maintained prose tables describing the same tree will drift apart every time either one is edited without the other. Consolidating to one canonical source (with the other referencing it) would prevent recurrence, not just fix today's numbers.
- **Related**: none (this is exactly the seeded SEED-C lead, independently re-verified rather than copied verbatim).
- **Suggested Fix**: Either (a) make one of the two files canonical for structural counts and have the other say "see X for current counts" instead of duplicating numbers, or (b) add a `scripts/` helper that regenerates both tables' numeric cells from `find`/`grep` so they can never diverge, similar to how `sync_version.py` propagates the version string.

---

### TD7-4: The path-validation gate covers 11 of 507 `docs/` markdown files (2.2%); applying its own rule to the remaining "current" docs finds ~278 stale path/symbol references across 51 files — TD7-1 (2026-07-25, 128 stale) was only partially acted on
- **Severity**: MEDIUM (promotion: this is a stale-baseline / gate-coverage claim that has misled this exact audit suite — `_audit-common.md` presents the gate as "the structural fix for stale-path drift" with no caveat about scope)
- **Dimension**: Stale Documentation & Comments
- **Location**: `.claude/commands/_audit-validate.sh:78-89` (the `skill_files`/`link_files` arrays — only `docs/architecture/*.md` (3 files) + `docs/subsystems/*.md` (4 files) + `CLAUDE.md` + `README.md` + `auralis-web/backend/WEBSOCKET_API.md` = 11 files are checked); every other file under `docs/` (496 of 507)
- **Status**: Regression of / still-open from AUDIT_TECH_DEBT_2026-07-25 (TD7-1)
- **Age**: TD7-1 filed 2026-07-25; the gate's own comments (`_audit-validate.sh:38-40`) attribute the partial extension to `#4547` ("the authoritative docs tree, which rotted unchecked while the gate reported PASS over the skill files alone")
- **Effort**: small (the gate mechanism itself is proven — extending its file list further is cheap); the underlying doc fixes are medium-to-large given the volume
- **Description**: `_audit-validate.sh` explicitly documents (its own comment, line ~92) that it deliberately excludes `docs/development/` and `docs/guides/` as "historical plan/audit snapshots whose purpose is to record what was deleted." Extending that same logic to the equally dated/historical `docs/archive/` (301 files), `docs/audits/` (23 files), and `docs/releases/` (12 files) leaves a **108-file "current" subset** of `docs/` (features, frontend, deployment, getting-started, optimization, security, testing, troubleshooting, ui_audit, versions, plus the repo-root `docs/MASTER_ROADMAP.md`, `docs/PACKAGE_MIGRATION_2026-02-21.md`) that is *not* flagged as historical-by-design, yet only 7 of those 108 are gate-covered (the `docs/architecture` + `docs/subsystems` files). I wrote a throwaway script (`/tmp/audit/tech-debt/dim7_validate_live_docs.sh`) that copies `_audit-validate.sh`'s exact `should_skip`/`expand_braces`/`path_exists` functions verbatim and applies them to all `docs/**/*.md` files outside the five historical dirs.
  - **Result**: 931 backticked path refs checked, **278 STALE**, spread across **51 of the 108 files** (47%).
  - **Hand-verification** (I checked ~20 of the 278 hits individually, across 4 files — roughly 7% of the raw count, not the full set):
    - `docs/security/WEBSOCKET_SECURITY_FIX_2156.md:35` references `auralis-web/backend/websocket_security.py`; the real file is `auralis-web/backend/websocket/websocket_security.py` (moved into a subpackage). Genuinely stale.
    - `docs/security/PATH_TRAVERSAL_FIX_2069.md:11` references `auralis-web/backend/path_security.py`; the real file is `auralis-web/backend/security/path_security.py`. Genuinely stale.
    - `docs/MASTER_ROADMAP.md:113` references `batch/variation.py` — no such file exists anywhere in the tree; the variation-dims logic actually lives in `auralis/analysis/fingerprint/metrics/variation_metrics.py` (`class VariationMetrics`). Genuinely stale, and this file is explicitly a *current*, actively-maintained doc (it opens "Current version: 1.5.1, unreleased recovery milestone", cross-referenced by SEED-D/TD7 version check above).
    - `docs/MASTER_ROADMAP.md:134` references `content/recommendations.py` (`RecommendationEngine`) — no such file or class exists; the real implementation is `auralis-web/backend/services/recommendation_service.py` (`class RecommendationService`). Genuinely stale (both path and symbol name wrong).
    - `docs/getting-started/START_HERE.md:3` — flagged 5 stale refs, but on inspection this file **already documents them as dead** with an explicit "2026-07-08 correction" note explaining the five companion docs don't exist and pointing readers to the real design-system tokens instead. This is a **false positive** for "rot" — it is a deliberately preserved, self-correcting historical note, not neglect. Counts toward the 278 raw figure but is not genuine debt.
  - So the true rate is somewhere below 278/931 but I did not hand-check the other ~93% of hits (worst offenders by stale-ref count, unverified beyond the grep-level pattern match: `docs/frontend/analysis/*` (6 files), `docs/ui_audit/*` (7 files), `docs/testing/MUTATION_TESTING_GUIDE.md` (7 refs to `tests/mutation/*` files that may or may not still exist under that name)).
- **Evidence**: full STALE listing at `/tmp/audit/tech-debt/dim7_live_docs_output.txt` (Bash-tool generated, not committed to the repo); script at `/tmp/audit/tech-debt/dim7_validate_live_docs.sh`.
- **Impact**: `_audit-common.md`'s Methodology section and this suite's Dim 10 both point at `_audit-validate.sh` passing clean as evidence the doc-rot problem is handled; it is only handled for 2.2% of `docs/`. TD7-1's two structural recommendations (extend the gate further; archive `docs/guides/` so the historical/current boundary is enforced by directory location, not a code comment) were **not both done** — the gate extension partially landed (#4547 added architecture/subsystems/CLAUDE.md/README.md/WEBSOCKET_API.md), but `docs/guides/` was never archived and remains 46 files deep with real stale refs of its own (not counted in the 278 above since it's in the excluded set), and no count-recomputation check was added (see TD7-3, still open).
- **Siblings**: n/a — this is a coverage-gap finding, not a repeated-prose finding.
- **Related**: `AUDIT_TECH_DEBT_2026-07-25` TD7-1 (this finding is its 2026-07-29 follow-up: confirms the gap persists at a similar order of magnitude — 278 vs 128 previously, over a larger "current" scope since I additionally excluded archive/audits/releases where TD7-1's methodology is not fully documented in the report). Dim 10 owns whether `.claude/commands/audit-*.md` skill files themselves cite stale dimension counts — not duplicated here.
- **Suggested Fix**: (1) Physically move `docs/guides/` (or at least its clearly-dated snapshot files) into `docs/archive/guides/` so the historical/current boundary is structural, not a comment in a validation script. (2) Extend `_audit-validate.sh`'s `skill_files`/`link_files` arrays to include the 108-file "current" set identified above (features, frontend, deployment, getting-started, optimization, security, testing, troubleshooting, ui_audit, versions, plus root-level roadmap docs) so it stops reporting false-clean. (3) Fix the two hand-verified real cases above first (`websocket_security.py`, `path_security.py` subpackage moves; `MASTER_ROADMAP.md`'s two dead module refs) as a quick down payment.

---

### TD7-5: `CLAUDE.md`'s Codebase Map calls `auralis/dsp/stages.py` "DSP pipeline entry (main())" — the module is dead, `main()` has zero production callers, and the pipeline's real entry point is elsewhere
- **Severity**: LOW
- **Dimension**: Stale Documentation & Comments
- **Location**: `CLAUDE.md:42` (`├── stages.py                   DSP pipeline entry (main())`)
- **Status**: NEW (doc half of a dead-code finding Dimension 2 owns)
- **Effort**: trivial (<=30min) — one line correction
- **Description**: Dimension 2 (`/tmp/audit/tech-debt/dim_2.md`, finding TD2-2) established that `auralis/dsp/stages.py::main()` is a "Matchering 2.0"-lineage reference-matching pipeline (LUFS/RMS matching, soft clipping) with **zero production callers** anywhere in the codebase, and that its only test importer (`tests/auralis/core/test_core.py::test_dsp_stages_functionality`) does `from auralis.dsp.stages import (MasteringStage, PreprocessingStage, ProcessingStage)` inside a `try/except ImportError: pytest.skip(...)` — and none of those three class names exist in `stages.py` (`grep -n "class \|^def " auralis/dsp/stages.py` shows only `def main`). The test has therefore `ImportError`d and silently skipped on every run, never once exercising the module. I independently re-ran the same grep to confirm Dim 2's claim before filing this doc-half finding.
- **Evidence**: `CLAUDE.md:42` calls it "DSP pipeline entry (main())" — prose that tells a reader this is *the* place execution starts for the DSP pipeline. It is not: it has no callers, and the three-class import the one test relies on doesn't exist in the file at all.
  ```
  grep -n "class \|^def " auralis/dsp/stages.py
    → def main(...)   (only definition in the file)
  ```
- **Impact**: Anyone onboarding via `CLAUDE.md`'s Codebase Map (the project's primary orientation doc, read at the start of every session per the harness) is pointed at a dead reference-matching tool and told it is where DSP processing begins — the real entry is `auralis/core/hybrid_processor.py` (`HybridProcessor`, per the same Codebase Map's own "Architecture Flow" section) or the per-stage pipeline under `auralis/core/stages/` (a same-named-but-unrelated package audited separately by the engine dimension). The name collision (`auralis/dsp/stages.py` vs `auralis/core/stages/`) compounds the confusion this line already causes.
- **Siblings**: none — single line in a single file.
- **Related**: `AUDIT_TECH_DEBT` Dimension 2, TD2-2 (owns the dead-code/reachability finding and the deletion recommendation for the module itself, its `__init__.py` re-export, and the always-skipping test).
- **Suggested Fix**: Once TD2-2 is resolved (module deleted or repurposed), update `CLAUDE.md:42`'s Codebase Map row to either remove the `dsp/stages.py` line entirely or, if the file is kept as a standalone dev tool per TD2-2's suggestion, redescribe it accurately (e.g. "standalone reference-matching CLI, not part of the runtime pipeline") instead of "DSP pipeline entry (main())".

---

### TD7-6: `WEBSOCKET_API.md` documents "30-second chunks" throughout — the actual, single-source-of-truth chunk duration is 15 seconds (10s interval / 5s overlap); the doc's own "Last Updated" header is also 9 months stale despite a 3-day-old edit
- **Severity**: LOW
- **Dimension**: Stale Documentation & Comments
- **Location**: `auralis-web/backend/WEBSOCKET_API.md:3` (header), `:421-423`, `:452-453` (payload field comments)
- **Status**: NEW (confirms a lead already flagged in project memory — "WEBSOCKET_API stale on chunk size" — with the exact current numbers)
- **Age**: file last touched 2026-07-26 (commit `89945612`) per `git log`, yet the stale content survived that edit; header still reads "Last Updated: October 24, 2025"
- **Effort**: trivial (<=30min) — 5 numeric/comment corrections
- **Description**: Three spots in the `audio_stream_start` and `audio_chunk_meta` message docs describe 30-second chunks:
  ```
  :421   "total_chunks": number,    // Total 30-second chunks in the stream
  :422   "chunk_duration": number,  // Seconds per chunk (typically 30)
  :452   "chunk_index": number,      // Which 30-second chunk this frame belongs to (0-based)
  ```
  The authoritative constant, per `auralis-web/backend/core/chunk_boundaries.py:19-21` (explicitly labeled "SINGLE SOURCE OF TRUTH"), is:
  ```python
  CHUNK_DURATION = 15.0    # seconds - actual chunk length
  CHUNK_INTERVAL = 10.0    # seconds - playback interval
  OVERLAP_DURATION = 5.0   # seconds - overlap for natural crossfades
  ```
  And the emitted wire value is not a doc guess — `auralis-web/backend/core/chunked_processor.py:351,566,776` construct the `audio_stream_start`/`audio_chunk_meta` payloads with `chunk_duration=CHUNK_DURATION` (i.e., `15.0`), so the field genuinely carries `15`, not `30`, at runtime. The doc's own header timestamp ("Last Updated: October 24, 2025") is itself stale — the file was edited as recently as 2026-07-26 (3 days before this audit) without the chunk-size error or the header date being corrected, meaning the edit touched unrelated content and left this specific rot in place.
- **Evidence**: quotes above; `chunk_boundaries.py:19` comment "SINGLE SOURCE OF TRUTH"; `chunked_processor.py:351` `chunk_duration=CHUNK_DURATION`.
- **Impact**: A frontend developer implementing or debugging the streaming client from this doc alone would assume 30-second granularity — wrong by 2x — potentially miscalculating buffer pre-fill thresholds, seek-chunk math, or UI progress increments against the real 15s/10s/5s-overlap model. This is exactly the kind of doc that `docs/development/TESTING_GUIDELINES.md`-style reference docs are trusted for during onboarding since it's linked from `CLAUDE.md`'s own Reference Docs section.
- **Siblings**: none found — grepped the rest of the file for "30" / "30-second" and these are the only occurrences of the wrong chunk size; no other message shape in the file was found to mismatch `chunked_processor.py`'s emitted payload during this pass (I did not exhaustively diff all 34 message types against `schemas.py` — see Coverage Statement).
- **Related**: project memory note "WEBSOCKET_API stale on chunk size" (pre-existing lead, now confirmed with exact numbers); `docs/subsystems/dsp-engine.md` and other docs correctly state 15s/10s/5s per SEED_docrot context, so this file is the outlier.
- **Suggested Fix**: Replace "30-second chunk(s)" / "(typically 30)" with "15-second chunks (`CHUNK_DURATION`), 10s new-content interval, 5s crossfade overlap" and update the "Last Updated" header to the actual last-edit date. Consider a one-line note pointing at `chunk_boundaries.py` as the source of truth so future edits don't hardcode the number again.

---

### TD7-7: `README.md` links to `docs/getting-started/BETA_USER_GUIDE.md` as "the User Guide" with no caveat, but that guide documents `v1.0.0-beta.1` (download links, screenshots-era features) while the README's own release table says the latest binary is `v1.2.0-beta.2` and current source is `v1.5.1`
- **Severity**: LOW
- **Dimension**: Stale Documentation & Comments
- **Location**: `README.md:364` (`- **[User Guide](docs/getting-started/BETA_USER_GUIDE.md)** - Complete user guide`); `docs/getting-started/BETA_USER_GUIDE.md:39,50,63,70,293`
- **Status**: NEW
- **Effort**: trivial (<=30min) — add a version caveat to the README link, or bump the guide's download filenames
- **Description**: `BETA_USER_GUIDE.md` itself is self-aware of partial staleness (`:465-466`: "Last Updated: 2026-07-08 (license section corrected; rest of document may still describe an earlier beta — see docs/README.md for current version)"; "Version at original writing: 1.0.0-beta.1") — so the guide's *authors* already flagged the drift internally. What is NOT flagged is the outbound link from the project root: `README.md:364` presents it flatly as "Complete user guide" with no version caveat, so a reader following the top-level README has no signal before clicking that the destination describes `Auralis-1.0.0-beta.1.AppImage` / `.deb` / `.exe` / `.dmg` download filenames (`:39,50,63,70`) and reports "Version: 1.0.0-beta.1" (`:293`) — three tagged releases behind the README's own stated latest binary (`v1.2.0-beta.2`, Dec 2025) and six behind current source (`v1.5.1`).
- **Evidence**: quotes above, verbatim line numbers.
- **Impact**: Minor — a beta tester following the README's own "User Guide" link would download filenames that no longer match any current release artifact name, and see a version string two minor releases stale. Low real-world cost since the guide already self-corrects at the bottom, but the entry point (README) doesn't pass that warning forward.
- **Siblings**: `docs/getting-started/LAUNCH.md` and `docs/getting-started/START_HERE.md` (both in the same directory) carry the same "historical, self-flagged" shape — each already has its own explicit correction banner (Dec-2025 launch retro; 2026-07-08 design-doc correction respectively), so I am not filing those as new findings — they are already handled, just noting the directory-wide pattern: `docs/getting-started/` is nominally the "start here" path but all 3 of its files are stale-with-disclaimer, and none is a true, currently-accurate quickstart.
- **Related**: none.
- **Suggested Fix**: Either update `BETA_USER_GUIDE.md`'s download filenames/version string to the current `v1.2.0-beta.2` binary release (matching README's own release table), or add a one-line caveat at the README link itself ("describes v1.0.0-beta.1; some details are stale — see the guide's own note").

---

### TD7-8: `WEBSOCKET_API.md`'s reproduced `WebSocketMessageType` union omits the live `cache_cleared` message entirely and undercounts the union as "34 members" (actually 35)
- **Severity**: LOW
- **Dimension**: Stale Documentation & Comments
- **Location**: `auralis-web/backend/WEBSOCKET_API.md:849-894` (the reproduced `WebSocketMessageType` union and its "System messages" comment group)
- **Status**: NEW
- **Effort**: trivial (<=30min) — add one line + fix the count
- **Description**: `WEBSOCKET_API.md:849` states "The complete `WebSocketMessageType` union (34 members) is reproduced here for quick reference," then reproduces the union type at `:851-894`. I diffed that reproduction against the canonical source, `auralis-web/frontend/src/types/ws/registry.ts:128-163` (`ALL_MESSAGE_TYPES`), member for member. Every entry in the doc matches the source **except one is missing**: `'cache_cleared'` (declared in `registry.ts:13` as `SystemMessageType`, included in `ALL_MESSAGE_TYPES:162`, and part of the `AnyWebSocketMessage` union at `registry.ts:120` via `CacheClearedMessage`). The doc's "System messages" group jumps straight from `library_tracks_removed` to `error`, skipping it. This is not a dead/unused type either — it is emitted at runtime: `auralis-web/backend/routers/cache_streamlined.py:162` sends `{"type": "cache_cleared", ...}` over the same WebSocket this doc describes.
- **Evidence**:
  ```
  registry.ts:128-163 (ALL_MESSAGE_TYPES, 35 entries) includes 'cache_cleared' at :162
  WEBSOCKET_API.md:851-894 (reproduced union) has 34 entries, no 'cache_cleared'
  cache_streamlined.py:162:    "type": "cache_cleared",
  ```
- **Impact**: A frontend/backend contributor consulting this doc as the canonical WS message reference (as `CLAUDE.md`'s Reference Docs section directs) would not find `cache_cleared` documented at all — no payload shape, no trigger description — despite the type being live and emitted from a real router.
- **Siblings**: none found — this was the only member-level mismatch discovered when diffing the reproduced union; I did not separately diff every individual message's payload shape against every corresponding TS interface in `types/ws/*.ts` (see Coverage Statement) so there could be others at the field level.
- **Related**: none.
- **Suggested Fix**: Add a `cache_cleared` entry to the reproduced union (with its own `#### cache_cleared` payload section, mirroring the others), update the member count to 35, and consider generating this table from `registry.ts` instead of hand-copying it, since this is the second time this file has drifted from its source (see TD7-6 for the chunk-size drift in the same file).

---

---

## Coverage and Caveats

### Dimension 1 — Stale Markers (TODO / FIXME / HACK / XXX)

**Examined**: every comment-anchored marker in `auralis/`, `auralis-web/backend/`,
`auralis-web/frontend/src/`, `vendor/auralis-dsp/src/` (all `.py`, `.ts`, `.tsx`, `.rs`); the full
102-hit widened soft-marker sweep, each read in surrounding context; both dedup JSON files for the
three suppressed items.

**Not reached**: markers inside `tests/` (excluded from this dimension's entry points — test-side
deferred work is Dim 6's remit); markers in `docs/` and `.claude/` (Dim 7 / Dim 10); markers in
`desktop/` and `scripts/` (outside the skill's stated Dim 1 entry points); non-English marker
conventions; markers inside minified/vendored JS.

---

### Dimension 2 — Dead Code & Unused Surface

**Examined**:
- All 6 high-value leads supplied in the task brief, each independently re-verified with fresh greps/reads rather than trusted from the brief or from the other same-day audit reports:
  1. `auralis-web/backend/monitoring/` (946 LOC) — confirmed zero production importers, wrote `TD2-1`. Also disambiguated it from the unrelated, live `cache/monitoring.py` (same basename, different package) — an easy false-positive trap on a bare grep for "monitoring".
  2. The engine "sophisticated-but-unshipped" cluster — traced the live path myself from `auralis-web/backend/core/audio_processing_pipeline.py:199/221/228` through `HybridProcessor.process()` to `ContinuousMode`, and independently re-derived the reachability of all four named clusters (13-stage `stages/`, `optimization/parallel/`, the `AdaptiveLimiter`/`RealtimeAdaptiveEQ` chain, `RecordingTypeDetector`) with my own grep evidence rather than citing the engine report's numbers. Built a consolidated LOC inventory (`TD2-3`, ~4,843 newly-inventoried LOC / ~5,661 including the already-tracked `#4565`).
  3. `auralis/dsp/stages.py::main()` — checked `#4592` first as instructed (confirmed it covers 4 *different* modules, not this one), then found the cited "test importer" doesn't even successfully import the module (`ImportError`→skip every run) — dead ness is total, wrote `TD2-2`.
  4. 15 orphan `schemas.py` models + cache-stats shadowing — independently re-derived a matching list of 12 orphans (+ the separately-tracked 4-model cache family), then discovered `AUDIT_BACKEND_2026-07-29.md` BE5B-N1 already files this today with near-identical evidence; converted to a dedup note (`TD2-4/5`) rather than a duplicate finding, per the task's explicit instruction for leads 4-6.
  5. Two `PaginationParams` classes — independently re-derived the same 500-vs-200 conflict and the "neither is wired, routes hardcode their own bounds" finding, found it already filed as BE5B-N2 today; folded in as an addendum (wider `le=` inconsistency across more routers than BE5B-N2's single example) rather than a new finding.
  6. Frontend orphan `AlbumDetailApiResponse` and `CacheAwareAPIClient.getChunk()`/`cache/endpoints.py` — independently re-verified both (zero references outside their own declarations; `cache/endpoints.py` mounts zero actual routes), found both already filed today (`AUDIT_FRONTEND_2026-07-29` T4-02, `AUDIT_BACKEND_2026-07-29` BE5-N3/BE1-7/BE5B-N7); dedup-noted, not re-filed.
- Ran `ruff check --select F401,F811` (via a pyenv-managed Python since the project `.venv` has no ruff/vulture) across all of `auralis/` + `auralis-web/backend/` — 6 hits, all read and triaged (`TD2-8`).
- Ran `mypy --warn-unused-ignores --ignore-missing-imports` against all 38 files containing a `type: ignore` (84 total occurrences) — 3 hits, all read and triaged; 1 already tracked (`#4397`), 2 new (`TD2-7`). Confirms the project memory's caution not to assume many stale ignores exist.
- Confirmed the Rust `#[allow(dead_code)]` baseline (0) directly against `vendor/auralis-dsp/src` — matches, nothing to report.
- Ran `ts-prune` against `auralis-web/frontend` (878 raw hits) as a frontend dead-export sweep. Cross-checked the top offenders: the largest, `src/performance/index.ts` (41 hits), corroborates the already-OPEN `#4696` (not re-filed). Spot-verified `src/design-system/index.ts`'s 55 flagged "unused" exports, including `tokens` — CLAUDE.md's mandated design-token import, actually used in 195 files — confirming these are tool false positives (path-alias resolution gap), not real debt. Did **not** mine the remaining ~800 ts-prune hits for further findings: per the methodology warning, a raw tool list this size is dominated by barrel-file/path-alias noise and every real finding in it would need the same individual verification already spent on the six supplied leads; the marginal, unverified tail was judged not worth reporting given the "quality over quantity" instruction and the "stop the long tail" guidance once the substantive items were in hand.
- Cross-checked dedup against `/tmp/audit/tech-debt/issues.json`, `issues_tech_debt.json`, and all four sibling `AUDIT_*_2026-07-29.md` reports for every finding above before filing.

**Not reached / explicitly out of scope for this pass**:
- Did not perform a symbol-by-symbol dead-code sweep of `auralis/analysis/` (56 files) beyond what the supplied leads and the engine-audit cross-reference already covered (`#4592`'s 4 modules, `#4565`'s `parallel/` family) — the module is large enough that a genuine sweep would need its own session; flagging as a gap rather than silently skipping it.
- Did not independently verify `QueueTemplateRepository` (`ENG-D7-3`, library-layer "wired into its factory, zero callers") — it's a `library/repositories/` concern, mentioned only as `Related` context for `TD2-3`, not verified in depth since it falls outside this dimension's primary entry points as scoped in `audit-tech-debt.md`.
- Did not run `vulture` (not installed anywhere available, including the pyenv fallback used for `ruff`) — relied on `ruff` F401/F811 plus targeted manual `grep`/read verification instead, consistent with the task's "otherwise grep" fallback instruction.
- Did not exhaustively work through all ~800 non-top-offender `ts-prune` hits (see above) — a follow-up frontend-focused dead-export pass could mine this list properly file-by-file if wanted, but that is a distinct, large effort or a future audit run rather than debt this pass verified.
- Did not attempt a full manual read of every one of the 106 Python / 139 TS/TSX files over 300 LOC for internal private-function dead code — that overlaps Dimension 9 (Complexity) and was left to that dimension to avoid duplicating effort.

---

### Dimension 3 — Logic Duplication

**Examined:**
1. Target group 1 (WAV encoder duplication hotspot): read both `auralis-web/backend/encoding/wav_encoder.py` and `auralis-web/backend/core/encoding/wav_encoder.py` in full; confirmed only one `WAVEncoderError` class exists (doc-rot in `_audit-common.md`, not filed here); traced every import of both modules across the backend (`processing_engine.py`, `chunked_processor.py`, `routers/enhancement.py`) and found a real, previously-unreported 2-way duplication one level down in `chunked_processor.py` (TD3-1).
2. Target group 2 (14 repositories + `base.py` + `factory.py`): read `base.py` in full; programmatically counted every `self.get_session()` and `_session_scope(` call site across all 14 repository files (89 hand-rolled / 21 migrated / 110 total); wrote and ran a script to verify every hand-rolled site has a matching `finally: session.close()` and that `except` blocks have `rollback()` (only one exception found, `queue_history_repository.py:124`, judged out of scope since `_session_scope()` doesn't provide rollback either); confirmed near-verbatim `get_by_id`-shape duplication across 7 files. Found this duplicates OPEN issue #4604 — marked as dedup, not re-filed, but the corrected 89/21/110 breakdown is recorded since it differs from the "~110 unmigrated" phrasing in project memory.
3. Target group 3 (20 routers + 5 named helpers `errors.py`/`pagination.py`/`serializers.py`/`dependencies.py`/`similarity_common.py`): read `errors.py` and `pagination.py` in full; grepped adoption of `dependencies.py` (14/20 routers, healthy) and `serializers.py` (3/4 serializable-list routers); found `pagination.py` has zero importers anywhere in the router tree (TD3-3, overlaps #3892) and that `artists.py` independently re-derives `serialize_artist()`'s count logic without its #4306 Mock-safety fix (TD3-4, genuinely new).
4. Target group 4 (DSP pre/post-amble, 13 stages + `auralis/dsp/`): re-read `auralis/core/stages/__init__.py`'s `no_op` helper and grepped all 13 stage files for bypass-path `.copy()` coverage and in-place mutation (`+=`/`-=`/`*=`/`/=`/`[...] =`) — zero hits, confirming the 2026-07-25 finding still holds after 128 commits.
5. Target group 5 (`stream_*.py`/`chunk_*.py`, `mastering_*.py`): read `stream_normal.py` in full; cross-referenced the embedded issue-number history of `stream_normal.py`/`stream_enhanced.py`/`stream_seek.py` to hunt for a fix mirrored to one but not another — none found on this sampling. Read the docstrings/headers of the 5 `mastering_*.py` files and confirmed they are non-overlapping god-file-split outputs (#4071/#4072), not duplicates.
6. Target group 6 (`auralis-web/frontend/src/hooks/`): read `useStandardizedAPI.ts` in full (already streamlined in an earlier pass); grepped for hand-rolled `loading`/`error` state (all instances found are legitimate `react-query` `useQuery` usage, not duplication); grepped `useWebSocketMessages` adoption vs. direct `wsContext.subscribe()` bypasses (3 found, one — `useAudioStreamingCore.ts` — read in full and judged deliberately-engineered, not accidental duplication).
7. Ran the dedup protocol against `issues.json`/`issues_tech_debt.json` for every candidate finding before finalizing (WAV encoder terms, `_session_scope`, pagination/has_more, artist/serialize/mock/4306) and against `AUDIT_TECH_DEBT_2026-07-25.md` for the WAV-encoder finding specifically.

**Not reached / explicitly out of scope for this pass:**
- `stream_enhanced.py` and `stream_seek.py` were only diffed via their issue-number comment trail, not read line-by-line in full the way `stream_normal.py` was — a deeper pass could still surface a mirrored-fix gap this sampling missed.
- `mastering_branches/` (base.py, continuous.py, soft_clip_params.py) internals were not read for duplication between the branch implementations themselves (only confirmed the outer `mastering_*.py` split-module family is non-overlapping).
- `auralis-web/frontend/src/hooks/` was sampled (websocket, shared, fingerprint subfolders) but not exhaustively — `player/`, `enhancement/`, `library/`, `app/`, `audio/` subfolders (the bulk of the ~29,600 LOC in `hooks/`) were not individually read end-to-end; only grepped for the two named patterns (fetch+loading+error state machines, subscribe/unsubscribe).
- `similarity_common.py` and `dependencies.py` bypass-counting was done at the grep-adoption level only (which files import them), not a line-by-line audit of whether each of the 14 dependencies.py-importing routers uses it correctly/completely.
- Did not attempt to quantify duplication inside `auralis/analysis/` (56 files, the largest module) — out of this dimension's named target groups and not reached given time budget.
- No test execution was performed (per HARD CONSTRAINTS) — all findings are from static reading plus targeted `grep`/`git log` evidence.

---

### Dimension 4 — Magic Numbers & Hardcoded Constants

**Examined**: `auralis-web/backend/core/chunk_boundaries.py` and every non-definition reference to its 4 exported constants + `content_chunk_count()` across `auralis-web/backend/` (chunked_processor.py, chunk_operations.py, cache/manager.py, cache/__init__.py, stream_normal.py, stream_seek.py, stream_enhanced.py, routers/enhancement.py, services/audio_content_predictor.py); `auralis/core/config.py` vs `auralis/core/config/` package byte-for-byte (values + import resolution, empirically verified with a live Python import in the project's `.venv`); the full current `sample_rate=44100` default site list (48) diffed against the commit the 2026-07-25 audit was generated from (`499a2101`, 46 sites), with call-site tracing for both genuinely new sites plus a 6-site spot-recheck of pre-existing ones; `auralis-web/backend/core/audio_stream_controller.py`'s constant cluster (`MAX_CONCURRENT_STREAMS`, `_global_stream_semaphore`, `CHUNK_PROCESS_TIMEOUT`) against its 3 streaming-router consumers; `auralis-web/backend/config/limits.py` and its 2 importers; FFT/window/buffer-size literals under `auralis/dsp/` and naming conventions in `auralis/analysis/fingerprint/`; a repo-wide sweep of frontend hex/rgb literals outside `design-system/`, cross-checked against `docs/audits/AUDIT_FRONTEND_2026-07-29.md` for dedup.

**Not reached / out of scope**: Rust DSP internals (`vendor/auralis-dsp/src/*.rs`) — any FFT/window/hop constants baked into the PyO3 module were not audited (would need a Rust-literate pass, and the task scoped this dimension to Python/TS surfaces); the full 48-site `sample_rate=44100` list was traced for its 2 new members plus a 6-site sample, not exhaustively re-verified site-by-site (the 2026-07-25 audit already did the exhaustive pass for the other 40; re-running all 46 unchanged sites would have been pure repetition with no new signal); `auralis/optimization/`, `auralis/learning/`, and `auralis/services/` were grep-swept for the priority-target patterns but not read file-by-file the way `chunk_operations.py`/`config.py`/`audio_stream_controller.py` were; frontend `rgb()`/`rgba()` literals (as opposed to `#hex`) were not separately re-swept beyond the sample noted above, since `D5-01` already owns the color-token migration as a whole and further raw-literal hunting there would duplicate that audit's scope, not extend it.

**Result**: 4 findings (1 MEDIUM, 3 LOW). No CRITICAL/HIGH — the HIGH promotion trigger ("hardcoded rate/chunk/buffer constant that would silently truncate/overflow audio under documented use") was explicitly checked for the chunk-boundary and sample-rate priority targets and did **not** fire in either case; every live call site passes the real value explicitly. The chunk-boundary single-source-of-truth is, on the whole, well-enforced — the one gap found (`chunk_operations.py`'s default parameters) is latent, not live. This dimension's largest lead (frontend color-token bypass) was already filed by the frontend audit; I verified it independently and cross-referenced rather than re-filing it.

---

### Dimension 5 — Stub & Placeholder Implementations

**Examined**:
- Both pre-verified facts from the task brief, independently re-traced rather than trusted: (1) the
  `NotImplementedError` contract in `duplicate_detector.py` — traced every caller repo-wide
  (`scanner.py`, both backend routers that could plausibly reach it, all test call sites) and confirmed
  zero reachability from any shipped route; (2) all bare `...` bodies — confirmed each is inside a
  `typing.Protocol` with at least one live concrete implementer.
- Full sweep for "stub-flavored" comments (`# This would`, `# In production`, `# Simplified`, `# For now`,
  `# Mock`, `# Placeholder`) across `auralis/` and `auralis-web/backend/`, individually read and triaged:
  `masking.py` (real computation, dismissed), `manager.py`/`track_repository.py::find_similar` (real
  computation — but its *caller* has a genuine tuple-unpack bug → `TD5-1`), `scanner.py:379-380`
  (`Existing: #4243`, confirmed no siblings), `sidecar_manager.py`, `playlist_repository.py` (both
  legitimate design notes, not stubs).
- Grep sweep for `pass`-only function bodies in `auralis/library/scanner/` and
  `auralis-web/backend/services/` — both hits found were legitimate exception-swallowing, not stubs.
- Grep sweep of `auralis-web/backend/services/*.py` for `return None` / `return []` / `return {}` /
  `return 0.0` (32 raw hits across `artwork_downloader.py`, `recommendation_service.py`,
  `learning_system.py`, `queue_enrichment.py`, `library_auto_scanner.py`, `audio_content_predictor.py`) —
  read every file with >1 hit in full; all are legitimate empty-state/failure-fallback returns backed by
  real logic, none are placeholder stubs. `learning_system.py` turned out to be dead code (noted as a
  `TD2-1` addendum), not a stub.
- Frontend sweep for "Coming soon" / "not implemented" / "placeholder" / no-op markers across
  `auralis-web/frontend/src` — the one live-code "Coming soon" hit (`AddToPlaylistMenu.tsx`) and its
  sibling (`useBatchOperations.ts` bulk-remove) both turned out to describe an already-fixed past state
  (#4240), not current behavior. Re-verified the `useFingerprintCache.ts` DEV-only guard (Existing:
  #4239) is intact and has not regressed.
- Frontend sweep for `Math.random()` in production (non-test) code — all 6 hits are legitimate (error/toast
  IDs, k-means init, retry jitter, a genuine random-track picker), none fabricate data presented as real
  results.
- Read `docs/audits/AUDIT_BACKEND_2026-07-29.md` and `AUDIT_FRONTEND_2026-07-29.md` in full-text grep for
  `stub|placeholder|mock|hardcoded|fabricat|coming soon` for dedup — found one direct Dimension-5-shaped
  overlap (`BE5B-N6`, hardcoded `/api/audio/formats` list) and recorded it as a dedup note rather than
  re-filing; `BE9-06` (two `assert True` placeholder tests) is Test Hygiene territory (Dimension 6), not
  restated here.
- Checked `/tmp/audit/tech-debt/dim_2.md` in full before starting, per instructions — cross-referenced its
  live-path tracing (`HybridProcessor` → `ContinuousMode` → WOLA EQ → brick-wall limiter) to establish
  reachability for both `TD5-1` (player pipeline) and the `masking.py` dismissal, and to identify
  `learning_system.py` as transitively dead behind `TD2-1`'s already-confirmed dead `monitoring/` package.
- Checked `issues_all.json` for prior/related issues on every candidate (`find_similar`, `auto_select`,
  `integration_manager`) before filing `TD5-1` as NEW.

**Not reached / explicitly out of scope for this pass**:
- Did not exhaustively read all ~20 registered routers line-by-line for hardcoded response bodies —
  narrowed via targeted greps (stub-comment markers, `return {`/`return []` sweeps, and the backend
  audit's own findings for dedup) rather than a full manual pass of every handler in every router. A
  dedicated route-by-route diff against its backing service/repository would be a larger, separate effort.
  `BE5B-N6` (the one hardcoded-route instance actually found) came from the backend audit's own sweep, not
  mine — I only verified and dedup'd it.
- Did not check `auralis/analysis/` (56 files, the largest module) function-by-function for stub-shaped
  returns beyond the two targeted grep sweeps above — a full read of that module for this specific pattern
  would need its own session, consistent with Dimension 2's coverage statement making the same call.
- Did not verify every one of the 32 raw `services/` return-based grep hits individually line-by-line
  beyond the ones with multiple hits per file (i.e. `artwork_downloader.py`'s 15 single-context `return
  None`s inside external-metadata-fetch fallbacks were skim-read as a block, not each individually
  re-derived) — judged low-yield given they are all inside the same external-API-failure-fallback pattern.
- Did not run a frontend `grep` for every component under `auralis-web/frontend/src/pages/` /
  `components/` individually for skeleton/empty-state components beyond the targeted "Coming soon" /
  "placeholder" keyword sweep — skeleton loaders (`SkeletonLoader.tsx` family) were confirmed to be
  legitimate loading-state UI, not stubs, and not investigated further per-component.
- Did not independently re-derive the full backend/frontend audits' other findings beyond the
  Dimension-5-relevant grep pass described above — read those two reports for dedup only, as instructed.

---

### Dimension 6 — Test Hygiene

### Examined (read in full or targeted-executed with `timeout`/`-k` scoping, never a whole hanging file)
- **SEED-1** (`active_streams`): Read `tests/backend/test_audio_stream_lifecycle.py` (lines 1-264+) and `tests/backend/test_stream_disconnect_toctou.py` (lines 1-373+) in full for the relevant sections; read `auralis-web/backend/core/audio_stream_controller.py` `__init__` (lines 146-220); ran 5 scoped test invocations (`-k test_cleanup_on_success`, `-k active_streams`) with `timeout 120`; used `git log -S` and `git show --stat` to find and read the removal commit `8e6fae6f` in full. → TD6-1.
- **SEED-2** (`status_code in [...]`): Extracted and parsed all 193 `status_code in [...]` occurrences across `tests/` with a script; read `test_artists_api.py` (lines 1-150), `test_player_api_comprehensive.py` (lines 260-330), `test_artwork_security.py` (all `status_code` lines) directly; grepped for the `if status_code == 200:` gating pattern across all 7 flagged files. → TD6-2.
- **SEED-3** ("CRITICAL INVARIANT" empty-fixture skips): Read `tests/auralis/test_audio_processing_invariants.py` (lines 1-180, 460-500) in full; read `tests/backend/test_library_pagination_invariants.py` in full (all ~930 lines, in three passes); read `tests/auralis/library/test_library_manager_invariants.py` (lines 180-340); ran a scoped execution (`-k "album_pagination or artist_pagination_completeness"`) to confirm the guaranteed-skip claim empirically. → TD6-3 (refuted the file the seed most worried about; confirmed a narrower instance elsewhere).
- **SEED-4** (frontend queue-hook wholesale mocking): Enumerated every `__tests__` file under `src/hooks/player/` and every file across `src/hooks/**` that mocks `useRestAPI`/`useRestAPIModule` (6 files total); read `useQueueHistory.test.ts` (337 lines) and `useQueueMutations.optimistic.test.ts` (204 lines) in full; grepped `usePlaybackQueue.test.ts` and `usePlaybackControl.test.ts` for assertion density; read `useLibraryQuery.test.ts` in full (1271 lines) once the queue-hook hypothesis didn't pan out, including its pagination/fetchMore/search/custom-endpoint/snake_case-transform `describe` blocks. → TD6-4 (seed's target files were clean; found the real instance in a sibling file).
- **Standard sweep**: Re-verified `tests/concurrency/test_thread_safety.py`'s xfail hygiene against the prior audit's TD6-1/#4548 by grepping every `@pytest.mark.xfail` line (7 total) and spot-checking one cited API-signature claim against real source (`auralis/dsp/dynamics/compressor.py`) — clean, not regressed. Enumerated all 54 remaining `@pytest.mark.skip`/`skipif`/`xfail` sites outside that file via grep and read each cluster (ffmpeg/mutagen-conditional skips, deprecated-REST-endpoint skips in `test_main_api.py`/`test_api_endpoint_integration.py`, "Known limitation" skips in `test_boundary_max_min_values.py`, the 9 `#4269`-cited xfails in `test_parallel_processing.py`, the `#4520`-cited HPSS xfail adjacent to the sample-count invariant) — all found to be legitimately documented with real, currently-accurate reasons, except the 13-site `except Exception: pytest.skip` pattern written up as TD6-5. Checked all 3 project-wide `NotImplementedError` occurrences — 0 are in `tests/`, out of scope for this dimension. Checked the frontend skip/todo baseline (1 `describe.skip` found, not 2 as the baseline states — the one found, `streaming-mse.test.tsx`, is a previously-fixed false-confidence test, #3935/TC-3, correctly quarantined and documented; did not chase the baseline's second count further). Ran a regex sweep for empty (`pass`-only) test bodies (6 hits, all false positives — either regex artifacts or legitimately class-level-skipped placeholder methods) and for `print()`-instead-of-assert (5 hits, all either non-pytest-collected standalone validation scripts under `tests/validation/validate_*.py`, or debug prints alongside real assertions).
- Cross-referenced every finding candidate against `/tmp/audit/tech-debt/issues_all.json` (both OPEN and CLOSED) before writing it up, per the dedup protocol.

### Not reached
- The remaining ~140 of the 193 `status_code in [...]` sites that mix only 2xx+4xx (not 2xx+5xx) — these are generally defensible (e.g. `[200, 404]` for "may or may not exist") and were excluded from TD6-2 by design, but were not individually read for a subtler version of the same problem (e.g. `[200, 400]` where 400 is actually always the wrong-content-type case being silently accepted).
- `tests/backend/test_similarity_api_new.py` and `tests/backend/test_metadata_api.py` (5 and 4 sites respectively counted into TD6-2's total) were counted via the parsing script and cross-checked against the `if status_code == 200:` gating grep, but individual test bodies in these two files were not read line-by-line the way `test_artists_api.py` and `test_player_api_comprehensive.py` were.
- The ~40 remaining `pytest.skip("No X to test")` conditional guards in `test_library_pagination_invariants.py` keyed off `populated_db` (search/favorites/recent/popular) were read and judged legitimate (data-dependent, not unconditionally empty) but not executed to empirically confirm they never actually fire in practice.
- `tests/auralis/library/test_scanning_invariants.py:98` and the remaining `test_library_manager_invariants.py` skip at line 582 (seed's SEED-3 candidate list) were located via grep but not read in full — time budget was directed at the confirmed `test_library_pagination_invariants.py` instance instead once the pattern was established there.
- Backend test files beyond the ones named above were not swept file-by-file for smoke-only (`assert X is not None`-only) assertions beyond the already-closed `#4049` (31 sites, LOW, closed 2026-05-30) — did not re-verify whether all 31 of that fix's sites are still fixed; spot checks elsewhere in the suite did not surface any new instances of that specific pattern.
- Frontend: only the `src/hooks/**` REST-mocking test files were examined in this depth; the wider frontend test suite (components, Redux slices, services) was not swept for the false-confidence framing beyond the two explicit SEED-4 candidates and the one project-wide `describe.skip`. `auralis-web/frontend/test-baseline.json`'s ~138 tracked pre-existing failures were deliberately not re-litigated per the task's explicit instruction.
- Did not execute `tests/backend/test_system_api.py` or `tests/concurrency/test_thread_safety.py` as whole files (per hard constraint) — all claims about them are from static reading plus scoped `-k`-filtered single-test/class runs under `timeout 120`.

---

### Dimension 7 — Stale Documentation & Comments

**Examined**:
- `.claude/commands/_audit-common.md` in full, plus a targeted grep-and-read of "baseline" / "WAVEncoderError" / "Two live" across all 11 other `.claude/commands/*.md` files (SEED-A, SEED-B siblings).
- `CLAUDE.md` in full (Codebase Map, Principles, version header).
- Live-tree recomputation (hand-run, not just trusted from SEED_counts.md) of: `auralis/analysis/` file count, registered-router count (with the include_router comment-line false-positive caught and excluded), test-file count, test-function count, `docs/` topic-dir count, `docs/**/*.md` total.
- `auralis/version.py`, `pyproject.toml` (root + `mutants/`), all 3 `package.json` files (root, `desktop/`, `auralis-web/frontend/`), `README.md`, `docs/versions/VERSIONING_STRATEGY.md`, `docs/MASTER_ROADMAP.md`, `docs/releases/CHANGELOG.md` for version-string consistency.
- `auralis/dsp/stages.py`'s reachability (re-verified Dim 2's TD2-2 grep independently) and its `CLAUDE.md` description.
- `auralis-web/backend/WEBSOCKET_API.md` in full (922 lines): read start-to-end; verified the chunk-duration/interval/overlap claims against `auralis-web/backend/core/chunk_boundaries.py` (the file's own declared "SINGLE SOURCE OF TRUTH") and `chunked_processor.py`'s actual payload construction; diffed the reproduced `WebSocketMessageType` union member-for-member against `auralis-web/frontend/src/types/ws/registry.ts`.
- `README.md` in full for command examples, package-manager usage (pnpm vs npm/yarn), Node/Python version badges, entry-point references, and download-link version consistency against its own release table.
- `docs/getting-started/` (all 3 files, read in full) as the most likely "stale onboarding doc" candidate; found all three already self-flag their own staleness with correction banners from an earlier (2026-07-08) docs pass — filed only the one gap that pass didn't close (the unwarned README outbound link, TD7-7).
- `_audit-validate.sh` read in full to extract its exact `should_skip`/`expand_braces`/`path_exists` logic, which I copied into a throwaway script (`/tmp/audit/tech-debt/dim7_validate_live_docs.sh`, `dim7_validate_all_docs.sh`) and ran twice: once over all 507 `docs/**/*.md` files (1,978 raw stale hits — explicitly rejected as a headline number per the methodology warning, since it includes 400 files in `docs/archive|audits|releases|development|guides` that are historical-by-design), and once restricted to the 108-file "current" subset (278 stale hits across 51 files). Hand-verified ~20 of those 278 individually (roughly 7%) across 4 files, confirming a mix of genuine rot (moved-file paths, renamed classes/modules) and at least one false-positive cluster (an already self-correcting historical doc).

**Not reached / explicitly out of scope**:
- The other ~93% of the 278 flagged "current-docs" stale hits (TD7-4) were NOT individually hand-verified — I verified a representative sample across the highest-signal files (`MASTER_ROADMAP.md`, both security fix docs, one testing doc, one getting-started doc) and extrapolated a directional estimate, not an exact count. Treat the 278 figure as an upper bound requiring further triage, not a precise debt count.
- `docs/development/`, `docs/guides/`, `docs/archive/`, `docs/audits/`, `docs/releases/` (400 of 507 files) were deliberately not stale-path-checked beyond the top-level policy question of whether they *should* be, per the gate's own stated design intent (historical snapshots). I did not open all 400 to confirm each one is genuinely historical rather than mislabeled.
- I did not diff every individual `WEBSOCKET_API.md` message payload's field list against its corresponding TS interface in `auralis-web/frontend/src/types/ws/*.ts` and Pydantic model in `auralis-web/backend/schemas.py` — only the union membership (TD7-8) and the chunk-duration numeric claim (TD7-6). A full field-by-field `/sync-contracts`-style pass across all ~34 message types was out of budget; there could be additional shape drift I did not catch.
- Did not exhaustively grep every docstring/comment in `auralis/` and `auralis-web/` for renamed/deleted symbol references — followed the one high-value lead flagged by Dim 2 (`stages.py`) rather than an unguided sweep, per the methodology warning against unverified grep-driven padding.
- Did not audit `docs/development/TESTING_GUIDELINES.md` content against current test tooling (pytest pin, vitest baseline mechanics) beyond what SEED-A already covers structurally.
- Did not cross-check every `docs/features/*` or `docs/frontend/*` subdirectory's prose against current component/module names beyond the stale-path pass in TD7-4 — no manual content read of those ~57 files individually.
- Dimension 10's remit (skill-file dimension-count drift, `docs/audits/` CRITICAL/HIGH triage status, `.claude/issues/` bookkeeping) was left entirely to that agent, as instructed.

