# Auralis Audio Engine Audit — 2026-08-23

**Scope**: `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/analysis/`, `auralis/library/`, `auralis/services/`, `vendor/auralis-dsp/`. All 7 dimensions, `--depth deep`, no `--limit`.
**Out of scope**: React frontend, FastAPI backend routing/WebSocket layer, Electron desktop (one finding below crosses this boundary — flagged explicitly).
**Prior reports**: `AUDIT_ENGINE_2026-07-12.md`, `AUDIT_ENGINE_2026-07-25.md`, `AUDIT_ENGINE_2026-07-29.md`, `AUDIT_ENGINE_2026-08-13.md`

---

## Executive Summary

| Severity | NEW findings |
|---|---|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 2 |
| LOW | 5 |
| **Total** | **9** |

**Zero regressions** across all 7 dimensions — every prior fix checked (roughly 40 individual re-verifications across the four earlier engine-audit rounds) was confirmed still present at HEAD. This is the fifth deep pass over this engine, and the trend is holding: Dimension 1 (Sample Integrity) found **zero** new issues for the second audit in a row — the pipeline's copy/dtype/clip/NaN-guard discipline is genuinely solid now, not merely unexamined.

**Key themes**:
1. **Two independently-discovered HIGH findings share the same shape**: a state-machine/data-path assumption that holds for the common case breaks under a less-common-but-real concurrent or format-specific condition, with no test coverage for the gap. Neither is a regression — both are latent gaps in otherwise well-hardened code.
2. **The chunk-audio I/O path (`ENG-D4-25-2`) is a repeat finding** — flagged independently by two different audit passes on 2026-07-29 (once from this engine audit, once from the backend audit) but never actually tracked as a GitHub issue, so it silently persisted for nearly a month. This is exactly the kind of gap `/audit-publish`'s dedup pass exists to close, and this report's own publish pass will file it properly this time.
3. **Two MEDIUM findings are both "the common path is correct, the less-common path silently isn't"**: `downmix_to_stereo()` handles canonical 5.1/7.1 correctly but silently misroutes 4.0/5.0-no-LFE audio; `FingerprintNormalizer.fit()` is correct under a single caller but has no lock against the exact concurrent-caller scenario the codebase's own startup sequence and REST API both create.
4. **The engine's config-reachability debt continues to accumulate**: `DIM2-01` extends the already-open dead-`UnifiedConfig`-parameter finding (ENG-D2-02) by three more fields, one of which actively misdocuments behavior that was never implemented (`processing_sample_rate`'s "saves 4x memory" claim).

**Most impactful findings**:
- **ENG-D3-NEW-01** (HIGH): a user's `pause()` landing during a `next_track()`/`previous_track()` transition is silently overridden back to PLAYING — the mirror-image of an already-fixed `stop()`-racing bug class, except `pause()` never got the equivalent guard.
- **ENG-D4-25-2** (HIGH): every chunk of every MP3/M4A/AAC/OGG/WMA/OPUS track triggers a full-track FFmpeg transcode + full float32 decode just to serve one ~20-25s window — a ~60× CPU/I/O amplification on a hot streaming path, known since 2026-07-29, never fixed.

---

## Findings

### HIGH

#### ENG-D3-NEW-01: `pause()` racing a gapless `next_track()`/`previous_track()` resume is silently overridden back to PLAYING
- **Dimension**: Player State
- **Location**: `auralis/player/player_queue_navigation_mixin.py:106-139` (`next_track`), `:141-178` (`previous_track`); `auralis/player/playback_controller.py:137-160` (`play`)
- **Status**: NEW
- **Description**: Both `next_track()` and `previous_track()` capture `was_playing` before a potentially slow, disk-I/O-bound track transition, then unconditionally call `self.playback.play()` afterward if `was_playing` was true — re-checking only `_stop_requested` (per the #4126 fix). `pause()` has no equivalent signal: it only flips `state` to `PAUSED`, doesn't set `_stop_requested` (by design, per #3296/#3712, to distinguish "user pressed stop" from "load reset state as a side effect"). If a user pauses while a transition is in flight, `play()` silently overrides the `PAUSED` state back to `PLAYING` — no error, no log line, indistinguishable from a legitimate resume.
- **Evidence**: `previous_track()`'s `load_file()` and `next_track()`'s prebuffer-miss fallback are both realistic-duration blocking disk reads. The project's own regression suite (`test_previous_track_resume.py`'s `TestConcurrentStopDuringPrevious`) tests this exact race shape for `stop()` — proving the team is aware of and has closed it for `stop()` — but no test anywhere exercises the `pause()` variant. Both `next_track()`/`previous_track()` (via `POST /api/player/{next,previous}`) and `pause()` (via `POST /api/player/pause`) are independently reachable from separate concurrent HTTP requests.
- **Impact**: The user explicitly pauses; 10s-100s of ms later, playback silently resumes with no signal that the pause was overridden. This is the mirror-image of the already-fixed-for-`stop()` bug class — the fix that closed the window for `stop()` relies on a signal `pause()` doesn't have.
- **Suggested Fix**: Add a `_pause_requested`-style guard mirroring `_stop_requested`'s pattern, or have `next_track()`/`previous_track()` re-check `self.playback.is_paused()` immediately before calling `play()`, treating "now paused" the same as "stop requested." The re-check must happen inside/adjacent to `PlaybackController._lock` so a `pause()` landing in the small remaining window doesn't reopen the race one level down.

