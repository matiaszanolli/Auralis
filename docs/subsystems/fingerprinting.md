# Subsystem: 25D Audio Fingerprinting & Analysis

[`auralis/analysis/`](../../auralis/analysis/) is the largest module in the project (81
files). Its centerpiece is the **25-dimensional audio fingerprint** — a compact numeric
descriptor of a track's spectral, dynamic, temporal, harmonic, and stereo character. The
fingerprint drives adaptive mastering, similarity search, and quality assessment.

> **Scope.** Fingerprint extraction, storage, the similarity stack, background scheduling,
> and the content/quality/ML analyzers. For how fingerprints feed mastering, see
> [dsp-engine.md](dsp-engine.md).

---

## 1. The 25 dimensions

**Authoritative semantics/units:**
[`fingerprint/schema.py:44`](../../auralis/analysis/fingerprint/schema.py) (`DIMENSION_SCHEMA`).
**Canonical ordering** (vectors, weights, DB columns):
[`fingerprint/normalizer.py:87`](../../auralis/analysis/fingerprint/normalizer.py)
(`DIMENSION_NAMES`) and
[`fingerprint_service.py:34`](../../auralis/analysis/fingerprint/fingerprint_service.py)
(`_FP_KEYS`) — these agree on order.

| Family | Dims | Names |
|--------|------|-------|
| **Frequency** (7-band spectral energy) | 7 | `sub_bass_pct, bass_pct, low_mid_pct, mid_pct, upper_mid_pct, presence_pct, air_pct` |
| **Dynamics** | 3 | `lufs` (BS.1770 K-weighted), `crest_db`, `bass_mid_ratio` |
| **Temporal** | 4 | `tempo_bpm`, `rhythm_stability`, `transient_density`, `silence_ratio` |
| **Spectral character** | 3 | `spectral_centroid`, `spectral_rolloff`, `spectral_flatness` |
| **Harmonic** | 3 | `harmonic_ratio`, `pitch_stability`, `chroma_energy` |
| **Variation** | 3 | `dynamic_range_variation`, `loudness_variation_std`, `peak_consistency` |
| **Stereo** | 2 | `stereo_width`, `phase_correlation` |

**Band edges (Hz):** 20–60 / 60–250 / 250–500 / 500–2000 / 2000–4000 / 4000–6000 / 6000–20000
([`schema.py:87`](../../auralis/analysis/fingerprint/schema.py)).

> ⚠️ **Critical unit convention.** The 7 band values are stored as **0–1 fractions that sum
> to ~1.0**, *not* 0–100 percentages, despite the `_pct` suffix. Consumers that assumed 0–100
> caused real bugs — hence the loud docstring at
> [`schema.py:8`](../../auralis/analysis/fingerprint/schema.py). Spectral centroid/rolloff are
> normalized 0–1 where 1.0 = 8000 Hz (`centroid_to_hz` / `rolloff_to_hz` convert back).
> `loudness_variation_std` is the unit outlier: dB in range 0–10.

**Count is hard-enforced everywhere:** `< 25` dims are discarded, not cached
([`fingerprint_service.py:387`](../../auralis/analysis/fingerprint/fingerprint_service.py));
the Rust server must return exactly 25; distance/normalize assert `len == 25`.

> **Known code-level inconsistencies** (real, not just doc drift — verify before relying):
> `phase_correlation` schema says 0–1 but the analyzer returns −1..+1; two different default
> value sets exist for the variation dims (`batch/variation.py` vs the orchestrator's
> `_get_default_fingerprint`).

---

## 2. Extraction — the analyzer

`AudioFingerprintAnalyzer.analyze()`
([`audio_fingerprint_analyzer.py:101`](../../auralis/analysis/fingerprint/audio_fingerprint_analyzer.py))
is the whole-track extraction entry point:

```
validate → resample to 22050 Hz  (so all paths produce identical fingerprints)
         → require ≥ 0.5 s → mono downmix
         → precompute ONE shared rfft / magnitude / freqs / rms
         → frequency (7D) + dynamics (3D)     [sequential]
         → temporal + spectral + harmonic + variation + stereo   [5-thread pool]
         → sanitize NaN/Inf → 0.0
```

