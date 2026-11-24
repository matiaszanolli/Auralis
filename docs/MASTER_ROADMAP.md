# Auralis Master Roadmap

**Current version:** 1.5.1, unreleased recovery milestone (source of truth:
[`auralis/version.py`](../auralis/version.py))

> **How to read this.** This roadmap records what is built, the course-corrections made along
> the way, the work that gates the next release, and the open backlog grouped by theme. The
> original 2025 plan (v1.0.0-stable plus a set of "future" tracks) has shipped or been replaced.
> Authoritative shipping record: git tags, [releases/CHANGELOG.md](releases/CHANGELOG.md), and
> the code itself. The issue tracker is the authority on the backlog.

---

## 1. Current state snapshot

| Fact | Value | Source |
|------|-------|--------|
| Version | 1.5.1 (unreleased recovery milestone) | [`auralis/version.py`](../auralis/version.py) |
| Latest tagged source release | `v1.2.1-beta.1` | `git tag` |
| Latest documented binary release | `v1.2.0-beta.2` (2025-12-27) | [releases/CHANGELOG.md](releases/CHANGELOG.md) |
| Toolchain | Python 3.14+, Node 24+, pnpm 10, Rust pinned in `rust-toolchain.toml` | [`vendor/auralis-dsp/rust-toolchain.toml`](../vendor/auralis-dsp/rust-toolchain.toml) |
| DB schema | independent of the product version | [`auralis/__version__.py`](../auralis/__version__.py) |
| Fingerprint algorithm | independent; whole-track analysis since v13 | [`auralis/__version__.py`](../auralis/__version__.py) |
| Default mastering engine | Continuous space (`ContinuousMode`), one `adaptive` preset | [`continuous_mode.py`](../auralis/core/processing/continuous_mode.py) |
| Fingerprint analysis | Whole track up to 900 s; longer tracks use a body window plus probes | [subsystems/fingerprinting.md](subsystems/fingerprinting.md) |
| CI failure baselines | Backend, nightly slow suite, and frontend baselines list no known failures | [`pytest-baseline.json`](../pytest-baseline.json) · [`pytest-slow-baseline.json`](../pytest-slow-baseline.json) · [`test-baseline.json`](../auralis-web/frontend/test-baseline.json) |
| Release state | Prepared, blocked on installed-artifact validation and signing | [releases/RELEASE_CHECKLIST_1_5_1.md](releases/RELEASE_CHECKLIST_1_5_1.md) |

Tagged lines to date: `1.0.0-beta.*` → `1.1.0-beta.*` → `1.2.0-beta.*` →
`v1.2.1-beta.1`. Versions 1.5.0 and 1.5.1 are source milestones only; neither has a local tag.

---

## 2. The original vision — shipped

Every major track from the 2025 roadmap is in production code or has been deliberately replaced.
Verify any row against the linked subsystem doc.

