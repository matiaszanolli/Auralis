# Subsystem: 25D Audio Fingerprinting & Analysis

[`auralis/analysis/`](../../auralis/analysis/) holds the analysis code. Its centerpiece is the
**25-dimensional audio fingerprint**: a compact numeric descriptor of a track's spectral, dynamic,
temporal, harmonic and stereo character. The fingerprint drives the mastering plan, similarity
search and the reference cloud.

> **Scope.** Fingerprint extraction, storage, the similarity stack, background scheduling, and the
> genre and quality analyzers. How a fingerprint becomes a mastering plan is in
> [dsp-engine.md](dsp-engine.md); the Rust crate that computes it is in
> [RUST_DSP_STATUS.md](../features/RUST_DSP_STATUS.md); the REST and WebSocket surface is in
> [backend-api.md](backend-api.md).

---

## 1. The 25 dimensions

**Authoritative semantics and units:**
[`fingerprint/schema.py::DIMENSION_SCHEMA`](../../auralis/analysis/fingerprint/schema.py).
**Canonical order** (vectors, DB columns): `DIMENSION_NAMES`, derived from `DIMENSION_SCHEMA`; every
other list of the names is built from it.

| Family | Dims | Names |
|--------|------|-------|
| **Frequency** (7-band spectral energy) | 7 | `sub_bass_pct, bass_pct, low_mid_pct, mid_pct, upper_mid_pct, presence_pct, air_pct` |
| **Dynamics** | 3 | `lufs`, `crest_db`, `bass_mid_ratio` |
| **Temporal** | 4 | `tempo_bpm`, `rhythm_stability`, `transient_density`, `silence_ratio` |
| **Spectral character** | 3 | `spectral_centroid`, `spectral_rolloff`, `spectral_flatness` |
| **Harmonic** | 3 | `harmonic_ratio`, `pitch_stability`, `chroma_energy` |
| **Variation** | 3 | `dynamic_range_variation`, `loudness_variation_std`, `peak_consistency` |
| **Stereo** | 2 | `stereo_width`, `phase_correlation` |