Only a `batch/` analyzer package exists. The `streaming/` analyzers referenced in some
docstrings and in `analyzers/__init__.py` **do not exist as files** — treat those references
as stale. All batch analyzers subclass
[`analyzers/base_analyzer.py:21`](../../auralis/analysis/fingerprint/analyzers/base_analyzer.py),
which wraps `_analyze_impl` in try/except returning `DEFAULT_FEATURES.copy()`.

| Analyzer | File | Notes |
|----------|------|-------|
| `SpectralAnalyzer` | `batch/spectral.py` | one shared `librosa.stft` |
| `TemporalAnalyzer` | `batch/temporal.py` | single `beat_track` pass (#3704) |
| `HarmonicAnalyzer` | `batch/harmonic.py` | full-track |
| `SampledHarmonicAnalyzer` | `batch/harmonic_sampled.py` | **default** ("sampling"); 5 s chunks at `sampling_interval`, own 4-thread pool |
| `VariationAnalyzer` | `batch/variation.py` | |
| `StereoAnalyzer` | `batch/stereo.py` | |

### Backend split (which dims use Rust vs librosa)

| Dims | Backend |
|------|---------|
| Frequency (7) + Dynamics (3) | NumPy `rfft` in the orchestrator |
| Harmonic (3) | **Rust** — HPSS, YIN, Chroma via `DSPBackend` |
| Spectral (3) + Temporal (4) + Variation (3) | **librosa / NumPy**, in-process |

`DSPBackend`
([`utilities/dsp_backend.py:24`](../../auralis/analysis/fingerprint/utilities/dsp_backend.py))
is **Rust-only** (raises `RuntimeError` at import if `auralis_dsp` is missing) and coerces all
inputs to float64 before the FFI call. See [dsp-engine.md §5](dsp-engine.md#5-rust-dsp-module-vendorauralis-dsp).

---

## 3. Storage — two `.25d` systems

There are **two distinct `.25d` mechanisms**. Know which one you're touching.

| System | Class | Location | Validation |
|--------|-------|----------|------------|
| **Centralized cache** | `FingerprintStorage` ([`fingerprint_storage.py`](../../auralis/analysis/fingerprint/fingerprint_storage.py)) | `~/.auralis/fingerprints/<md5>.25d` | key = MD5 of `abs_path:mtime:size:strategy` (#3679, #4127) |
| **Per-file sidecar** | `SidecarManager` ([`library/sidecar_manager.py`](../../auralis/library/sidecar_manager.py)) | `<audio>.25d` next to the file | size + mtime (not checksum) |

Both write **flat** JSON fingerprint dicts. `FingerprintExtractor` reads/writes the
per-file sidecar during scanning.

> ⚠️ **The spec doc lies.**
> [`docs/guides/25D_SIDECAR_FORMAT_SPEC.md`](../guides/25D_SIDECAR_FORMAT_SPEC.md) is a
> **design proposal (Oct 2025)**, not as-built. It shows a *nested* fingerprint
> (`frequency/dynamics/…`), band values as **0–100**, and SHA-256 checksums — none of which
> match the code (flat dict, 0–1 fractions, size+mtime validation). Do not treat its example
> numbers as authoritative. Treat `schema.py` as truth.

**Version gating:** fingerprints carry a version; sidecars older than
`FINGERPRINT_ALGORITHM_VERSION` (= **2**,
[`auralis/__version__.py:14`](../../auralis/__version__.py)) are rejected and re-extracted.
Bumping that constant auto-triggers Phase-2 re-fingerprinting (see §5).

---

## 4. Similarity search

Pipeline: **raw 25D vector → normalize → weighted Euclidean distance → rank**.

| Stage | Class / file | Notes |
|-------|-------------|-------|
| Normalize | `FingerprintNormalizer` ([`normalizer.py`](../../auralis/analysis/fingerprint/normalizer.py)) | robust min-max on 5th/95th percentiles; `fit()` streams `track_fingerprints` in 5000-row batches (#4115); zero-variance dim → 0.5 |
| Distance | `FingerprintDistance` ([`distance.py:175`](../../auralis/analysis/fingerprint/distance.py)) | `sqrt(Σ wᵢ(xᵢ−yᵢ)²)`; hand-tuned per-family weights (frequency 33%, dynamics 23%, temporal 18%, spectral 12%, harmonic 9%, variation 5%, stereo 3%), renormalized in `to_array()` |
| High-level API | `FingerprintSimilarity.find_similar` ([`similarity.py:108`](../../auralis/analysis/fingerprint/similarity.py)) | pre-filter on 4 distinctive dims (`lufs±3, crest_db±2, bass_pct±8, tempo_bpm±15`), bounded full-search fallback (`limit=5000`, #3705); `.fit()` must run first |
| kNN graph | `KNNGraphBuilder.build_graph(k=10)` ([`knn_graph.py`](../../auralis/analysis/fingerprint/knn_graph.py)) | streams fingerprints in batches (#3454); writes edges via the graph repo |
| Graph storage | `SimilarityGraphRepository` ([`library/repositories/similarity_graph_repository.py`](../../auralis/library/repositories/similarity_graph_repository.py)) | edges: `track_id, similar_track_id, distance, similarity_score, rank` |

**REST surface** — [`routers/similarity.py`](../../auralis-web/backend/routers/similarity.py),
prefix `/api/similarity`:
`GET /tracks/{id}/similar` (graph-first, real-time fallback, auto-enqueues missing
fingerprints), `/tracks/{a}/compare/{b}`, `/tracks/{a}/explain/{b}`, `POST /fit`,
`POST /graph/build`, `GET /graph/stats`, `DELETE /graph`, plus `/fingerprint-queue/*` and
`/fingerprint-stats`. CPU-bound work is offloaded via `asyncio.to_thread` (#2738); errors go
through a correlation-id wrapper that never leaks `str(exc)` (#3331).

---

## 5. Background scheduling (how tracks get fingerprinted)

`FingerprintExtractionQueue`
([`services/fingerprint_queue.py`](../../auralis/services/fingerprint_queue.py)) uses **no
job queue** — N daemon worker threads pull directly from the DB. Worker count auto-sizes
`max(4, 0.5×CPU)` up to `2.0×CPU`, governed by an `AdaptiveResourceMonitor` (75% RAM ceiling).
Each worker runs two phases: Phase 1 claims **unfingerprinted** tracks, Phase 2
re-fingerprints **outdated-version** tracks.

**Atomic claiming** (avoids two workers grabbing the same track) lives in
[`fingerprint_scheduler_repository.py`](../../auralis/library/repositories/fingerprint_scheduler_repository.py):
`claim_next_unfingerprinted_track` inserts a placeholder `TrackFingerprint` row with a
`lufs = -100.0` sentinel; a UNIQUE-constraint `IntegrityError` means another worker won the
race. Outdated claims use a `version = 0` sentinel and a rowcount check.

**Extractor** — `FingerprintExtractor.extract_and_store`
([`services/fingerprint_extractor.py:264`](../../auralis/services/fingerprint_extractor.py))
tries, in order:

1. Valid `.25d` sidecar → instant.
2. **Rust server (port 8766)** — attempted first in code, but **currently dead** (see §7):
   nothing launches the server, the client speaks HTTP while the server is gRPC, and its
   compute is a stub. `_is_rust_server_available()` is effectively always False, so this branch
   never runs in practice.
3. **Python analyzer** — the *actual* primary path (≤ 300 MB OOM guard).

It stamps `fingerprint_version`, filters to exactly the 25 keys, rejects incomplete
fingerprints, and deletes corrupted files via `TrackRepository`.

**Multi-window LUFS/crest correction** — `FingerprintService.get_or_compute`
([`fingerprint_service.py:108`](../../auralis/analysis/fingerprint/fingerprint_service.py)) is
the 3-tier cache (DB → `.25d` → compute). Its `_compute_fingerprint` runs the full 25D on a
90 s body window plus two 30 s mono probes at 25%/75% and takes the **median** of lufs/crest
(cuts LUFS RMSE from 1.96 → 1.07 dB). It rejects entries whose 7 band fractions don't sum to
1 ± 0.05.

---

## 6. Content, quality, and genre analysis

- **Genre (ML)** — despite the `ml/` path, there is **no neural network**.
  [`ml/genre_classifier.py:22`](../../auralis/analysis/ml/genre_classifier.py) is
  `RuleBasedGenreClassifier`: 10 genres, hand-coded linear weights, softmax, 0.6 confidence
  threshold → falls back to "pop". Cached singleton (#2528).
- **Content** — `ml/` is now the sole genre classifier. The former parallel content-analysis
  stack (`analysis/content/`: a second `GenreAnalyzer`/`MoodAnalyzer`/`RecommendationEngine`)
  was **retired** in the 2026-07 streamlining (dead except a test-only public API). The live
  content analyzer for mastering is [`core/analysis/content_analyzer.py`](../../auralis/core/analysis/content_analyzer.py).
- **Quality** — `QualityMetrics.assess_quality`
  ([`quality/quality_metrics.py:79`](../../auralis/analysis/quality/quality_metrics.py))
  runs 5 assessors → weighted `overall_score` 0–100 (frequency .25, dynamic .20, stereo .15,
  distortion .25, loudness .15) → Excellent/Very Good/Good/Fair/Poor. Underlying analyzers:
  `LoudnessMeter`, `PhaseCorrelationAnalyzer`, `DynamicRangeAnalyzer`, `SpectrumAnalyzer`
  (8192-FFT, 128 bands). Per-track history is reset to avoid cross-track bleed (#4221).

---

## 7. Performance

- **Two Rust surfaces — one live, one dead:** the in-process PyO3 module (HPSS/YIN/Chroma,
  and the shared `fingerprint_compute::compute_complete_fingerprint`) is the real one. The
  standalone **gRPC fingerprint server**
  ([`vendor/auralis-dsp/src/bin/grpc_fingerprint_server.rs`](../../vendor/auralis-dsp/src/bin/grpc_fingerprint_server.rs))
  is **abandoned/non-functional**: it has its *own* `compute_25d_fingerprint` with **hardcoded
  placeholder values** for the 7 frequency bands + 3 spectral features + `rhythm_stability`;
  it's a `tonic` gRPC server while the Python client (`FINGERPRINT_ENDPOINT`) posts **HTTP
  JSON**; and nothing launches it. The extractor probes port 8766 but the branch never fires.
  Slated for removal (streamlining #12).
- **Parallelism layers:** the worker pool (0.5–2.0×CPU threads), a per-analyzer 5-thread
  pool for the 5 independent analyzers, and a per-`SampledHarmonicAnalyzer` 4-thread pool.
- **Timing figures to cite carefully:** the popular "~500 ms/track" number is from a planning
  doc, not asserted in code. The code-level throughput claim is concurrent batching
  `28.7 → 140+ tracks/sec`; the server targets 10–40 tracks/sec on low-end hardware.

---

## 8. Where to start reading

1. [`schema.py`](../../auralis/analysis/fingerprint/schema.py) — the 25 dimensions and their
   real units (authoritative).
2. [`audio_fingerprint_analyzer.py`](../../auralis/analysis/fingerprint/audio_fingerprint_analyzer.py)
   — the extraction orchestrator.
3. [`fingerprint_service.py`](../../auralis/analysis/fingerprint/fingerprint_service.py) — the
   3-tier cache and multi-window correction.
4. [`distance.py`](../../auralis/analysis/fingerprint/distance.py) +
   [`similarity.py`](../../auralis/analysis/fingerprint/similarity.py) — similarity math.

**Related:** [dsp-engine.md](dsp-engine.md) · [backend-api.md](backend-api.md) ·
[../architecture/module-map.md](../architecture/module-map.md)