| 2025 plan | Status | Where it lives now |
|-----------|--------|--------------------|
| **25D fingerprinting** (extraction, storage, background queue) | Shipped | [`analysis/fingerprint/`](../auralis/analysis/fingerprint/) · [subsystems/fingerprinting.md](subsystems/fingerprinting.md) |
| **Sampling strategy** (5 s chunks, ~90% accuracy, big speedup) | Replaced | Analysis is a property of the whole track, so the fingerprint reads the entire track (algorithm v13); only mastering is chunked |
| **Background fingerprinting** (worker pool, `.25d` sidecars, scanner integration) | Shipped | `FingerprintExtractionQueue`, atomic claiming, a fair and cancellable analysis gate |
| **Similarity graph system** (weighted 25D distance, kNN, API, UI) | Shipped | `distance.py`, `knn_graph.py`, `similarity_graph_repository.py`, [`routers/similarity.py`](../auralis-web/backend/routers/similarity.py) |
| **25D adaptive mastering** (fingerprint → one track-level plan, deterministic chunks) | Shipped | `ContinuousMode` maps 25D → 3D processing space; `CrossDimensionalGuard` |
| **Continuous enhancement space** (replace discrete presets with interpolation) | Shipped, default | `ContinuousMode`; the preset list is narrowed to `adaptive` |
| **Rust DSP acceleration** | Shipped, narrowed | [`vendor/auralis-dsp/`](../vendor/auralis-dsp/) carries the 25D fingerprint only; the other PyO3 bindings and the standalone server are gone |
| **Phase 1 testing infrastructure** (boundary/invariant suites) | Shipped, far exceeded | `tests/` plus CI ratchets on failures, file size, comments, and path references |
| **Desktop binaries** (AppImage, Flatpak, DEB, Windows, macOS ARM64 `.dmg`) | Prepared | `build-release.yml` builds and checksums all five; installed validation and signing remain, see [section 4](#4-active--near-term) |

**Bottom line:** the "revolutionary features enabled by the 25D system" are the shipped
architecture. See [architecture/overview.md](architecture/overview.md).

---

## 3. Course-corrections since the old plan

Things the old roadmap listed, or the project later built, that did not survive contact with the
code:

- **MSE / WebM-Opus streaming was abandoned, not shipped.** The old roadmap celebrated a
  "Unified MSE + Multi-Tier Buffer streaming (4,518 lines)" milestone. That approach was
  replaced: the shipped browser player is the **Web Audio API** with a circular `Float32Array`
  PCM buffer + `AudioWorkletNode`, fed by binary PCM WebSocket frames. `MediaSource` /
  `SourceBuffer` / WebM / Opus appear **nowhere** in the current backend or frontend. The
  `docs/archive/guides/MSE_*` and `MULTI_TIER_BUFFER_*` guides are legacy. See
  [subsystems/frontend.md](subsystems/frontend.md).
- **Presets were narrowed to `adaptive`.** The gentle, warm, bright, punchy, and live presets
  were deleted from the engine, API, settings, and frontend. Do not reintroduce a preset list;
  the continuous space is the control surface.
- **Analysis is whole-track; only rendering is chunked.** Fingerprinting per chunk or per
  window was replaced by one whole-track analysis that every chunk of a render applies.
- **The preference-learning engine was removed (#5763).** Nothing consumed it. The reference
  seeder in [`auralis/learning/`](../auralis/learning/) remains.
- **Dead settings and surfaces were deleted:** crossfade, gapless, and replay-gain settings
  (#6683), the `mastering_recommendation` broadcast and its service (#6579), the queue
  history/undo feature (#5526), and nine unused PyO3 bindings (#5764).
- **The "architecture cleanup" track (remove `SpectrumMapper`) never happened.**
  `SpectrumMapper` is still constructed by `HybridProcessor`'s setup in
  [`hybrid_setup.py`](../auralis/core/hybrid_setup.py). No issue tracks folding it into
  `AdaptiveTargetGenerator`; file one if it becomes a priority.

---

## 4. Active / near-term

The active target is **v1.5.1 recovery**. The
[recovery audit](audits/AUDIT_RECOVERY_2026-07-24.md) records the original findings, the
[release checklist](releases/RELEASE_CHECKLIST_1_5_1.md) is the tag gate, and the
[release notes](releases/RELEASE_NOTES_1_5_1.md) summarize its status.

- **Done:** the three product blockers (fresh fingerprint persistence #5530, mono enhancement
  #5550/#6118, rapid track selection #4426); the supervised source launcher and `/api/ready`
  readiness, covered by a collected startup smoke; Electron supervision of the packaged backend.
- **Remaining before a tag:** the packaged-Electron launch in its default sandbox configuration
  and every installed artifact on its target platform; the audit's eleven-point definition of
  "working" against a fresh home and the repeated-run gates; Windows and macOS signing and
  notarization, and a published checksum-signing key fingerprint (#4905).

The [PRD index](prd/README.md) holds the acceptance criteria for the two recovery slices.

1. [Application startup](prd/application-startup.md) establishes process ownership, readiness,
   and an isolated launch smoke test.
2. [Library and playback recovery](prd/library-playback-recovery.md) uses that launch path to
   verify the complete scan-to-playback workflow.

Broad lint cleanup, unfinished cache/similarity surfaces, and visual polish are outside the
"working" milestone unless they block that slice.

---

## 5. Open backlog (real, tracked)

The backlog is quality and tech debt, not vision features. Most items are LOW-severity findings
from the 2026-10 and 2026-11 audits; the tracker carries each one's severity and labels. Items
that need a decision before work starts are listed first.

### Decisions and larger items

| Item | Issue | Notes |
|------|-------|-------|
| Code-signing credentials | #4905 | Windows Authenticode and Apple Developer ID plus notarization need the maintainer's certificates; the GPG signing of `SHA256SUMS.txt` is wired and waits on a key |
| Per-album mastering consistency | #3481 | Phase 1 target derivation landed; the render pipeline does not use it |
| Wire EQ, dynamics, level matching, and genre override into the offline pipeline | #5098 | Follow-up to #3490 |
| Mastering fingerprint window | #6346 | `MasteringFingerprint` still reads the 90 s body window while the 25D fingerprint is whole-track |
| Fingerprint air band | #6721 | Analysis at 22.05 kHz stops at 11 kHz, so no path corrects the top octave |
| Offline loudness maximizer window | #6361 | Driven by a 30 s middle window, not the whole track |
| CSP `script-src 'unsafe-inline'` | #5484 | Revisit when Vite CSP/nonce support or a browser test suite lands |

### Release, desktop, and security hardening

| Theme | Issues |
|-------|--------|
| Unsigned auto-update pipeline | #4905 |
| FFmpeg floor is 4.0 and none is bundled for Windows/macOS | #6180 |
| Electron main-process security events are console-only when packaged | #6187 |
| Loopback addressing (`localhost` may resolve to `::1`) | #6169 |
| WebSocket limits (`ws_max_size`, unbounded connections, paused streams hold slots; a 16-connection cap landed) | #6171 |
| Log hygiene: unthrottled origin-rejection warnings, per-request access log, absolute paths in errors | #6486, #6487, #6383 |
| `CONFIG.md` omits about 15 tunables | #6489 |

### Audio engine and DSP integrity

| Theme | Issues |
|-------|--------|
| Offline mastering gain and clipping: unbounded peak-normalize gain, no floor on near-silent input, stage-1 soft clip, true-peak edge zero-padding, decoder overshoot hard-clip | #6353, #6386, #6388, #6385, #6360 |
| Input contract and safety: float16/longdouble input, one Inf sample poisons the compressor, out-of-phase stereo gain, truncated WAV bypasses the loaders' check | #6369, #6354, #6355, #6387 |
| DC offset removal landed in `HybridProcessor` (`0e1677ab8`); the issue is still open | #5187 |
| Per-chunk loudness mixes the fingerprint RMS proxy with K-weighted loudness | #5700 |
| Realtime path: per-buffer AGC bursts, auto-master headroom cap, dead realtime state | #6106, #6370, #6381 |
| Legacy and divergent tables: `AdaptiveMode` hard thresholds, exciter boost, band-target tables, inline EQ edges, stereo-width scales | #6371, #6372, #6373, #6648, #6119 |
| Reference-mode processor without a reference fails with the wrong error | #6374 |
| Container and codec edge cases: WAV past 4 GiB, FLAC with unknown length, RIFF size placeholders, pre-decode budget uses the source channel count | #6357, #6358, #6359, #6382 |
| Gapless transition zero-pads the last chunk | #6109 |
| Temp-folder handling | #6384 |

### Fingerprint and similarity

| Theme | Issues |
|-------|--------|
| Whole-track Rust accumulation in f32; centroid/rolloff from one 2^N FFT; analysis gate bypassed by `fingerprint_preloaded` | #6362, #6363, #6364 |
| `phase_coherence` reads 0.0 for realistic levels; mislabelled secondary values; duplicated header probes | #6389, #6394, #6393 |
| No handshake between the Rust engine and `FINGERPRINT_ALGORITHM_VERSION`; malformed cache files raise; `FingerprintUnavailable` swallowed | #6391, #6390, #6392 |
| ML genre features are degenerate | #6365 |
| Enqueue-all ignores outdated rows; inline re-implementation of enqueueing | #6451, #6458 |
| Explain and vector schemas: DB-column names, all-optional fields | #6480, #6481 |
| Pre-computed K-NN graph is never built automatically; auto-fit logs errors for the normal empty-library case | #5922, #6488 |

### Player, queue, and streaming

| Theme | Issues |
|-------|--------|
| Engine and state-manager divergence: queue pointer follows no frontend navigation, state bypasses on `load_file()`/gapless, whole-queue deep copies, four track-changing locks | #5937, #6379, #5960, #6082 |
| Transport edge cases: `stop()` then `play()` during auto-advance, terminal ERROR after gapless, failure after audio swap, negative `start_index`, `enable_auto_mastering` does not enable the stage | #6375, #6376, #6377, #6378, #6380 |
| Production `load_file()` decodes and fingerprints for nothing | #5708 |
| `StreamlinedCacheWorker` does no work; `get_wav_chunk_path` has no caller | #5959, #6468 |
| WebSocket handlers: rejected `play_enhanced` overwrites shared settings, seek/preset rejections omit `command`, `track_id` bounds, write-only stream state, `handle_play_normal` bookkeeping, single-flight follower polls forever, `teardown_connection` swallows cancellation | #6466, #6479, #6478, #6464, #5076, #6491, #6461 |
| Job queue: cancelled jobs keep their slot, temp files swept only as a side effect | #6473, #6475 |
| Upload quota cannot be released | #6453 |

### Library, scanner, and database

| Theme | Issues |
|-------|--------|
| Rescan and prune: new album never gets artwork, deleted folders leave rows | #6366, #6367 |
| Metadata normalization: non-Latin artists collapse, numeric ID3v1 genres stored verbatim | #6368, #6395 |
| Concurrent scans share one frame stream | #5878 |
| Repository hygiene: hand-rolled rollbacks, unwritten columns, `get_all_artists()` hydration, artwork unlink before commit | #6403, #6397, #6399, #6401 |
| Pool exhaustion returns HTTP 500; unbounded `GET /api/playlists/{id}` | #6490, #6455 |

### Backend API contract and tests

| Theme | Issues |
|-------|--------|
| Schemas: `PlaylistListResponse` envelope, inline `Literal` sets, stale docstrings, same name with different meaning | #6482, #6483, #6484, #6485 |
| Startup wiring of the `.25d` sweep untested | #6501 |
| Vacuous negative tests and dead fixtures | #6499, #6500 |

### Frontend

| Theme | Issues |
|-------|--------|
| Accessibility and contrast: semantic status colors and brand accent as text, focus after Back, track-row Tab stops, Escape in nested dialogs, remappable shortcuts, roving tabindex, list size/position, alt text, toggle names, table columns, dialog error boundaries | #6400, #6408, #6407, #6409, #6410, #6411, #6417, #6465, #6467, #6469, #6470, #6416 |
| Performance: unvirtualized playlist table, 60 Hz album pane, visualization switch, abort signals | #6405, #6406, #6463, #6404 |
| Request and state handling: queue re-fetch on remount, `refresh()` supersession, retry rules, search races, queue index reconciliation, `isPlaying` source, stale initial-state fetches, health poll overlap, WebSocket refcount | #6396, #6398, #6402, #6456, #6412, #6418, #6015, #5655, #6460, #6423 |
| Dead or write-only state: connection slice, `player.streaming.normal`, unmounted components, write-only Redux fields, unreachable drag-drop branches, unused queue selectors, dead queue-subscription keys | #5615, #5616, #5628, #6039, #6047, #6419, #6421 |
| Component and hook size, prop drilling, duplicated debounce and literals | #6413, #6414, #5630, #6415, #6457, #6459 |
| Error text and response validation | #6452, #6454, #6462 |
| Artists list on WS/queue payloads | #6722 |
| Test gaps: gates skip some files, sort modes, settings folder flow, playlist dialog, orphaned fixtures | #6472, #6474, #6476, #6477, #6420 |

### Tooling and dependencies

| Theme | Issues |
|-------|--------|
| `numpy<2.5` ceiling revisit, unpinned CI test tools, anyio plugin warning | #6347, #6348, #6349 |
| Legacy typing aliases, unused root dependencies, orphaned tooling configs | #6350, #6351, #6352 |
| Python function-length census | #5481 |

**Test-suite health:** the CI baselines are empty, so any new failure fails the job. Two files
still hang when run as whole files, `tests/backend/test_system_api.py` and
`tests/concurrency/test_thread_safety.py`, so CI excludes them; gate local work on targeted
domain tests. See [CONTRIBUTING.md](CONTRIBUTING.md#4-testing).

---

## 6. Longer-term vision (foundation built, depth/UX remaining)

The ambitious 2025 vision items are no longer greenfield; the primitives exist. What remains
is depth, UX, and productization:

| Vision | Foundation in code | Remaining |
|--------|--------------------|-----------|
| "Find songs like this" | Similarity API + kNN graph shipped; a track's menu opens a **Find Similar Tracks** list | Richer discovery UX, cross-genre tuning |
| Intelligent / flow playlists | Similarity distance and kNN graph | Playlist generation UX, sequencing (the earlier `RecommendationService` was deleted, #6579) |
| Per-album consistency | Album-consistent target derivation (#3481) | Wiring into the render pipeline |
| Section-aware / real-time adaptation | `ContinuousMode` applying one track-level plan per chunk | Intra-track section detection |
| Enhancement profile sharing | Deterministic fingerprint→params | Export/import + sharing surface |

Treat these as directions, not committed milestones; prioritize against user feedback.

---

## 7. Sources of truth

When this doc and the code disagree, the code wins.

- **Version** → [`auralis/version.py`](../auralis/version.py)
- **DB schema and fingerprint algorithm versions** → [`auralis/__version__.py`](../auralis/__version__.py)
- **What shipped** → git tags + [releases/CHANGELOG.md](releases/CHANGELOG.md)
- **Release gate** → [releases/RELEASE_CHECKLIST_1_5_1.md](releases/RELEASE_CHECKLIST_1_5_1.md)
- **How it works now** → [architecture/](architecture/) + [subsystems/](subsystems/)
- **Chunk geometry / fingerprint dims** → the source-of-truth registry in
  [architecture/overview.md](architecture/overview.md#source-of-truth-registry)

Superseded planning docs (including the 1.1.0-cycle roadmap) live in
[archive/](archive/) — reference only.
