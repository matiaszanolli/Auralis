# Auralis Master Roadmap

**Current version:** 1.5.0 (source of truth: [`auralis/version.py`](../auralis/version.py))
**Last updated:** 2026-07-18 — v1.5.0 stable release prep (version-fact refresh).

> **How to read this.** This roadmap was previously a November-2025 planning document built
> around shipping "v1.0.0-stable" and a set of "future" tracks (similarity graph, continuous
> enhancement space, background fingerprinting, sampling strategy, 25D adaptive mastering).
> **Those tracks have all since shipped.** This version records what is actually built, the
> course-corrections that happened along the way, and the work that is genuinely still open.
> Authoritative shipping record: git tags, [releases/CHANGELOG.md](releases/CHANGELOG.md), and
> the code itself.

---

## 1. Current state snapshot

| Fact | Value | Source |
|------|-------|--------|
| Version | 1.5.0 (first stable release) | [`auralis/version.py`](../auralis/version.py) |
| Latest tagged binary release | `v1.2.0-beta.2` (2025-12-27) — `v1.2.1-beta.1`/`beta.2` were source-only, no binaries; both folded into 1.5.0 | `git tag`, [releases/CHANGELOG.md](releases/CHANGELOG.md) |
| Backend tests | ~5,445 functions across 391 files | `tests/` |
| Frontend tests | ~3,476 functions across 215 files | `auralis-web/frontend/src` |
| DB schema | v16 | [`migration_manager.py`](../auralis/library/migration_manager.py) |
| Fingerprint algo | v3 | [`auralis/__version__.py`](../auralis/__version__.py) |
| Default mastering engine | Continuous space (`use_continuous_space=True`) | [`unified_config.py:154`](../auralis/core/config/unified_config.py) |
| Default fingerprint strategy | Sampling (20 s interval) | [`unified_config.py`](../auralis/core/config/unified_config.py) |

Released lines to date: `1.0.0-beta.*` → `1.1.0-beta.*` → `1.2.0-beta.*` → `1.2.1-beta.*` (source-only) → `1.5.0` (first stable).

---

## 2. The original vision — shipped

Every major track from the 2025 roadmap is now in production code. Verify any row against the
linked subsystem doc.

| 2025 plan | Status | Where it lives now |
|-----------|--------|--------------------|
| **25D fingerprinting** (extraction, storage, background queue) | ✅ Shipped | [`analysis/fingerprint/`](../auralis/analysis/fingerprint/) · [subsystems/fingerprinting.md](subsystems/fingerprinting.md) |
| **Sampling strategy** (5 s chunks, ~90% accuracy, big speedup) | ✅ Shipped, **default** | `SampledHarmonicAnalyzer`, `fingerprint_strategy="sampling"` |
| **Background fingerprinting** (worker pool, `.25d` sidecars, scanner integration) | ✅ Shipped | `FingerprintExtractionQueue`, atomic claiming, gRPC Rust server |
| **Similarity graph system** (weighted 25D distance, kNN, API, UI) | ✅ Shipped | `distance.py`, `knn_graph.py`, `similarity_graph_repository.py`, [`routers/similarity.py`](../auralis-web/backend/routers/similarity.py) (12 endpoints) |
| **25D adaptive mastering** (fingerprint → pre-computed params, deterministic chunks) | ✅ Shipped | `ContinuousMode` maps 25D → 3D processing space; `CrossDimensionalGuard`, `PipelineJournal` |
| **Continuous enhancement space** (replace discrete presets with interpolation) | ✅ Shipped, **default** | `ContinuousMode` is the default adaptive path; named presets remain as entry points |
| **Rust DSP acceleration** (HPSS/YIN/Chroma, native fingerprint) | ✅ Shipped | [`vendor/auralis-dsp/`](../vendor/auralis-dsp/), PyO3 + standalone gRPC server |
| **Phase 1 testing infrastructure** (boundary/invariant suites) | ✅ Shipped, far exceeded | ~5,300 backend test functions vs the old "850+ / 2,500 target" |
| **Desktop binaries** (AppImage, DEB, Windows, macOS `.dmg`) | ✅ Shipped | CI/CD across all platforms |

**Bottom line:** the "revolutionary features enabled by the 25D system" are no longer a plan —
they are the shipped architecture. See [architecture/overview.md](architecture/overview.md).

---

## 3. Course-corrections since the old plan

Two things the old roadmap listed as milestones did **not** survive contact with the code, and
the roadmap should stop implying otherwise:

