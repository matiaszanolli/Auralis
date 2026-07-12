# Streamlining Plan — Retiring Alternate Implementations

**Goal:** enforce the "No variants" principle ([`CLAUDE.md`](../../CLAUDE.md) #3) by retiring
parallel/duplicate implementations of the same concept, **one at a time**, each independently
revertible.

**Started:** 2026-07-11. Candidates were surfaced during the developer-docs rebuild and
verified by call-site analysis before classification.

> ⚠️ **The #1 risk in this work is collapsing variation that is intentional.** See the
> [Do-not-collapse list](#do-not-collapse--intentional-variation) before touching anything.
> Blast-radius numbers below are point-in-time — **re-grep before you act** (see the playbook).

---

## Per-item playbook

Each item = **one PR**, independently revertible:

1. **Confirm** call sites with a fresh grep — do not trust a stale catalog (this list has
   already been wrong once; see #1 below).
2. **Pick the survivor** — the default / better-tested / more-referenced implementation.
3. **Migrate** call sites to the survivor.
4. **Delete** the alternate in the same PR — no deprecation shims (this repo refactors in-place).
5. **Verify by driving the affected path**, not just running tests (the `verify` skill).
6. **Update the subsystem doc** if documented behavior changed.

---

## Wave 1 — Dead code / stale duplicates (near-zero risk)

| # | Item | Verified state | Status |
|---|------|----------------|--------|
| 2 | `frontend/src/main.tsx` | Stale duplicate of `index.tsx` (no `ErrorBoundary`, old version string); not loaded by `index.html`; only a test *comment* mirrored it | ✅ **Done 2026-07-11** — deleted |
| 3 | `HealthCheckResponse` / `VersionResponse` schemas | Superseded by `HealthResponse` / `VersionInfoResponse`; **zero** production callers; the one test that imported them never used them | ✅ **Done 2026-07-11** — removed models + dead test imports + stale comment |
| 4 | Phantom `streaming/` analyzer references | Referenced in `analyzers/__init__.py` docstring but the dir never existed | ✅ **Done 2026-07-11** — docstring corrected |

---

## Wave 2 — Flag-gated / effectively-dead legacy paths (low-medium risk)

| # | Item | Verified state | Status |
|---|------|----------------|--------|
| 5 | `AdaptiveMode` (legacy adaptive path) | Removed its `chunked_processor` usage (+ fixed a latent bug, see below). After that, `AdaptiveMode` has **no production caller** — it backs only the `hybrid`/`reference` mastering modes, which the app never selects | ✅ **Closed 2026-07-11 — kept intentionally.** Per product decision, the `hybrid`/`reference` modes stay, so `AdaptiveMode` stays as their backing. Documented as legacy in its class docstring. Not further retired |
| 6 | Two processor caches | `hybrid_processor._processor_cache` (max 10, core library) vs `ProcessorFactory` (max 32, backend). **These sit at different layers** — `auralis` core cannot import the backend's `ProcessorFactory` (confirmed), so this is layered, not a naive merge. The real duplication was 3 **unused** `process_adaptive/reference/hybrid` wrappers in `processor_factory` duplicating `hybrid_processor`'s public API | ✅ **Done 2026-07-11** — removed the 3 dead `processor_factory` convenience fns. Two caches **kept** (layered/intentional) |

---

## Wave 3 — Duplicated infrastructure (medium; each needs a "canonical" decision)

| # | Item | Blast radius | Note |
|---|------|--------------|------|
| 1 | **Two `SpectralOperations` classes, same name** — `metrics/spectral_ops.py` (low-level magnitude helpers, test-only) vs `utilities/spectral_ops.py` (high-level `calculate_*`, used in production by `batch/spectral.py`) | Both re-exported via package `__init__`s → **name collision** | ✅ **Done 2026-07-11** — renamed the metrics class → `SpectralMetrics` (fits the package's `*Metrics` convention); updated both `__init__`s + the test. Production `utilities.SpectralOperations` untouched. 52 metrics tests pass |
| 7 | Two frontend REST clients: `useRestAPI` (16 sites) + `standardizedAPIClient` (9 sites) | 25 call sites | Pick one canonical; migrate the other. Biggest consistency win |
| 8 | **Two parallel content-analysis stacks** (reclassified — bigger than "two genre classifiers"). `ml/RuleBasedGenreClassifier` feeds `core/analysis/content_analyzer.py` (mastering path); `content/GenreAnalyzer`+`MoodAnalyzer`+`RecommendationEngine` feed `analysis/content_analysis.py::ContentAnalyzer`, which is behind the public `analyze_audio_content` API. Each stack has its own `ContentAnalyzer` class (a second name collision) | design-level + public API | **Wave 4 / needs decision** — pick a canonical content stack; `analyze_audio_content` removal is a breaking public-API change. (NOTE: `RecommendationEngine` is **not** dead — it's used via the `create_recommendation_engine` factory in `content_analysis.py`; an earlier note wrongly called it removable, caught by re-verify) |
| 10 | Two `.25d` systems: `FingerprintStorage` + `SidecarManager` | — | ✅ **Investigated 2026-07-11 — not duplication.** `FingerprintStorage` = centralized machine-local cache (`~/.auralis/fingerprints/<hash>.25d`, content-keyed); `SidecarManager` = portable per-file sidecar (`<audio>.25d`, travels with the file). Complementary — moved to do-not-collapse. *Optional* future nicety: share the `.25d` JSON schema/serializer between them to prevent format drift |

---

## Wave 4 — Design-level consolidation (higher risk, core paths)

| # | Item | Note |
|---|------|------|
| 11 | `SpectrumMapper` → fold into `AdaptiveTargetGenerator` | The old roadmap's never-done "architecture cleanup." Still used by `HybridProcessor`. Needs a design pass |
| 12 | Two Rust fingerprint surfaces (PyO3 in-process vs gRPC server) | **Investigate first** — likely *not* duplication (batch throughput vs in-process harmonic ops). May just need documenting |

---

## Do-not-collapse — intentional variation

These read like duplicates but are deliberate; collapsing them reintroduces fixed bugs.
**Document, don't merge.**

- **Offline dynamics vs realtime `DynamicsProcessor`** — separated on purpose (#2897) to avoid
  double-compression fighting the LUFS target.
- **Sampling vs full-track harmonic analyzers** — strategy variants, both intentional.
- **Three chunk paths** (WS streaming / REST batch / REST WAV) — different transports/uses.
- **`HybridProcessor` (streaming) vs `SimpleMasteringPipeline` (offline file)** — different
  workflows that share only the audio invariants.
- **`analysis/quality/` vs `analysis/quality_assessors/`** (was #9) — **not duplication.**
  `quality/` (the assessment modules) imports its base class and utilities *from*
  `quality_assessors/` (`base_assessor`, `utilities/scoring_ops`, `assessment_constants`).
  `quality_assessors/` is the shared base layer, `quality/` builds on it. Confusing names, but
  complementary — a future rename for clarity is the only cleanup, not a collapse.
- **`AdaptiveMode`** — kept as the backing for the `hybrid`/`reference` mastering modes (see #5).
  Legacy but load-bearing for those modes; documented in its class docstring.
- **`FingerprintStorage` vs `SidecarManager`** (was #10) — **not duplication.** Centralized
  content-keyed cache (`~/.auralis/fingerprints/`) vs portable per-file sidecar (`<audio>.25d`).
  Different capabilities; keep both. Only *optional* cleanup: share the `.25d` serializer.

---

## Bugs discovered during streamlining

- **`get_mastering_recommendation` silently returned `None` for fingerprinted tracks**
  (chunked_processor). `_init_adaptive_mastering()` (run whenever a fingerprint was cached at
  init) stored an `AdaptiveMode` in `self.adaptive_mastering_engine`, but
  `get_mastering_recommendation` expects that slot to hold an `AdaptiveMasteringEngine` and
  calls `.recommend_weighted()` on it → `AttributeError` → swallowed by `except` → `None`. So
  weighted mastering recommendations failed exactly when a fingerprint was available (the normal
  case). **Fixed 2026-07-11** by removing the dead-and-harmful `_init_adaptive_mastering` (the
  slot now stays `None` and is lazily filled with the correct `AdaptiveMasteringEngine`). This
  was found while working item #5.

## Progress log

- **2026-07-11 (#10 classified, RecommendationEngine correction)** — #10 investigated →
  **not duplication** (centralized cache vs portable sidecar), moved to do-not-collapse. A trial
  delete of `content/RecommendationEngine` was **reverted** — it's live via the
  `create_recommendation_engine` factory in `content_analysis.py`; the earlier "dead" note
  grepped the class name but the import surface is the factory. **Lesson:** grep the factory
  function name too, not just the class. With this, the mechanical/safe pass is complete —
  every remaining item (#7, #8, #11, #12) is design-level or decision-gated.
- **2026-07-11 (#5 closed, #8/#9 reclassified)** — Per product decision the `hybrid`/`reference`
  modes are kept, so #5 is closed with `AdaptiveMode` retained (documented as legacy in its
  docstring). #9 reclassified as **not duplication** (`quality_assessors/` is the base layer for
  `quality/`) → moved to do-not-collapse. #8 reclassified as **two parallel content-analysis
  stacks** (design-level + public `analyze_audio_content` API), bigger than "two genre
  classifiers". (Corrected: `content/RecommendationEngine` is **not** dead — used via the
  `create_recommendation_engine` factory in `content_analysis.py`; caught by re-verify when a
  trial delete broke the import. Grep the factory name, not just the class.)
- **2026-07-11 (Wave 3)** — #1 done: resolved the `SpectralOperations` name collision by
  renaming the test-only metrics class → `SpectralMetrics` (52 metrics tests pass; production
  `utilities.SpectralOperations` untouched).
- **2026-07-11 (#5 gate)** — After removing the `chunked_processor` usage, `AdaptiveMode` has
  **no production caller**: the app always runs `mode="adaptive"` + `use_continuous_space=True`
  → `ContinuousMode`. `AdaptiveMode` survives only via `HybridMode` (which uses it as its core
  adaptive component, not just a fallback) and the dead `use_continuous_space=False` branch —
  both reachable only through the `hybrid`/`reference` config modes the app never selects.
  **Full retirement is gated on a product decision:** keep the `hybrid`/`reference` mastering
  modes (→ `AdaptiveMode` stays, document as legacy) or drop them (→ larger refactor,
  behavior change to currently-unused modes). Not a mechanical cleanup.
- **2026-07-11 (Wave 2)** — #6 done: removed 3 unused `processor_factory` convenience wrappers
  (the two caches are layered, kept). #5 partial: removed the `AdaptiveMode` usage from
  `chunked_processor` and fixed the recommendation bug above; `HybridMode` fallback +
  `hybrid_processor.adaptive_mode` still to retire. Verified: both files compile/import;
  recommendation integration tests pass (6 passed); `test_enhancement_api` shows 10 failures
  that are **pre-existing** (identical on a clean HEAD worktree) — no regression.
- **2026-07-11 (Wave 1)** — Plan created. Wave 1 (#2 `main.tsx`, #3 old health/version schemas,
  #4 phantom `streaming/` docstring) completed and verified. #1 reclassified from Wave 1 → Wave
  3 after re-verification revealed two distinct same-named classes, not dead code.