#### ENG-D4-25-2: Chunk-audio loader still full-decodes the entire track on any FFmpeg-only-format chunk read — persists unfixed since two independent 2026-07-29 audit passes
- **Dimension**: Audio I/O *(boundary case: location is in `auralis-web/backend/`, nominally out of this audit's scope — but it's the sole per-chunk audio *loader*, an I/O-path bug not a routing/WebSocket one, so it's reported here where it was found; also cross-reference to `/audit-backend`'s domain)*
- **Location**: `auralis-web/backend/core/chunk_operations.py:106-172` (`ChunkOperations.load_chunk_from_file`)
- **Status**: NEW — raised previously as `AUDIT_ENGINE_2026-07-29`'s "ENG-D4-1" and independently as `AUDIT_BACKEND_2026-07-29`'s "BE8-06," but never became a tracked GitHub issue nor appears in `.claude/issues/` — treated as NEW per the dedup protocol (no issue-tracker match), not a duplicate of an untracked narrative finding.
- **Description**: `load_chunk_from_file()` always opens the file with `sf.SoundFile(filepath)` directly — no extension check against `FFMPEG_FORMATS`/`SOUNDFILE_FORMATS`, unlike every loader in `auralis/io/` itself. libsndfile cannot open `.mp3/.m4a/.aac/.ogg/.wma/.opus` at all, so for every chunk of every FFmpeg-only-format track, the `try` unconditionally raises and falls back to `unified_loader.load_audio()` — a full FFmpeg transcode plus a full float32 decode of the **entire track** — merely to slice out one ~20-25s chunk window. This fires **once per chunk**, not once per session.
- **Evidence**: For a 10-minute M4A at the documented 10s chunk interval, that's ~60 full-track transcode+decode passes to play the file once — confirmed unchanged at HEAD, matching what both 2026-07-29 passes independently derived.
- **Impact**: Every streamed chunk of six of the eleven supported formats pays a full-track transcode+decode instead of a bounded window read, concurrently with live playback/enhancement — CPU/I/O waste, repeated re-triggering of every guard in `load_audio()` against the whole track, and a transient multi-hundred-MB-to-GB float32 allocation per concurrent chunk request. Exactly the anti-pattern #4497 already fixed once for metadata-only reads; never applied to the method loading actual chunk audio, which runs far more often.
- **Suggested Fix**: Check the file extension against `FFMPEG_FORMATS` up front before attempting `sf.SoundFile`. For FFmpeg-routed formats, either decode once per streaming-session instance and cache the buffer, or use `load_with_ffmpeg`'s existing `offset`/`duration` parameters (added for #5110) to extract only the needed window via `ffmpeg -ss/-t` — the bounded-decode primitive this method needs already exists in the same codebase, unused here.

### MEDIUM