**Band edges (Hz):** 20-60 / 60-250 / 250-500 / 500-2000 / 2000-4000 / 4000-8000 / 8000-20000
(`BAND_RANGES_HZ`; the split is made in Rust, `frequency_analysis.rs`, and the two must stay in
lockstep). The fingerprint analyses audio at 22,050 Hz, so the air band effectively stops at
11 kHz (#6721, open).

> **Unit conventions (a recurring source of bugs).**
> - The 7 band values are **0-1 fractions summing to 1 ± 0.05** (`band_pct_valid`), not
>   percentages, despite the `_pct` suffix.
> - `spectral_centroid` is normalized by 8000 Hz and `spectral_rolloff` by **10000 Hz**
>   (`centroid_to_hz`, `rolloff_to_hz` invert them).
> - `bass_mid_ratio` is dB (Rust's `bass/(bass+mid)` fraction is converted); `dynamic_range_variation`
>   is `v / (v + 6)` of the raw crest-factor dB deviation; `loudness_variation_std` is dB, clamped to 0-10.
> - `lufs` is an **RMS proxy** (`20·log10(rms)` with a fixed offset, floored at -120), not BS.1770.
>   Standards-compliant loudness comes from
>   [`analysis/loudness_meter.py::LoudnessMeter`](../../auralis/analysis/loudness_meter.py).

**Known inconsistency (verify before relying):** `phase_correlation`'s schema range is 0-1, but the
Rust engine returns -1..+1 and the glue passes it through.

**The count is enforced everywhere:** the Rust glue raises `KeyError` if the engine drops a key; a
result with fewer than 25 dimensions is discarded, never cached
(`windowed_compute.py::compute_windowed_fingerprint`); `FingerprintExtractor._prepare_for_storage`
and the distance code require exactly 25. Stored rows also carry `fingerprint_version`.

---

## 2. Extraction: the analyzer

### Which audio is analysed

Analysis is a property of the **entire track**; only mastering is chunked.
[`windowed_compute.py::compute_windowed_fingerprint`](../../auralis/analysis/fingerprint/windowed_compute.py)
is the single implementation of load, window-select and analyze, shared by the library scan, the
on-demand queue, the stream's whole-track extraction and the player:

- A track up to `FINGERPRINT_FULL_TRACK_MAX_S` (900 s) is analysed **whole**
  ([`track_audio.py`](../../auralis/analysis/fingerprint/track_audio.py)), decoded in 60 s segments
  with a 1 s margin each side so the segments join without a seam, at 22,050 Hz, and folded to at
  most two channels (BS.775 for 5.1/7.1).
- A longer track, or one whose duration cannot be probed, uses a 90 s **body window** at the
  middle plus two 30 s **probes** at 25 % and 75 %; the median `lufs` and `crest_db` across the three
  replace the body's.
- A buffer already in memory (a whole-file job) follows the same rule through
  [`preloaded_fingerprint.py::fingerprint_preloaded`](../../auralis/analysis/fingerprint/preloaded_fingerprint.py).
- All window geometry lives in [`windows.py`](../../auralis/analysis/fingerprint/windows.py).

Memory is bounded by [`analysis_budget.py`](../../auralis/analysis/fingerprint/analysis_budget.py):
a process-wide gate admits at most `ANALYSIS_BUDGET_MINUTES` (40) minutes of audio in flight across
all workers, weighting each job by its length and reserving **before** decoding. Admission is
FIFO with interactive callers (a listener waiting on a stream) ahead of background ones, and a
waiter can be cancelled (`should_stop`). A job is always admitted when nothing else runs, so one
long track cannot deadlock.

### The Rust call

`AudioFingerprintAnalyzer.analyze`
([`audio_fingerprint_analyzer.py`](../../auralis/analysis/fingerprint/audio_fingerprint_analyzer.py))
is a **thin Python facade over the in-process Rust engine**. Rust owns the DSP; Python does input
repair, resampling and marshalling:

```
non-finite samples zeroed
 → resample to 22,050 Hz (so every path yields the same fingerprint)
 → require at least 0.5 s
 → marshal mono (n,) or interleaved stereo (2n,); more than two channels fold to mono
 → rust_fingerprint.py::compute_fingerprint_schema → auralis_dsp.compute_fingerprint(audio, sr, channels)
 → rust_fingerprint_to_schema: raw Rust keys and units → the 25 schema dimensions
 → require_finite
```

`analyze` returns `{}` for empty, invalid-rate or too-short audio (a documented skip). Any engine
failure (missing module, Rust or resample error, partial or non-finite result) raises
`FingerprintUnavailable`. There is **no Python fallback**: without the `auralis_dsp` wheel every
fingerprint fails, and startup logs it and `/api/health` reports it
(`fingerprint_engine_error`; build with `cd vendor/auralis-dsp && maturin develop`).

`compute_windowed_fingerprint` turns any failure into `None` ("no fingerprint") unless called with
`raise_unavailable=True`, which only the stream's whole-track extraction does (§5). `FingerprintService.get_or_compute`
([`fingerprint_service.py`](../../auralis/analysis/fingerprint/fingerprint_service.py)) is the
3-tier lookup used by the player and the offline CLI: database, then `.25d`, then compute.

`scripts/fingerprint.py` with [`catalog.py`](../../auralis/analysis/fingerprint/catalog.py) fingerprints a
file or folder into a standalone SQLite catalog; it is not part of the app.

---

## 3. Storage — two `.25d` systems

There are **two distinct `.25d` mechanisms**, plus the database row. Know which one you are touching.

| System | Class | Location | Trust and validation |
|--------|-------|----------|----------------------|
| **Centralized cache** | `FingerprintStorage` ([`fingerprint_storage.py`](../../auralis/analysis/fingerprint/fingerprint_storage.py)) | `~/.auralis/fingerprints/<md5>.25d` (beside the library database when that lives elsewhere) | key = MD5 of `abs_path:mtime:size:strategy`; file format `2.0`; algorithm version at least current; complete, finite, measurable values. Unsigned |
| **Per-file sidecar** | `SidecarManager` ([`library/sidecar_manager.py`](../../auralis/library/sidecar_manager.py)) | `<audio filename>.25d` next to the file (`track.mp3.25d`) | HMAC signature from this install, then format version, exact algorithm version, file size and mtime (not a checksum), then the same value checks |

Both hold **flat** JSON fingerprint dicts. `FingerprintStorage` also stores the derived mastering
targets; readers re-derive them from the fingerprint rather than trusting the stored copy
(`strategy` survives only as a cache-key component). `FingerprintExtractor` writes the per-file
sidecar during library scans; the stream's tier-2 lookup, tier-3 save and `FingerprintService` use the
central cache. The database row (`track_fingerprints`, via `FingerprintRepository`; see
[library.md](library.md)) is the third tier and the one similarity reads.

**Value checks** ([`sidecar_fingerprint_check.py`](../../auralis/library/sidecar_fingerprint_check.py)):
all 25 dimensions present, finite and below `MAX_ABS_DIMENSION_VALUE`; band shares summing to 1;
`lufs` not below -120 and not the -100 claim sentinel (§5).

**Sidecar trust.** A per-file sidecar sits in the music folder, so whoever supplied the folder may
have written it. It is trusted only with a `signature`, an HMAC-SHA256 of its canonical JSON under a
per-installation key (`sidecar.key`, owner-only, in `~/.auralis` or `$AURALIS_DATA_DIR`;
[`sidecar_signature.py`](../../auralis/library/sidecar_signature.py)). An unsigned or foreign sidecar is
ignored: the track is re-analysed and a signed one written in its place, so sidecars do not carry
between installations. The central cache is not signed.

**Maintenance** ([`fingerprint_store_maintenance.py`](../../auralis/analysis/fingerprint/fingerprint_store_maintenance.py)):
`delete_entry`; `sweep_orphans` (entries nothing can load again: unreadable, wrong format, missing
source, or not the key the source would produce today; skips entries younger than 60 s), run at
startup and on Clear Cache; `clear_all_entries`, run by a library reset. Reading, writing and key
derivation stay on `FingerprintStorage`.

**Version gating.** `FINGERPRINT_ALGORITHM_VERSION` in
[`auralis/__version__.py`](../../auralis/__version__.py) is bumped whenever extraction changes the values
it produces; the file carries the current value and the reason for every bump. Rows, sidecars
and cache entries below it are rejected and re-extracted: the queue's second pass (§5) re-fingerprints
outdated database rows in the background.

> The archived [25D sidecar format spec](../archive/guides/25D_SIDECAR_FORMAT_SPEC.md) is a design
> proposal, not the as-built format (nested fingerprint, 0-100 band values, SHA-256 checksums).
> Treat `schema.py` and the writers above as truth.

---

## 4. Similarity search

Pipeline: **raw 25D vector → normalize → weighted Euclidean distance → calibrated score → rank**.

| Stage | Class / file | Notes |
|-------|-------------|-------|
| Normalize | `FingerprintNormalizer` ([`normalizer.py`](../../auralis/analysis/fingerprint/normalizer.py), persistence in [`normalizer_stats.py`](../../auralis/analysis/fingerprint/normalizer_stats.py)) | Per-dimension min-max on the 5th/95th percentiles, clipped to [0, 1]; a zero-range dimension maps to 0.5. `fit()` streams current-version rows in keyset-paged batches of 5000 (minimum 10 samples) and publishes one stats dict at the end |
| Distance | `FingerprintDistance` ([`distance.py`](../../auralis/analysis/fingerprint/distance.py)) with `DimensionWeights` ([`dimension_weights.py`](../../auralis/analysis/fingerprint/dimension_weights.py)) | `sqrt(Σ wᵢ(xᵢ−yᵢ)²)`; hand-set family weights (frequency 33, dynamics 23, temporal 18, spectral 12, harmonic 9, variation 5, stereo 3), renormalized to sum 1 |
| Score | `similarity_calibration.py` | `score = 1 − distance / reference_distance`, where the reference is the 95th percentile of pairwise distances among up to 300 sampled library tracks, measured at fit time (1.0 before a fit). A NaN distance scores 0.0 |
| API | `FingerprintSimilarity` ([`similarity.py`](../../auralis/analysis/fingerprint/similarity.py)) | `find_similar`, `calculate_similarity`, `get_similarity_explanation` (per-dimension contributions). Normalizer stats and reference distance are one `fitted_model`, so a result always comes from one model even during a refit |
| K-NN graph | `KNNGraphBuilder.build_graph(k=10)` ([`knn_graph.py`](../../auralis/analysis/fingerprint/knn_graph.py)) | Streams fingerprints in batches and replaces each batch's edges in place, so readers never see an empty graph. One build or clear at a time (`GraphBuildInProgress`) |
| Graph storage | `SimilarityGraphRepository` | edges: `track_id, similar_track_id, distance, similarity_score, rank` |

`find_similar` first pre-filters on four distinctive dimensions (`lufs` ±3, `crest_db` ±2,
`bass_pct` ±0.08, `tempo_bpm` ±15) to at most `n × 10` candidates, and widens to a full search
(bounded at 5000 rows) when the box holds fewer than `n`. `fit()` must run first.

**Auto-fit.** [`services/similarity_autofit_worker.py::SimilarityAutoFitWorker`](../../auralis-web/backend/services/similarity_autofit_worker.py)
fits once at startup, then re-checks every 300 s: it fits a library that was too small at startup and
**refits once the current-version fingerprint count reaches 1.5× the fitted sample**
(`REFIT_GROWTH_FACTOR`). A fit runs in a thread that checks a stop event between batch reads; a
stopped or failed refit keeps the previous model. A library reset calls `reset()`, so the new
library is fitted on its own statistics. The first successful fit creates the K-NN graph builder; an
already persisted graph keeps its edges until rebuilt.

**REST** (`/api/similarity`, [`routers/similarity.py`](../../auralis-web/backend/routers/similarity.py) and
siblings): `GET /tracks/{id}/similar` (graph first, real-time fallback, enqueues a missing
fingerprint), `/tracks/{a}/compare/{b}`, `/tracks/{a}/explain/{b}`, `POST /fit`,
`POST /graph/build`, `GET /graph/stats`, `DELETE /graph`, and `/fingerprint-queue/{status,enqueue/{id},enqueue-all}`;
coverage is `GET /api/library/fingerprints/status`. The full router map is in [backend-api.md](backend-api.md).

---

## 5. Background scheduling (how tracks get fingerprinted)

There are **two queues** with different jobs, and a third, synchronous route for a track being played.

| Route | Class | Fed by | Worker |
|-------|-------|--------|--------|
| **Library batch** | `FingerprintExtractionQueue` ([`services/fingerprint_queue.py`](../../auralis/services/fingerprint_queue.py)), globals key `fingerprint_queue` | Nothing: workers pull from the database | N daemon threads |
| **On-demand** | `FingerprintQueue` ([`analysis/fingerprint_queue.py`](../../auralis-web/backend/analysis/fingerprint_queue.py)), globals key `ondemand_fingerprint_queue` | Streams of an unfingerprinted track, the post-scan enqueue (added and updated tracks), the REST enqueue routes | One asyncio task; in-memory FIFO of up to 5000 ids, deduplicated; each track goes through `FingerprintGenerator` (a small thread pool, 30 s timeout) |
| **Stream tier-3** | `MasteringTargetService.load_fingerprint` | A play or seek whose track has no database row and no `.25d` | The stream's own constructor thread |

### Library batch queue

`FingerprintExtractionQueue` has **no job queue**. Worker count starts at `max(4, 0.5 × CPU)` with
a ceiling of `2.0 × CPU`. An `AdaptiveResourceMonitor` samples RAM every 2 s and steps up below
50 % and down above 80 %; its recommendation resizes the concurrent-decode semaphore (initially
`max(8, max_workers)` permits, never below 2). Worker-count changes are advisory bookkeeping: threads
are fixed at `start()`. Each worker loops two
passes: the first claims **unfingerprinted** tracks, the second claims tracks whose **algorithm version
is outdated**; a worker reports "drained" once, after both. When every worker has drained and at
least one track was processed, `on_drained` fires and refreshes the reference cloud (below). It is
restartable after `stop()` (a library reset stops it, wipes, and restarts it).

**Atomic claiming** lives in
[`fingerprint_scheduler_repository.py`](../../auralis/library/repositories/fingerprint_scheduler_repository.py).
`claim_next_unfingerprinted_track` inserts a placeholder `TrackFingerprint` row with the
`lufs = -100.0` sentinel (`PLACEHOLDER_LUFS_SENTINEL`); a UNIQUE `IntegrityError` means another
worker won the race. `claim_next_outdated_fingerprint` sets `fingerprint_version = 0` with a rowcount
check. Each queue keeps a claim cursor so a full-library run is not quadratic; a search that finds
nothing wraps once to the start. A claim that raises is retried with backoff
([`fingerprint_claim.py::claim_with_retry`](../../auralis/services/fingerprint_claim.py), five attempts) so a
lock timeout is never read as "queue empty". Startup crash recovery clears every sentinel
(`cleanup_incomplete_fingerprints`).

**Per-track behavior** ([`fingerprint_worker.py`](../../auralis/services/fingerprint_worker.py)): extraction
runs under a wall-clock bound (`AURALIS_FINGERPRINT_TRACK_TIMEOUT`, default 600 s) on a daemon thread
that is abandoned, not killed, on timeout. A **failed** track releases its claim so it is retried, up
to `MAX_EXTRACTION_ATTEMPTS` (3) per process; then it stays claimed until the next startup cleanup. A
worker stopped while waiting on the analysis gate hands its claim back without counting a failure,
and so does a track whose file changed during analysis (`AudioChangedDuringAnalysis`; nothing is
stored, and the new audio is analysed next).

**Extractor.** `FingerprintExtractor.extract_and_store`
([`services/fingerprint_extractor.py`](../../auralis/services/fingerprint_extractor.py)) tries a valid
`.25d` sidecar first (version at least current), else runs `compute_windowed_fingerprint`. It filters to
exactly the 25 keys, stamps `fingerprint_version`, rejects incomplete vectors, upserts with
`expected_filepath`, then writes the signed sidecar stamped with the **pre-analysis** `stat`.

### Stream tier-3 extraction

A stream resolves its fingerprint before chunk 0 (database, `.25d`, then extraction), so a track
is mastered against one plan from its first chunk to its last
([dsp-engine.md](dsp-engine.md#analysis-happens-once-per-whole-track)). Extraction:

- queues on the analysis gate **ahead of** background work, and is deduplicated per
  `(track, file signature)` by `fingerprint_single_flight.py::extract_once`: one leader extracts, followers
  wait and read the cache (a follower never inherits the leader's failure);
- writes the central `.25d` only if the file's size and mtime are unchanged afterwards;
- **fails the stream** with "Audio analysis failed; the track was not mastered" when the engine itself
  is broken (`FingerprintUnavailable`), instead of mastering each chunk blindly;
- on any other failure (decode error, partial result, cancelled wait) returns `None`: the stream
  continues with per-chunk analysis, the client gets `fingerprint_progress` status `failed`, and a
  background retry is queued.

### The reference cloud

Fingerprint rows flagged `is_reference` form the cloud the EQ plan pulls toward
([dsp-engine.md](dsp-engine.md#the-track-level-mastering-plan)). `auralis/learning/reference_seeder.py::refresh_cloud`
scores current rows heuristically and replaces the flagged set in one transaction; the batch queue's
`on_drained` hook and the library routes trigger it.

---

## 6. Genre and quality analysis

- **Genre.** Despite the `ml/` path there is **no neural network**.
  [`ml/genre_classifier.py::RuleBasedGenreClassifier`](../../auralis/analysis/ml/genre_classifier.py) scores
  ten genres (classical, rock, electronic, jazz, pop, hip_hop, acoustic, ambient, metal, country)
  with hand-set linear weights ([`genre_weights.py`](../../auralis/analysis/ml/genre_weights.py)) over
  features from `FeatureExtractor` (one extractor per sample rate), applies a softmax, and falls
  back to `pop` at confidence 0.5 below 0.6. `create_ml_genre_classifier()` is a cached singleton.
  Its only consumer is `ContentAnalyzer`
  ([`core/analysis/content_analyzer.py`](../../auralis/core/analysis/content_analyzer.py)), which feeds the
  `hybrid` path of the engine; it is independent of the 25D fingerprint.
- **Quality.** `QualityMetrics.assess_quality`
  ([`quality/quality_metrics.py`](../../auralis/analysis/quality/quality_metrics.py)) runs five assessors
  (each a `BaseAssessor`, scoring 0-100) into a weighted `overall_score` (frequency 0.25, dynamic 0.20,
  stereo 0.15, distortion 0.25, loudness 0.15) and a category (Excellent from 90, Very Good 75, Good 60,
  Fair 40, else Poor). It owns four stateful analyzers (`SpectrumAnalyzer` with an 8192-point FFT and
  128 bands, `LoudnessMeter`, `PhaseCorrelationAnalyzer`, `DynamicRangeAnalyzer`) that are reset per
  assessment so one track does not bleed into the next. Production use is limited to advisory,
  off-by-default measurement: the engine's quality gate and the offline CLI's before/after evaluation
  (`MasteringEvaluator`), neither of which changes audio.

---

## 7. Where to start reading

1. [`schema.py`](../../auralis/analysis/fingerprint/schema.py): the 25 dimensions and their real units.
2. [`windowed_compute.py`](../../auralis/analysis/fingerprint/windowed_compute.py),
   [`audio_fingerprint_analyzer.py`](../../auralis/analysis/fingerprint/audio_fingerprint_analyzer.py) and
   [`rust_fingerprint.py`](../../auralis/analysis/fingerprint/rust_fingerprint.py): what audio is
   analysed and the thin Rust facade.
3. [`fingerprint_storage.py`](../../auralis/analysis/fingerprint/fingerprint_storage.py) and
   [`sidecar_manager.py`](../../auralis/library/sidecar_manager.py): the two `.25d` systems.
4. [`fingerprint_queue.py`](../../auralis/services/fingerprint_queue.py) and
   [`fingerprint_scheduler_repository.py`](../../auralis/library/repositories/fingerprint_scheduler_repository.py):
   scheduling and claiming.
5. [`distance.py`](../../auralis/analysis/fingerprint/distance.py) and
   [`similarity.py`](../../auralis/analysis/fingerprint/similarity.py): the similarity math.

**Related:** [dsp-engine.md](dsp-engine.md) · [backend-api.md](backend-api.md) ·
[library.md](library.md) · [../architecture/module-map.md](../architecture/module-map.md)
