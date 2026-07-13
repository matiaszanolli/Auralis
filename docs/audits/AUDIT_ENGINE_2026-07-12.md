# Audio Engine Audit — 2026-07-12

**Scope**: Core audio engine — DSP pipeline, player state machine, audio I/O, parallel processing, analysis/fingerprint subsystem, library & database. React frontend, FastAPI routing, and Electron are out of scope (but engine-adjacent backend I/O paths — FFmpeg subprocess lifecycle, chunked metadata load — were traced where they are the direct consumer of the I/O layer).

**Method**: Seven dimension agents performed a fresh read of the current `master` source, traced full call graphs, and deduplicated against the 142 open GitHub issues (`gh issue list`), `docs/audits/`, and `.claude/issues/`. Findings are only included where the agent could not disprove them.

---

## Executive Summary

**Total: 20 findings — 0 CRITICAL, 5 HIGH, 5 MEDIUM, 10 LOW** (21 raw findings; one cross-dimension duplicate — the crossfade-label issue found by both Dim 2 and Dim 5 — merged).

The engine's core audio-integrity invariants are in excellent shape. Every dimension independently confirmed that sample-count preservation, copy-before-modify, dtype propagation, NaN/Inf containment, and pre-PCM clipping are enforced with explicit asserts and guards backed by dozens of numbered regression fixes. **No CRITICAL was found** — no sample-count mismatch in a live DSP stage, no in-place mutation of a caller-owned array, no DB-corruption path, no shared-buffer race in production audio.

The real risks cluster in three themes:

1. **Lock scope in the player / auto-advance path (HIGH).** Two extensions of already-fixed deadlock/dropout classes remain: `record_track_completion()` fires app-level callbacks while `_audio_lock` is held (reopens the #3781 deadlock class via an un-deferred notify path), and the gapless fallback runs a blocking disk load inside `_audio_lock` (reintroduces the #3656 audible-dropout pattern).

2. **FFmpeg subprocess & metadata I/O (HIGH).** Cancelling a job cannot stop an in-flight `subprocess.run` FFmpeg decode (orphaned CPU/thread-pool slot for up to 5 min), and chunked-playback metadata lookup silently falls back to a full-file decode for every FFmpeg-routed format (MP3/M4A/AAC/OGG/WMA/OPUS) — undermining the bounded-decode architecture and reintroducing OOM exposure on long-form content.

3. **Mono-file crash + latent robustness gaps (HIGH + LOW/MEDIUM).** A true mono input crashes offline mastering with an unhandled `ValueError` (data loss for that job). The remaining findings are latent (unreachable-today parallel/PyO3 paths, pre-loaded-audio fast path) or quality/consistency issues (genre eager-load data loss, engine-disposal leak, stereo-width scaling, crossfade mislabel).

**Most impactful to fix first**: ENG-D1-1 (mono crash — real data loss, trivial fix), ENG-D3-1 (latent full-application hang), ENG-D4-1/ENG-D4-2 (subprocess orphaning + full-decode regression on the dominant library format).

### Severity Breakdown

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 5 | ENG-D1-1, ENG-D3-1, ENG-D3-3, ENG-D4-1, ENG-D4-2 |
| MEDIUM | 5 | ENG-D3-2, ENG-D4-3, ENG-D6-1, ENG-D7-1, ENG-D7-2 |
| LOW | 10 | ENG-D2-1, ENG-D2-2, ENG-D2-3, ENG-D2-4, ENG-D2/5-5, ENG-D5-1, ENG-D5-2, ENG-D6-2, ENG-D7-3, ENG-D7-4 |

**New vs. existing**: 13 NEW; ENG-D3-2 (Existing #3726) and ENG-D3-3 (Existing #3735) are re-assessed UPWARD in severity vs. their filed LOW; ENG-D2/5-5 is Existing #3878 (label-only, confirmed non-audible).

---

## HIGH Findings

### ENG-D1-1: Mono input file crashes SimpleMastering `master_file`
- **Severity**: HIGH
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/mastering_chunk_loop.py:60-98,212-221`
- **Status**: NEW
- **Description**: The offline mastering loop opens its output `SoundFile` with `out_channels = min(channels, 2)`, which is **1** for a mono source. But every path inside the loop expands mono to stereo (`if chunk.ndim == 1: chunk = np.stack([chunk, chunk]).T`), processes it as `(2, samples)`, and writes back `write_region.T` of shape `(samples, 2)`. Writing a `(frames, 2)` array to a `channels=1` sink raises `ValueError: Invalid shape (…, 2) (Expected 1 channels, got 2)`. The `min` was meant to cap multichannel down to 2, not permit 1.
- **Evidence**:
  ```python
  out_channels = min(channels, 2)          # == 1 for a mono file
  if chunk.ndim == 1:
      chunk = np.stack([chunk, chunk]).T   # mono ALWAYS expanded to stereo
  write_region = write_region.T            # (samples, 2)
  output_file.write(write_region)          # sink has channels=1 -> ValueError
  ```
  Reproduced: writing a `(1000, 2)` float32 array to a `channels=1` PCM_24 SoundFile raises `ValueError`. No `master_file` test feeds a true mono file (all helpers default `channels=2`).
- **Impact**: Any mono WAV/FLAC (voice memos, mono field recordings, mono transfers of vintage records — exactly the QuietBranch's target material) crashes mastering at the first write. No output produced (data loss for that job). FFmpeg-sourced mono files remain mono after decode and crash too.
- **Siblings**: `HybridProcessor._process_impl` (`hybrid_processor.py:267-269`) makes the same mono→stereo assumption but returns to an in-memory caller, so it is correct-by-design there. The file-writer sink is the only broken path. Distinct from #3882/#3881 (backend `chunked_processor.py` mono handling).
- **Suggested Fix**: Set `out_channels = 2` unconditionally (processing always yields stereo, matching the existing comment), or downmix `write_region` to mono before writing when the source was mono. The former is simplest and consistent with the ">2ch downmixed to stereo" contract.

### ENG-D3-1: `record_track_completion()` fires app-level callbacks while `_audio_lock` is held — reopens the #3781 deadlock class
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:332-336`; `auralis/player/integration_manager.py:297-305,132-141`
- **Status**: NEW
- **Description**: #3781 fixed an AB-BA deadlock between `AudioFileManager._audio_lock` and `IntegrationManager._position_lock` by wrapping every `_audio_lock`-holding mutator in `PlaybackController.defer_notifications()`, so callbacks fire only after `_audio_lock` releases. That fix covers only notifications flowing through `PlaybackController._notify_callbacks`. `AudioPlayer.next_track()` also calls `self.integration.record_track_completion()` from **inside** the same `with self.playback.defer_notifications(), self.file_manager._audio_lock:` block. `record_track_completion()` calls `IntegrationManager._notify_callbacks()` directly — a separate notify path with no deferral — so every callback registered via `AudioPlayer.add_callback()` fires synchronously while `file_manager._audio_lock` is still held by the auto-advance thread.
- **Evidence**:
  ```python
  # enhanced_audio_player.py:332-336
  with self.playback.defer_notifications(), self.file_manager._audio_lock:
      if self.gapless.advance_with_prebuffer(was_playing):
          self.integration.record_track_completion()   # fires callbacks NOW, lock held
  # integration_manager.py:297-305
  def record_track_completion(self) -> None:
      ...
      self._notify_callbacks({'action': 'track_completed', ...})  # not deferred
  ```
  The established order is `_position_lock -> _audio_lock` (used by `get_playback_info()`/`_get_position_seconds()`). A callback that reads player state back (e.g. to build a broadcast payload) acquires `_position_lock` while holding `_audio_lock` — the reverse order; a second thread polling `get_playback_info()` completes the AB-BA cycle: hard deadlock. Existing regression tests don't register an `IntegrationManager` callback, so the gap is invisible to them.
- **Impact**: Latent today (no in-tree backend registers such a callback — it polls `PlayerStateManager` instead), but the callback surface is a supported/tested/documented contract. One future integration or plugin reading player state from a `track_completed` callback hangs the whole application.
- **Siblings**: All other `IntegrationManager._notify_callbacks` call sites (`load_file`, `load_reference`, `set_shuffle`, `set_repeat`, …) fire OUTSIDE any lock scope — `record_track_completion()` inside `next_track()` is the only offender.
- **Suggested Fix**: Move `self.integration.record_track_completion()` out of the `with` block (call it after the lock releases using a local `advanced` flag), matching how `load_file()` already defers its `integration._notify_callbacks` call.

### ENG-D3-3: Gapless fallback disk load runs inside `_audio_lock` — reintroduces the #3656 audible-dropout pattern
- **Severity**: HIGH (impact re-assessed; filed LOW as a perf note)
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:332` → `auralis/player/gapless_playback_engine.py:337-358`
- **Status**: Existing: #3735 (OPEN, LOW) — severity rationale corrected
- **Description**: #3656 explicitly fixed `add_to_queue()` because holding `_audio_lock` across blocking disk I/O stalls `get_audio_chunk()` for the load duration → audible dropout. The same pattern remains in `next_track()`'s gapless fallback: when the prebuffer isn't ready/matching, `advance_with_prebuffer()` calls `self.file_manager.load_file(file_path)` (a blocking disk read) while `_audio_lock` is held by the auto-advance thread (RLock re-entered by the same thread from `next_track()`'s `with ... _audio_lock:` block), blocking the real-time chunk supplier for the full I/O duration.
- **Evidence**: `enhanced_audio_player.py:317-332` docstring notes the wide lock was deliberate for the atomic *swap*, but does not address that the same scope also covers the fallback's blocking `load()` (`gapless_playback_engine.py:291`/`:341`).
- **Impact**: Whenever prebuffering hasn't completed (short tracks, slow disk, queue mutated after prebuffer started), auto-advance stalls the audio-chunk supplier for the full disk-I/O latency — turning the "<10ms gap" design into an audible dropout/freeze.
- **Siblings**: `add_to_queue()` (`enhanced_audio_player.py:412-441`) already avoids this (#3656) — its "short lock for check, unlocked load" is a directly reusable template.
- **Suggested Fix**: In `advance_with_prebuffer()`'s fallback branches, drop `_audio_lock`/`defer_notifications()` before `file_manager.load_file(file_path)` and re-acquire only for the atomic commit (queue advance + audio_data swap + rollback-on-mismatch).

### ENG-D4-1: Cancelling a processing job does not stop the in-flight FFmpeg subprocess
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/core/processing_engine.py:442,707-731`; `auralis/io/loaders/ffmpeg_loader.py:228-278`
- **Status**: NEW
- **Description**: `cancel_job()` calls `task.cancel()`, which injects `CancelledError` at the next await point. When the task is inside `await asyncio.to_thread(load_audio, ...)` for an FFmpeg-routed format, that await does not resolve until the worker thread's blocking `subprocess.run(ffmpeg_cmd, ..., timeout=300)` returns. `task.cancel()` cannot interrupt a synchronous `subprocess.run` in a `ThreadPoolExecutor` worker, and nothing sends the FFmpeg child a terminate/kill signal.
- **Evidence**:
  ```python
  # processing_engine.py:442
  audio, sample_rate = await asyncio.to_thread(load_audio, job.input_path)
  # ffmpeg_loader.py:228 — blocking, uninterruptible
  result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
  ```
  Job status flips to CANCELLED immediately, but the FFmpeg child and its worker thread keep running for up to 5 minutes.
- **Impact**: "Cancelled" is a lie for FFmpeg-routed inputs while a load is in flight — the backend keeps burning a CPU core and a thread-pool slot on cancelled work. Rapid cancel/retry can pile up multiple live FFmpeg processes, degrading throughput. (Desktop/localhost, single-user — impact is resource waste, not a security boundary.)
- **Siblings**: #3889 (OPEN, LOW) covers a lock race in `cancel_job` but not the subprocess lifecycle. Same class applies to the reference-audio load at `processing_engine.py:471-473`.
- **Suggested Fix**: Use `subprocess.Popen` in `load_with_ffmpeg` and thread a cooperative cancellation token from `cancel_job()` down to the loader (poll `Popen.wait(timeout=...)`), so the child is `.terminate()`/`.kill()`ed promptly on cancel.

### ENG-D4-2: Chunked-playback metadata lookup silently falls back to a full-file decode for every FFmpeg-routed track
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/core/chunked_processor.py:242-262`
- **Status**: NEW
- **Description**: `_load_metadata()` is documented as loading "metadata without loading full audio" but opens the file with `sf.SoundFile(self.filepath)` directly, with no extension routing. libsndfile cannot open the FFmpeg-only formats (`.mp3/.m4a/.aac/.ogg/.wma/.opus` — the reason `FFMPEG_FORMAT_NAMES` exists), so the open raises and the `except` falls back to `load_audio(self.filepath)` — a full decode (temp-WAV + full `sf.read`) merely to read duration/sample-rate/channels. `unified_loader.get_audio_info()`/`_get_info_with_ffprobe()` already provides the cheap ffprobe path that this method fails to use.
- **Evidence**:
  ```python
  def _load_metadata(self) -> None:
      try:
          with sf.SoundFile(self.filepath) as f: ...
      except Exception as e:
          logger.error(...)
          audio, sr = load_audio(self.filepath)   # full decode for metadata
  ```
- **Impact**: Every chunked-playback session for an MP3/M4A/AAC/OGG/WMA/OPUS track — the dominant library format — pays a full FFmpeg conversion + full float32 decode just to start streaming, instead of a millisecond ffprobe. Undermines the bounded-decode architecture and reintroduces OOM exposure for long-form content (multi-hour masters/podcasts hold a multi-GB buffer + temp WAV before the first chunk).
- **Siblings**: #3881 (OPEN, LOW) tracks a *different* bug in the same fallback branch (wrong `self.channels` for mono int16 WAV) — fix both, but the primary fix is to stop the fallback firing for FFmpeg formats.
- **Suggested Fix**: Route `_load_metadata()` by extension like `unified_loader.load_audio()`: `get_audio_info()` (ffprobe) for FFmpeg formats, `sf.SoundFile()` only for natively-decodable ones. Reserve `load_audio()` for genuine probe failures.

---

## MEDIUM Findings

### ENG-D3-2: `previous_track()` rollback baseline TOCTOU + `rollback_index()` has no bounds clamp
- **Severity**: MEDIUM (existing issue undersells blast radius)
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:373-410`; `auralis/player/components/queue_manager.py:170-181`
- **Status**: Existing: #3726 (OPEN, LOW) — impact re-assessed
- **Description**: `previous_track()` captures its rollback baseline via `snapshot_index()` in a *separate* lock acquisition from the `queue.previous_track()` decrement, leaving a TOCTOU gap. #3726's proposed `snapshot_index()` fixes the torn-read half but not the two-critical-section gap. Worse, `QueueManager.rollback_index()` does **no bounds check**: if the queue shrinks (concurrent `remove_track()`) between snapshot and rollback, `current_index` can be restored `>= len(tracks)` — genuinely out of bounds, not merely off-by-one as #3726 states.
- **Evidence**:
  ```python
  saved_index = self.queue.snapshot_index()   # separate critical section
  prev_track = self.queue.previous_track()     # separate locked decrement
  ...
  self.queue.rollback_index(saved_index)       # unclamped write
  # queue_manager.py:170-181
  def rollback_index(self, saved_index): 
      with self._lock: self.current_index = saved_index   # no bounds check
  ```
  Trace: 10 tracks, index 5; snapshot 5; concurrent removes shrink queue to 3 (index 2); load fails → `rollback_index(5)` sets index 5 in a 3-track queue.
- **Impact**: `get_current_track()` silently returns `None` until the next navigation resets the index; subsequent next/previous behave as at the boundary, potentially wrapping to 0 via repeat. Narrow but real queue-corruption path.
- **Siblings**: `set_queue()`/`load_playlist()` clamp under a single held lock (#4098); `previous_track()`'s rollback is the only unclamped write.
- **Suggested Fix**: Clamp in `rollback_index()` (`min(saved_index, len(tracks)-1)` / `-1` if empty). For the TOCTOU, fold snapshot + decrement into one critical section returning a rollback token.

### ENG-D4-3: Upload magic-byte allowlist doesn't cover AIFF/AU/WMA — legitimate uploads rejected
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/routers/files.py:34-50`
- **Status**: NEW
- **Description**: `SUPPORTED_FORMATS` advertises `.aiff/.aif` (`FORM…AIFF/AIFC`), `.au` (`.snd`), and `.wma` (ASF GUID) as decodable, and the upload endpoint's extension check accepts them. But `_has_valid_audio_magic()` only recognizes MP3/ID3, RIFF, `fLaC`, `OggS`, and MP4/`ftyp` — no AIFF/AU/WMA signatures. A well-formed AIFF/AU/WMA upload is rejected at the magic-byte check ("File content does not match any known audio format") even though `load_audio()` would decode it.
- **Evidence**: `_AUDIO_MAGIC` tuple contains no `FORM`/`AIFF`/`AIFC`, `.snd`, or ASF GUID entry, despite all three extensions being in `SUPPORTED_FORMATS`.
- **Impact**: Silent false-rejection of valid uploads for 3 of 11 supported formats. Functional/coverage bug, not a security control gap.
- **Siblings**: None in baseline.
- **Suggested Fix**: Add the three signatures (or check `FORM`+`AIFF/AIFC` at offset), or derive the magic-byte check from the same `SUPPORTED_FORMATS` source of truth so the two lists can't drift (spirit of #4109).

### ENG-D6-1: Pre-loaded-audio path in FingerprintService resamples the full buffer before applying the 90s cap
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:307-323`
- **Status**: NEW
- **Description**: `_compute_fingerprint()`'s no-preloaded-audio branch bounds duration up front via soundfile offset/duration reads. But the pre-loaded `audio`/`sr` branch resamples the *entire* array with `librosa.resample(...)` (per-channel for 2-D) and only *then* crops to 90s (`audio[..., :_max_samples]`). For a multi-hour pre-loaded buffer this is an O(duration) resample + transient full-duration float32 allocation before discarding all but the first 90s.
- **Evidence**:
  ```python
  else:
      if sr != _target_sr:
          audio = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=_target_sr)
      audio = audio[..., :_max_samples]   # crop AFTER the expensive resample
  ```
  Latent: every current `get_or_compute(path)` call site passes no `audio`/`sr`, so this branch is unreachable today.
- **Impact**: If a future caller wires up the pre-loaded-audio fast path (the parameter exists to skip a redundant file load), a multi-hour buffer causes a multi-minute resample + large transient allocation — defeating the shortcut and reintroducing the #4116 OOM/latency class.
- **Siblings**: None — every other entry point (`MasteringFingerprint.from_audio_file`, `AudioFingerprintAnalyzer.analyze`) crops/bounds before the expensive step.
- **Suggested Fix**: Slice to `int(sr * 90.0)` in the original sample rate *before* resampling, matching the crop-then-resample order used everywhere else.

### ENG-D7-1: Track list/by-id queries never eager-load `Track.genres`; genres silently empty
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository.py:217,236,256,273,345,471,503,536,574,639,659`
- **Status**: NEW
- **Description**: Every track read path except `get_by_genre` loads only `joinedload(Track.artists), joinedload(Track.album)` then `session.expunge(track)`. `Track.genres` is lazy; after expunge, `to_dict()` accesses `self.genres` → `DetachedInstanceError`, swallowed by the surrounding `try/except` (`models/core.py:117-120`), returning `genres: []`. Result: every track from list/single-fetch/search/favorites/recent/popular carries an empty `genres` list regardless of DB data.
- **Evidence**: Reproduced — a Track with a genre fetched via `joinedload(artists), joinedload(album)` then expunged yields `to_dict()['genres'] == []`. `get_by_genre` (`:437-439`) is the only path adding `selectinload(Track.genres)`.
- **Impact**: Silent data loss for genre on all common read paths (manifests as empty data, not a query storm — expunge blocks the lazy load, exception swallowed).
- **Siblings**: The expunge-then-access pattern is safe for artists/album (eager-loaded); only `genres` is omitted.
- **Suggested Fix**: Add `selectinload(Track.genres)` to the shared track-loading `.options(...)` (ideally centralize the option list), mirroring `get_by_genre`.

### ENG-D7-2: `FingerprintService` owns a private engine with no disposal path (connection-pool leak)
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:45-61,95-101`; callers `auralis/core/simple_mastering.py:83`, `auralis/player/enhanced_audio_player.py:111`
- **Status**: NEW
- **Description**: Constructed without a `session_factory` (both production call sites do this), `FingerprintService.__init__` builds its own `create_engine(...)` pool (`_make_engine`) and stores `self._engine`. The class exposes no `close()`/`dispose()`/`__del__`, and no owner disposes it. `HybridProcessor.close()` closes only `fingerprint_analyzer`'s executor, never the engine. Processors are LRU-evicted (`processor_factory.py:250-261`), so each evicted processor's `FingerprintService` engine leaks its pooled connections until GC finalizers run.
- **Evidence**: `grep 'def close\|dispose\|__del__' fingerprint_service.py` → none. Eviction calls `_evicted_proc.close()` but that doesn't cascade to the engine.
- **Impact**: Non-deterministic connection/engine leak in long-running sessions — same class as `8adb8d0a`/#2395/#3746, left unaddressed for this private engine. Bounded by GC (slow, not unbounded).
- **Siblings**: Mirrors the executor-leak #3746 fixed for `fingerprint_analyzer`; the engine half was missed.
- **Suggested Fix**: Add `FingerprintService.close()` disposing `self._engine` when self-created, called from `HybridProcessor.close()` / player teardown.

---

## LOW Findings

### ENG-D2-1: PyO3 multiband-EQ / chunk wrappers derive channel count from an unvalidated axis
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `vendor/auralis-dsp/src/py_bindings.rs:653-685,748-784`
- **Status**: NEW
- **Description**: `apply_multiband_eq_wrapper`/`process_chunks_wrapper` set `num_channels = audio_array.shape()[0]` with no check for (channels, samples) orientation and `channels ∈ {1,2}`. A (samples, channels) array — the orientation soundfile/most of the pipeline use — makes `num_channels` the sample count, allocating one filter bank/channel buffer per sample. The fingerprint wrapper (`:571`) DOES validate this, so the omission is inconsistent.
- **Evidence**: `let num_channels = audio_array.shape()[0];` unbounded, vs. fingerprint's `channels == 0 || channels > 2` guard.
- **Impact**: Pathological allocation / near-certain panic on transposed input. Contained (`py.allow_threads(catch_unwind(...))` → `PyRuntimeError`), and no live Python callers exist. Latent robustness gap.
- **Siblings**: `compute_fingerprint_wrapper` has the guard to mirror.
- **Suggested Fix**: Reject `shape[0] > 2` with a `PyValueError` naming the expected (channels, samples) layout.

### ENG-D2-2: Continuous-mode stereo width conflates correlation-scale and side-gain-scale widths
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:617-669`; `auralis/dsp/utils/stereo.py:17-83`
- **Status**: NEW
- **Description**: `stereo_width_analysis(audio)` returns a correlation-derived metric (0=mono, 0.5≈normal, 1=decorrelated), but `adjust_stereo_width(audio, target_width)` treats its arg as a side-gain factor (0.5=unchanged). The code compares the two on the same axis (`abs(target_width - current_width) > 0.05`) and derives `target_width` from `current_width`, mixing scales — a `target_width` numerically above `current_width` can still map to narrowing.
- **Evidence**: `target_width = current_width * (1 - conf*(1 - stereo_width_target))` feeds `adjust_stereo_width(audio, target_width)`.
- **Impact**: Applied width change doesn't precisely track intended direction/magnitude; tuning-quality only, no invariant break (post-stage phase-correlation guard catches gross decorrelation).
- **Siblings**: The SimpleMastering `stereo_expansion.py` path avoids this via explicit `width_factor = 0.5 + expansion_amount`.
- **Suggested Fix**: Convert `stereo_width_analysis` output to the side-gain scale (or vice-versa) before comparing/deriving.

### ENG-D2-3: Continuous-mode uses full-band stereo widening (bass not protected)
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:665`; `auralis/dsp/utils/stereo.py:55-83`
- **Status**: NEW
- **Description**: The offline continuous path widens with full-band `adjust_stereo_width` (single mid/side gain across the whole spectrum), whereas SimpleMastering uses `adjust_stereo_width_multiband`, which keeps <300 Hz mono to protect kick/bass and mono-compatibility.
- **Evidence**: `audio = adjust_stereo_width(audio, target_width)` (full-band) vs. `stereo_expansion.apply` → `adjust_stereo_width_multiband(...)`.
- **Impact**: Possible mono-compatibility / bass-punch loss on the continuous path; bounded (widening skipped when peak > -2 dBFS; downstream phase-correlation guard blends toward mid on collapse).
- **Siblings**: ENG-D2-2 (same function); `adjust_stereo_width_multiband` is the low-freq-safe replacement.
- **Suggested Fix**: Route the continuous path through `adjust_stereo_width_multiband`.

### ENG-D2-4: Multiband stereo-widen bands overlap at the 2 kHz crossover
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/utils/stereo.py:128-170`
- **Status**: NEW
- **Description**: Low-mid band 300–2000 Hz and high-mid band 2000–8000 Hz share the 2000 Hz edge; each is an order-2 Butterworth bandpass with wide skirts, so energy near 2 kHz appears in BOTH extracted bands and the additive widening delta is applied ~twice there, producing a width bump at the crossover.
- **Evidence**: `freq_lowmid_hi = 2000/nyq` and `freq_highmid_lo = 2000/nyq`; both `diff_lowmid` and `diff_highmid` summed onto the dry signal.
- **Impact**: Mild spectral-width coloration near 2 kHz. Parallel-additive on zero-phase bands → no phase cancellation; only the width curve is slightly overweighted at the seam. Quality-only.
- **Siblings**: N/A.
- **Suggested Fix**: Use complementary crossover edges or subtract the overlap so each frequency is widened once.

### ENG-D2/5-5: Chunk-reassembly crossfade labelled "equal-power" but is equal-gain (sin²/cos²)
- **Severity**: LOW
- **Dimension**: DSP Pipeline / Parallel Processing (found by both Dim 2 and Dim 5 at the same location — merged)
- **Location**: `auralis/core/mastering_chunk_loop.py:49-51,179-187`
- **Status**: Existing: #3878
- **Description**: The docstring/comments call the blend "equal-power (cosine curves maintain loudness)", but the ramps are `fade_in = sin(t)²`, `fade_out = cos(t)²`, which sum to 1 in amplitude — an equal-**gain** crossfade, not equal-power (equal-power uses sqrt/`sin`/`cos` so squared gains sum to 1). For THIS join both chunks processed the SAME overlap region (correlated content), so equal-gain is in fact the *correct* choice — a sqrt-Hann pair would produce a ~+3 dB bump. The defect is the misleading label only.
- **Evidence**: `fade_in = np.sin(t) ** 2` / `fade_out = np.cos(t) ** 2` at `:185-186`.
- **Impact**: None on audio (math is correct for correlated overlap); naming only. Do NOT "fix" by switching to sqrt curves — that would regress level at the joins.
- **Siblings**: #3878 (`apply_crossfade` docstring/impl naming, same class).
- **Suggested Fix**: Correct the comment to "equal-gain (correlated-overlap preserving)"; close under #3878.

### ENG-D5-1: ParallelBandProcessor failed-band fallbacks filter the shared (uncopied) buffer
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py:291-294,311-314`
- **Status**: NEW (sibling/regression-class of #4229)
- **Description**: Per-band fallbacks are precomputed as `band_filters[i](audio) * gain` over the same shared `audio` with no `.copy()`. The sibling `_process_band_groups` fallback (`:395-402`) was fixed under #4229 to use `band_filters[band_idx](audio.copy())` precisely to avoid an in-place band filter corrupting `audio` for remaining iterations. The flat band path never got this fix.
- **Evidence**: `band_filters[i](audio) * (10 ** (band_gains[i]/20))` (no copy) vs. fixed group path `band_filters[band_idx](audio.copy())`.
- **Impact**: In-place-mutating filter + failed band → cross-contaminated fallback spectrum. Latent only (no production callers; in-repo band_filters are pure).
- **Siblings**: #4229, #3355, #3430/#3675.
- **Suggested Fix**: Copy the input in the flat fallback comprehensions to match the #4229 invariant.

### ENG-D5-2: ParallelEQProcessor silently drops samples when a chunk is longer than fft_size
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/dsp/eq/parallel_eq_processor/parallel_processor.py:53-88,126,144-148,170,193-198`
- **Status**: NEW
- **Description**: `apply_eq_gains_parallel` handles only `len < fft_size` (zero-pad). For `len > fft_size`, both parallel and sequential mono paths do `fft(audio_mono[:fft_size])`, so the inverse yields only `fft_size` samples; `processed_audio[:len(audio_mono)]` returns `min(fft_size, len)` and the caller's `result[:original_length]` cannot restore the dropped tail — output length becomes `fft_size` (a sample-count violation).
- **Evidence**: No `len > fft_size` branch; `fft(audio_mono[:fft_size])` with `return processed_audio[:len(audio_mono)]` where `processed_audio` has only `fft_size` samples.
- **Impact**: Truncated audio for oversized chunks (would be CRITICAL if reachable). Currently LOW: `ParallelEQProcessor` has no production callers; `psychoacoustic_eq.py` imports only `VectorizedEQProcessor`; only test exercises it at exactly `fft_size`.
- **Siblings**: #2448, #3659/#3685.
- **Suggested Fix**: Assert `len == fft_size` at entry (explicit contract), or block-process in `fft_size` frames with overlap-add.

### ENG-D6-2: `FingerprintStorage.save()` writes the `.25d` cache file non-atomically
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:121-125`
- **Status**: NEW
- **Description**: `save()` opens the destination directly in `'w'` mode and streams `json.dump()` — not atomic. `open('w')` truncates immediately, so a concurrent reader (scheduler worker vs. interactive playback fingerprint request on the same track, or two processes sharing `~/.auralis/fingerprints/`) can observe a truncated file mid-write.
- **Evidence**: `with open(cache_path, 'w', encoding='utf-8') as f: json.dump(content, f, ...)`.
- **Impact**: Low — `load()` catches `JSONDecodeError` as a cache miss, so worst case is a wasted recomputation on the losing side of a race; no corruption, no wrong fingerprint served.
- **Siblings**: None (only writer of `.25d`).
- **Suggested Fix**: Write to a `NamedTemporaryFile` in `cache_dir` and `os.replace()` onto `cache_path` after a successful dump (the established atomic-write idiom).

### ENG-D7-3: Per-directory scan dedup guard is per-instance and effectively bypassed
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/scanner.py:66-67,137-148`; `auralis-web/backend/services/library_auto_scanner.py:202`; `auralis/library/manager.py:489,495`
- **Status**: NEW
- **Description**: The `_active_paths`/`_active_paths_lock` guard (#3455) that rejects a scan of an already-scanning directory is an *instance* attribute. Both `LibraryAutoScanner._do_scan` and `LibraryManager.scan_directories` construct a *new* `LibraryScanner` per invocation, so two overlapping scans never share `_active_paths` — the guard only sees its own empty set. Cross-scan serialization relies solely on the scan-slot (`try_acquire_scan_slot`, default `max_concurrent_scans=1`).
- **Evidence**: `library_auto_scanner.py:202` and `manager.py:489/495` build fresh `LibraryScanner` per call; no shared instance.
- **Impact**: If `max_concurrent_scans` is raised above 1, two scans of the same folder run concurrently with the per-directory guard doing nothing. No DB corruption (UNIQUE(filepath) + skip_existing + IntegrityError rollback); wasted work/confusing logs. Fully masked at default max=1.
- **Siblings**: #2438 (scan-slot concurrency).
- **Suggested Fix**: Hoist `_active_paths` + lock to a process-shared location (e.g. `LibraryManager`, already shared for the scan slot).

### ENG-D7-4: Fingerprint service engine omits `PRAGMA foreign_keys=ON`
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:54-59`
- **Status**: NEW
- **Description**: `_make_engine` sets `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=60000` but not `foreign_keys=ON`, while `LibraryManager` (`manager.py:158`) and `MigrationManager` (`migration_manager.py:147`) both enable FK enforcement on the same `library.db`. Fingerprint writes (keyed by `track_id`) run without FK enforcement.
- **Evidence**: `grep 'foreign_keys' fingerprint_service.py` → none; present in the other two engine setups.
- **Impact**: Low — fingerprint writes go through repositories against existing tracks, so orphan rows are unlikely, but a stale `track_id` write wouldn't be rejected the way the main engine would.
- **Siblings**: Same engine as ENG-D7-2.
- **Suggested Fix**: Add `PRAGMA foreign_keys=ON` to `_make_engine`'s connect listener.

---

## Relationships & Shared Root Causes

- **Lock-scope regression family (ENG-D3-1, ENG-D3-3).** Both are the *same underlying mistake* — doing work (callback dispatch / blocking disk I/O) inside the `_audio_lock` scope of `next_track()` — that the codebase has already fixed elsewhere (#3781 for callbacks, #3656 for blocking loads). The player module is heavily hardened, but the auto-advance path has two residual leaks of these exact classes. Fixing both means auditing `next_track()`'s `with ... _audio_lock:` block for anything that isn't a strictly-atomic in-memory swap.

- **FingerprintService lifecycle family (ENG-D7-2, ENG-D7-4, and adjacent to ENG-D6-1/ENG-D6-2).** `FingerprintService` and the fingerprint cache layer accumulate several independent gaps: a self-created engine with no disposal (ENG-D7-2), missing FK PRAGMA on that engine (ENG-D7-4), an unbounded resample in the pre-loaded path (ENG-D6-1), and non-atomic cache writes (ENG-D6-2). A focused pass over `fingerprint_service.py` + `fingerprint_storage.py` closes four findings at once.

- **"Cheap metadata" vs. "full decode" (ENG-D4-1, ENG-D4-2).** Both stem from the FFmpeg loader using a blocking, all-or-nothing `subprocess.run` full-decode where a cooperative/ffprobe-scoped path exists. ENG-D4-2 fires the full decode unnecessarily; ENG-D4-1 makes that full decode uncancellable. `unified_loader` already has the right primitive (`get_audio_info`/ffprobe) — routing both call sites through it addresses the shared root cause.

- **Mislabel confirmed benign, twice (ENG-D2/5-5).** Two independent dimensions flagged the crossfade label and *both* concluded the math is correct for the correlated overlap — a good cross-check that the "fix" is docs-only. Merged to prevent a duplicate issue.

- **Latent-until-wired cluster (ENG-D2-1, ENG-D5-1, ENG-D5-2, ENG-D6-1).** Four findings are in code with no current production callers (generic parallel machinery, PyO3 multiband wrappers, the pre-loaded-audio fingerprint branch). They are correctly LOW/MEDIUM today, but each would jump in severity the moment a caller is wired up — worth fixing before that happens rather than after.

---

## Prioritized Fix Order

1. **ENG-D1-1 (HIGH, mono crash)** — Real data loss on a whole class of real files, one-line fix (`out_channels = 2`). Highest value-to-effort. Add a mono `master_file` regression test.
2. **ENG-D4-2 (HIGH, full decode for FFmpeg metadata)** — Actively degrades every MP3/M4A/etc. chunked session today and reintroduces OOM exposure on long-form content. Route `_load_metadata()` through ffprobe.
3. **ENG-D4-1 (HIGH, uncancellable FFmpeg)** — Resource waste on every cancel of an FFmpeg-routed job. Convert `load_with_ffmpeg` to `Popen` + cooperative cancel. Pairs naturally with #2.
4. **ENG-D3-1 (HIGH, latent deadlock)** — 3-line fix (move `record_track_completion()` out of the lock). Latent but catastrophic (full hang); cheap insurance. Extend the lock-ordering regression suite to register an `IntegrationManager` callback.
5. **ENG-D3-3 (HIGH, gapless dropout)** — Reuse the #3656 `add_to_queue()` template to unlock the fallback load. Improves real playback quality under slow-disk/short-track conditions.
6. **MEDIUM batch** — ENG-D7-1 (genre data loss on all list paths — add `selectinload(Track.genres)`), ENG-D3-2 (clamp `rollback_index()` + fold snapshot into one lock), ENG-D7-2 (add `FingerprintService.close()`), ENG-D4-3 (add AIFF/AU/WMA magic bytes), ENG-D6-1 (crop-before-resample). ENG-D7-1 and ENG-D7-2 are quick and self-contained.
7. **LOW batch** — Fold ENG-D7-4/ENG-D6-2 into the FingerprintService pass; ENG-D2-1/ENG-D5-1/ENG-D5-2 harden the latent parallel/PyO3 paths before they get callers; ENG-D2-2/2-3/2-4 are stereo-width tuning polish; ENG-D2/5-5 is a docs-only fix under #3878.

---

## Deduplication Notes

- Baseline: 142 open issues (`gh issue list --limit 200`), plus `docs/audits/` (no prior engine report present) and `.claude/issues/`.
- **Re-assessed existing** (reported here with corrected severity, not re-filed as new): ENG-D3-2 (#3726, LOW→MEDIUM), ENG-D3-3 (#3735, LOW→HIGH), ENG-D2/5-5 (#3878, confirmed label-only LOW).
- **Related-but-distinct existing issues** noted inline: #3889 (cancel_job lock race, distinct from ENG-D4-1's subprocess lifecycle), #3881 (mono int16 channel calc, distinct from ENG-D4-2's full-decode path), #4229/#3355 (parallel copy fixes — ENG-D5-1 is the un-fixed sibling), #3882/#3881 (backend mono handling, distinct from ENG-D1-1).
- Confirmed-clean areas (not findings, documented in dimension notes): sample-count preservation at every stage, copy-before-modify across all DSP stages, dtype propagation, NaN/Inf containment, pre-PCM clipping, double-windowing (cca59d9c not regressed), sub-bass parallel path (8bc5b217 not regressed), Rust GIL release + typed dtype boundary, fingerprint determinism (#3741), ML classifier singleton (`@lru_cache`), resource caps (#4116/#3454/#3705), KeyboardInterrupt propagation (53cef6b4), migration file-lock + backup, engine disposal (8adb8d0a), cleanup_missing_files pagination (bd94fd59), scanner symlink/permission/Unicode robustness, repository-pattern compliance, concurrent-scan UNIQUE-constraint safety.

---

*Report generated by the audit-engine orchestrator (7 dimension agents). Suggested next step: `/audit-publish docs/audits/AUDIT_ENGINE_2026-07-12.md`.*