#### ENG-D4-25-1: `downmix_to_stereo` assumes a fixed 5.1/7.1-with-LFE channel order for any input between 3 and 8 channels, silently misrouting or dropping content on other real layouts (4.0/quad, 5.0 no-LFE)
- **Dimension**: Audio I/O
- **Location**: `auralis/io/processing.py:122-207` (`downmix_to_stereo`), consumed by `auralis/io/loader.py:171-180` and `auralis/io/loaders/soundfile_loader.py:126-134`
- **Status**: NEW
- **Description**: Hardcodes channel *index* → channel *role* by position (index 2=Center, 4=Ls, 5=Rs) — correct only for canonical 5.1/7.1. Nothing in the call chain reads the file's actual channel layout mask (`sf.info()` exposes only a channel *count*). For genuine 4.0/quad (L,R,Ls,Rs, no Center/LFE): index 2 (the true Ls) is read as "Center" and mixed equally into both outputs; index 3 (the true Rs) is silently dropped entirely. For 5.0 (no LFE): the real Ls is discarded and the real Rs is imaged onto the wrong (left) side. Sample count/dtype/shape invariants are all preserved, so nothing downstream detects it — no exception, no distinguishing warning.
- **Evidence**: The regression suite for this function (`test_downmix_3743.py`) only exercises 6ch and 8ch plus the trivial 1/2-channel passthroughs — no test for 4ch or 5ch, so this gap was never exercised even by the tests the original #3743 fix added. FFmpeg's `-ac 2` path is unaffected (it derives real layout from container/stream metadata) — this is native-loader-only (WAV/AIFF/AU).
- **Impact**: A genuine 4.0/5.0-no-LFE multichannel master — a plausible input for a mastering tool (quad and 5.0 masters exist for surround-music/DVD-Audio-era content) — gets an incorrect stereo image: discrete-left content centered, one full channel dropped outright. Audio-integrity degradation on a documented, previously-fixed code path, narrower in domain than #3743's original bug.
- **Suggested Fix**: Either narrow the function's guaranteed-correct claim to exactly 6ch/8ch and route any other channel count through FFmpeg's `-ac 2` instead, or read the real channel mask where available (falling back to the positional assumption only when no mask is present, with a warning). At minimum, add regression tests for `n_channels ∈ {4, 5, 7}` so the gap is visible.

