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

| # | Item | Verified state | Action |
|---|------|----------------|--------|
| 5 | `AdaptiveMode` (legacy adaptive path) | `use_continuous_space=False` is set **nowhere** → dead in production. **But** `HybridMode` delegates to it as a no-reference fallback, and `chunked_processor` + one test reference it | Rework `HybridMode`'s fallback off `AdaptiveMode`, then retire it. Not a pure delete |
| 6 | Two processor caches | `hybrid_processor._processor_cache` (max 10, module-level convenience fns) vs `ProcessorFactory` (max 32, web backend). Convenience fns used by `auralis/__init__.py`, `audio_processing_pipeline.py`, `processor_factory.py`, tests | Make `ProcessorFactory` the single cache owner; convenience fns delegate |

---

## Wave 3 — Duplicated infrastructure (medium; each needs a "canonical" decision)

| # | Item | Blast radius | Note |
|---|------|--------------|------|
| 1 | **Two `SpectralOperations` classes, same name** — `metrics/spectral_ops.py` (low-level magnitude helpers: `normalize_magnitude`, `spectral_flatness`, `spectral_centroid_safe`; used only by `test_common_metrics.py`) vs `utilities/spectral_ops.py` (high-level `calculate_*`, used in production by `batch/spectral.py`) | Both re-exported via package `__init__`s → **name collision** | **Reclassified here from Wave 1.** Not dead code. Merge/rename to kill the collision; update the test |
| 7 | Two frontend REST clients: `useRestAPI` (16 sites) + `standardizedAPIClient` (9 sites) | 25 call sites | Pick one canonical; migrate the other. Biggest consistency win |
| 8 | Two genre systems: `ml/genre_classifier` (2) + `content/GenreAnalyzer` (1) | 3 sites | Consolidate |
| 9 | Two quality packages: `quality/` (1 caller) + `quality_assessors/` (5) | 6 sites | Consolidate — note the doc-designated "main" (`quality/`) has *fewer* callers; decide direction |
| 10 | Two `.25d` systems: `FingerprintStorage` (3) + `SidecarManager` (1) | 4 sites | **Investigate first** — may be legitimately different (centralized cache vs per-file sidecar) |

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

---

## Progress log

- **2026-07-11** — Plan created. Wave 1 (#2 `main.tsx`, #3 old health/version schemas, #4
  phantom `streaming/` docstring) completed and verified (schemas import clean; affected test
  collects 50 tests). #1 reclassified from Wave 1 → Wave 3 after re-verification revealed two
  distinct same-named classes, not dead code.