- **MSE / WebM-Opus streaming was abandoned, not shipped.** The old roadmap celebrated a
  "Unified MSE + Multi-Tier Buffer streaming (4,518 lines)" milestone. That approach was
  replaced: the shipped browser player is the **Web Audio API** with a circular `Float32Array`
  PCM buffer + `AudioWorkletNode`, fed by binary PCM WebSocket frames. `MediaSource` /
  `SourceBuffer` / WebM / Opus appear **nowhere** in the current backend or frontend. The
  `docs/guides/MSE_*` and `MULTI_TIER_BUFFER_*` guides are legacy. See
  [subsystems/frontend.md §8](subsystems/frontend.md#8-browser-audio-pipeline-the-real-one).
- **The "architecture cleanup" track (remove `SpectrumMapper`) never happened.**
  `SpectrumMapper` is still constructed and used by `HybridProcessor`
  ([`hybrid_processor.py:60`](../auralis/core/hybrid_processor.py)). It remains a real
  consolidation opportunity (see §5).

---

## 4. Active / near-term

As of v1.5.0 there is no open `[Unreleased]` line — the mastering-quality refinement pass that
previously lived there (Linkwitz-Riley LR4 crossovers, auto-mastering headroom fix, smooth
processing curves) shipped as part of 1.5.0; see
[releases/CHANGELOG.md](releases/CHANGELOG.md#150---2026-07-18) for the full entry.

Near-term work going forward is tracked as the open backlog below (§5), plus whatever surfaces
from post-1.5.0 usage. This is consistent with the ongoing mastering-tuning work (loudness
maximizer, `LOUDNESS_GAP_CLOSURE_FACTOR`) tracked in the engine notes.

---

## 5. Open backlog (real, tracked)

The genuine "what's next" is quality and tech-debt, not vision features. These are the
deferred LARGE items and known gaps:

| Item | Issue | Notes |
|------|-------|-------|
| **`response_model=` coverage** | #3838 | ~28 endpoints across 8 routers return raw dicts (albums, artwork, metadata, library, playlists, tracks, files, fingerprint_status). New Pydantic models needed. See [subsystems/backend-api.md §6](subsystems/backend-api.md#6-schemas--the-response_model-gap-schemaspy) |
| **God-file splits** | #4075–#4083 | Remaining 900–1,500-line module decompositions in the series (#4071–#4074 done) |
| **Rust LUFS → BS.1770** | #4123 | Rust LUFS is RMS-approx; wants K-weighting + gating. Confirmed: 0 k-weighting refs in `vendor/auralis-dsp/`. Needs `maturin` rebuild |
| **`semantics.ts` token convention** | #4203 | Frontend design-token composition decision needed before further token work |
| **`SpectrumMapper` consolidation** | — | Still used by `HybridProcessor`; candidate to fold into `AdaptiveTargetGenerator` now that fingerprints drive processing |

**Code-level inconsistencies** surfaced during the 2026-07-11 docs pass (worth issues if not
already tracked):

- `phase_correlation` — schema says 0–1, analyzer returns −1..+1.
- Variation dims have two different default-value sets (`batch/variation.py` vs the
  orchestrator's `_get_default_fingerprint`).
- `25D_SIDECAR_FORMAT_SPEC.md` diverges from the as-built format (nested vs flat, 0–100 vs 0–1
  band fractions, SHA-256 vs size+mtime validation) — spec should be reconciled or marked
  design-only.

**Test-suite health** (not new, but load-bearing): the full `tests/backend` suite never goes
fully green (v15→v16 migration cascades); `test_system_api.py` and
`concurrency/test_thread_safety.py` hang as whole files. Gate on targeted domain tests. See
[CONTRIBUTING.md §4](CONTRIBUTING.md#4-testing).

---

## 6. Longer-term vision (foundation built, depth/UX remaining)

The ambitious 2025 vision items are no longer greenfield — the primitives exist. What remains
is depth, UX, and productization:

| Vision | Foundation in code | Remaining |
|--------|--------------------|-----------|
| "Find songs like this" | Similarity API + kNN graph shipped | Discovery UX, cross-genre tuning |
| Intelligent / flow playlists | `content/recommendations.py` (`RecommendationEngine`) | Playlist generation UX, sequencing |
| User preference learning | [`auralis/learning/`](../auralis/learning/) (`preference_engine`, `reference_analyzer`, `reference_library`) | Closing the loop into live mastering params |
| Section-aware / real-time adaptation | ContinuousMode + per-chunk params | Intra-track section detection |
| Enhancement profile sharing | Deterministic fingerprint→params | Export/import + sharing surface |

Treat these as directions, not committed milestones — prioritize against user feedback.

---

## 7. Sources of truth

When this doc and the code disagree, the code wins.

- **Version** → [`auralis/version.py`](../auralis/version.py)
- **What shipped** → git tags + [releases/CHANGELOG.md](releases/CHANGELOG.md)
- **How it works now** → [architecture/](architecture/) + [subsystems/](subsystems/)
- **Chunk geometry / fingerprint dims** → the source-of-truth registry in
  [architecture/overview.md](architecture/overview.md#source-of-truth-registry)

Superseded planning docs (including the 1.1.0-cycle roadmap) live in
[archive/](archive/) — reference only.