#### D6-1: `FingerprintSimilarity`/`FingerprintNormalizer.fit()` has no lock against a concurrent second `fit()`, letting two callers interleave writes into the shared normalization-stats dict
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/normalizer.py:118-207` (`fit()`, 25-iteration loop with no lock); `auralis/analysis/fingerprint/similarity.py:88-104`; `auralis-web/backend/config/startup.py:892-925` (`_init_similarity_system`, spawns an untracked daemon-thread auto-fit); `auralis-web/backend/routers/similarity.py:428-478` (`POST /api/similarity/fit`)
- **Status**: NEW (distinct from Existing #4682, which is about the daemon thread never being joined/cancelled on shutdown — a lifecycle bug, not this concurrent-write race)
- **Description**: The startup auto-fit daemon thread and `POST /api/similarity/fit` can both pass their independent `is_fitted()` checks and proceed into `fit()`'s loop concurrently, since the check-then-fit sequence is not atomic and nothing serializes it. Neither `FingerprintSimilarity` nor `FingerprintNormalizer` declares any lock. `fit()`'s per-dimension loop does 25 separate dict-key writes, not one atomic swap.
- **Impact**: Two concurrent `fit()` runs, each reading a possibly-different snapshot of the library, can leave `self.stats` holding a mix of dimension-stats from two different runs. Every subsequent `normalize()`/`find_similar()` call then normalizes against inconsistent baselines — silently wrong similarity distances, kNN neighbor lists, and the persisted similarity graph, with no crash and no log line pointing at the cause. Self-limiting (a later uncontended `fit()` clears the corruption), but produces a wrong-result window each time the race fires.
- **Suggested Fix**: Build the new stats dict into a local variable inside `fit()` and assign `self.stats = new_stats` once at the end (a single atomic reference swap), combined with a lock around the `is_fitted()`-check + `fit()`-call sequence in the router handler so a second concurrent `/fit` request is rejected/no-ops instead of racing.

### LOW

#### DIM2-01: Three more `UnifiedConfig` parameters are dead — including one whose docstring claims a memory/time-saving behaviour that was never implemented
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/config/unified_config.py:40-59` (`processing_sample_rate`, `max_length`, `temp_folder`)
- **Status**: NEW (corrects/extends Existing ENG-D2-02, which examined the same constructor and asserted the opposite for one of these three)
- **Description**: `processing_sample_rate`'s inline comment claims audio is downsampled on load when set ("saves 4x memory and time") — no code anywhere reads this field to perform that downsampling. `max_length` and `temp_folder` are validated at construction and never read again. The prior 08-13 audit's ENG-D2-02 finding explicitly asserted `processing_sample_rate` was "genuinely read downstream" — that claim is incorrect, verified via grep (the only non-definition reference in the repo is a regression test snapshotting the field's value, not exercising any downsampling behavior).
- **Suggested Fix**: Either wire `processing_sample_rate` into the loader stack (resample on load when set, mirroring the comment's intent), or remove all three fields and drop the misleading comment. Low priority given ENG-D2-02 already covers the bulk of this constructor.

#### D5-NEW-1: `process_chunk`'s Stage 3 output-normalization branch is permanently unreachable
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_process_chunk.py:117-155`; `auralis/core/mastering_branches/continuous.py:239`; `auralis/core/mastering_branches/base.py:26-33`
- **Status**: NEW
- **Description**: `ContinuousMasteringBranch` is the sole branch class and always sets `needs_output_normalize = False` ("this path performs its own final normalization"). Stage 3's `if needs_output_normalize:` branch in `mastering_process_chunk.py` can therefore never execute under the current architecture.
- **Impact**: No behavioral bug — normalization is genuinely handled elsewhere. Cost is maintainability: a future contributor sees a live-looking conditional stage and reasonably assumes it fires under some condition; it's also untested dead code that could rot silently.
- **Suggested Fix**: Delete Stage 3 (folding its "leave headroom for playback" comment into `continuous.py` if still relevant), or drop the `ProcessingBranch` ABC indirection so there's no per-branch contract implying a second implementation might exist.

#### D6-2: The rule-based ML genre classifier is a process-lifetime singleton hardcoded to 44.1kHz; any caller configured at a different `internal_sample_rate` gets silently wrong spectral/temporal features with no way to pass the real rate through
- **Dimension**: Analysis
- **Location**: `auralis/analysis/ml/genre_classifier.py:29-42,156-167`; `auralis/analysis/ml/feature_extractor.py:31-38`; `auralis/core/analysis/content_analyzer.py:44-47,265-273`
- **Status**: NEW — severity kept at LOW because dormant (every live production path uses the 44100 default), but would become a live MEDIUM/HIGH-accuracy bug the moment any caller sets a non-default `internal_sample_rate` — an explicitly supported, logged config option, not a hypothetical.
- **Description**: `RuleBasedGenreClassifier.__init__` builds its `FeatureExtractor` with the hardcoded default `sample_rate=44100`; `classify()` takes no `sr` parameter. `ContentAnalyzer` correctly threads its own configured sample rate into every other feature call in the same method — only the ML-classifier call silently drops it. Because the classifier is an `lru_cache(maxsize=1)` singleton, the mis-scaled `FeatureExtractor` cannot self-correct once constructed at the wrong rate.
- **Suggested Fix**: Add an optional `sr` parameter to `classify()` and either rebuild/cache a `FeatureExtractor` per distinct sample rate seen, or resample incoming audio to the extractor's fixed rate before feature extraction — mirroring what `AudioFingerprintAnalyzer` already does via `_TARGET_SR` for the same reason.

#### D7-1: `QueueRepository.update_queue_state()` persists an out-of-bounds `current_index` when `track_ids` shrinks without `current_index` in the same call
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/queue_repository.py:97-149`
- **Status**: NEW
- **Description**: `_validate_index` only runs when `'current_index' in updates`. A caller supplying `track_ids` alone (shrinking the queue) leaves the existing `current_index` unchecked against the new, shorter list. The sibling `set_queue_state()` always validates the pair together.
- **Impact**: Violates the project's own "queue index valid" invariant. Currently unreachable in production (zero callers of `update_queue_state()` outside one test whose scenario happens not to trip the bug) — becomes live the moment any caller updates `track_ids` alone.
- **Suggested Fix**: Always resolve the effective `track_ids` and effective `current_index` (new value if supplied, else existing) and validate that pair whenever either field changes.

#### D7-2: `TrackRepository.update_metadata()` returns a Track with no relationships eager-loaded; `refresh()`+`expunge()` doesn't fix it, and `Track.to_dict()` silently swallows the resulting `DetachedInstanceError` with no log line
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_mutation.py:161-195`; `auralis/library/models/track.py:118-197`
- **Status**: NEW
- **Description**: `update_metadata()` loads the track with a bare query (no eager-load options), unlike the sibling `update()`/`update_by_filepath()` which explicitly re-query with `_track_eager_options()` after commit. The returned object is fully detached with `album`/`artists`/`genres` unloaded. Compounding it: `Track.to_dict()`'s relationship reads are wrapped in a bare, unlogged `except Exception` — predates the project's own `_safe_collection()`/`_safe_scalar()` helpers (built for exactly this situation, and which log a WARNING) and was never migrated onto them.
- **Impact**: Not triggered today — the sole caller only reads `.filepath` from the return value. Latent: any future caller serializing this method's return value (e.g. a WebSocket broadcast or batch response including album/artist/genre fields) gets a silently-empty result with no diagnostic trail.
- **Suggested Fix**: Re-query with `_track_eager_options()` after commit (matching the sibling methods), or force-touch the three relationships before `expunge()`. Separately, migrate `Track.to_dict()`'s three bare `except Exception` blocks onto `_safe_collection()`/`_safe_scalar()` repo-wide.

---

## Relationships

- **ENG-D3-NEW-01** is the structural mirror of the already-fixed `stop()`-racing-a-transition bug class (#3669/#4126): both are "a fast-path resume doesn't re-check a state change that happened mid-transition." The `stop()` case got a dedicated signal (`_stop_requested`); `pause()` never did. Any fix should consider generalizing the guard rather than adding a second bespoke `_pause_requested` flag that could itself drift from `_stop_requested`'s behavior later.
- **ENG-D4-25-2** and **ENG-D4-25-1** share a root file family (`auralis/io/` and its direct consumers) but are independent bugs — one is a missing extension-routing check, the other a channel-layout assumption. Both are silent-failure-mode bugs on the native/chunked I/O path, a pattern worth a dedicated regression-test sweep once both are fixed (see Prioritized Fix Order).
- **D6-1** and Existing #4682 are two distinct bugs in the same two-line startup mechanism (`_init_similarity_system`'s daemon thread): #4682 is "the thread is never joined/cancelled," D6-1 is "the thread's work can race another caller's work." Fixing #4682 alone (adding a stop signal) would not fix D6-1.
- **DIM2-01** extends the already-open **ENG-D2-02** (9 dead `UnifiedConfig` parameters) by three more fields and corrects that report's own claim that `processing_sample_rate` was verified live — worth folding into the same tracking issue rather than filing separately, since the remediation (delete-or-wire-in) is identical.
- **ENG-D4-25-2**'s domain crosses into `auralis-web/backend/` — when this report is published, consider applying the `backend` label alongside `dsp`/`audio-integrity` so it surfaces in both this audit's engine tracking and any backend-focused triage.

---

## Prioritized Fix Order

1. **ENG-D4-25-2** (HIGH) — fix first: known for a month, actively wastes CPU/I/O on every FFmpeg-format track streamed today, and the fix primitive (`load_with_ffmpeg`'s `offset`/`duration`) already exists unused in the same codebase. Highest ratio of impact to effort.
2. **ENG-D3-NEW-01** (HIGH) — user-facing correctness bug with a real (if narrow) timing window; fix by mirroring the proven `_stop_requested` pattern rather than inventing a new mechanism.
3. **D6-1** (MEDIUM) — silent wrong-similarity-results window; the atomic-dict-swap fix is a small, low-risk change with a clear correctness payoff for anyone relying on similarity/recommendations.
4. **ENG-D4-25-1** (MEDIUM) — narrower blast radius (4.0/5.0-no-LFE sources are less common than the FFmpeg-format-chunk path above) but a real audio-integrity bug on a mastering tool's native-loader path; fix alongside #1 since both touch the same I/O boundary.
5. **D7-1, D7-2** (LOW) — both currently unreachable in production; fix opportunistically before either path gains a new caller, since both are cheap, well-understood fixes once identified.
6. **D5-NEW-1, DIM2-01** (LOW) — dead-code/dead-config cleanup; no urgency, bundle with other tech-debt work.
7. **D6-2** (LOW, dormant) — fix before ever enabling a non-default `internal_sample_rate` in production; not urgent today since nothing exercises the path, but cheap to fix now while the shape is fresh in this report.

---

*Generated 2026-08-23 by `/audit-engine` (7 dimension subagents, `--depth deep`, no `--limit`).*
