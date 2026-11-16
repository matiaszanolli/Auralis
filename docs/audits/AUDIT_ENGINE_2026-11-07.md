# Audio Engine Audit — 2026-11-07

**Scope**: Auralis core audio engine. The seven `/audit-engine` dimensions were Sample Integrity, DSP Pipeline, Player State, Audio I/O, Chunked Mastering, Analysis, and Library & Database.
**Depth**: deep. **Limit**: none. **HEAD**: `d7d29213f`.
**Method**: each dimension ran as a fresh sub-audit of the current source. Findings were checked with probes on synthetic and real audio. Every probe used a scratch `HOME` and scratch temp DBs, so the real library was never touched and no repo file changed. Each finding was deduplicated against the full issue dump (`gh issue list --state all`, 6044 issues, highest #6292, verified complete). Prior reports in `docs/audits/` were used only for that dedup check.
**Environment note**: the `auralis_dsp` wheel was present in the repo venv this time, so the fingerprint path was exercised for real (the 2026-10-22 audit had to stub it).
**Status of the findings**: they come from the dimension sub-audits and were not individually re-probed by the orchestrator. The one HIGH (E4-01) was spot-checked against the code: `can_seek_natively` does only test whether libsndfile opens the file. `/audit-publish` re-validates each finding before an issue is filed.

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 6 |
| LOW | 31 |
| **Total** | **38** |

By dimension (after the two cross-dimension merges below): Sample Integrity 2 · DSP Pipeline 7 · Player State 7 · Audio I/O 6 · Chunked Mastering 2 (carries the merged E2-08) · Analysis 9 (carries the merged E7-05) · Library & Database 5. Raw count was 40; E2-08 folded into E5-01 and E7-05 into E6-04.

The shipped path held every hard invariant under probing: sample count, dtype, finiteness, input immutability and the limiter ceiling survived about 600 fuzz combinations on the live `ContinuousMode` path, and a production-geometry seam simulation on real recordings showed a seam gain mismatch of at most 0.005 dB. Whole-versus-chunked offline renders agree to 4.6e-5. No CRITICAL finding survived, and no closed issue regressed in the audio path. The one regression (E7-04) is in the fingerprint queue claim. Most of the remaining debt falls into four themes:

1. **The enhanced stream reads some files differently from every other path (the one HIGH).** E4-01: `can_seek_natively()` asks only "does libsndfile open this file?". For `.mp3/.ogg/.opus` it says yes, so those files skip the FFmpeg conversion that `stream_normal`, `load_audio` and the scanner all use. A valid MP3 with no Xing header (older VBR encoders, cut or `cat`-joined files) is then sized wrongly: a 40 s file produced one chunk with 0.0 s of audio and another with 4.7 of 10 s, while the UI showed the full duration. None of the 400 MP3s on this machine is affected, so it is rare here and real in the wild. E4-02 (truncated AIFF/AU loading as short clips) and E4-03 (downmix level differs by path) are the same kind of inconsistency between decode routes.
2. **Fixes that closed an issue but covered only part of the class.** E1-01 (#6118 guard catches only 1-2 row arrays), E3-04 (#5729 fixed the auto-master and safety ceilings but not the level matcher's), E3-06 (#6130 covered inf but not NaN), E4-04 (#5733 anchors only names matching an incomplete protocol regex), E2-04 (#5704 made the makeup gain continuous but not the peak target beside it), E6-02 (#5711 fixed the 25D windows but not `MasteringFingerprint`), E6-05 (#6141), and E7-04, a formal regression of #6080 whose commit says "part". Each is cheap to fix because the pattern and the pinning test already exist.
3. **Library metadata hygiene.** E7-01: retagging a file leaves empty albums, artists and genres behind, because `prune_orphans` runs only on delete. E7-02: albums are keyed on the first track artist and the extracted `albumartist` tag is dropped, so compilations split (5 albums from 2 real ones in the probe). E7-03: a tag removed from a file is never cleared in the DB. E7-06: upgraded databases lack the unique `filepath_key` index that fresh installs have.
4. **Fingerprint measurements that depend on the tail frame, the timezone or the container.** E6-01: a partial trailing 1 s frame is weighted like a full one in three variation dimensions, so one extra sample moved `dynamic_range_variation` from 0.154 to 0.279 on a real master (tracks under 90 s). E6-04: `.25d` sidecar validity depends on the machine's timezone. E6-09: FFmpeg-only containers never get a sidecar.

Player findings (E3-*) and the realtime DSP findings (E1-02, E2-02, E2-03) are **latent**: `AudioPlayer.get_audio_chunk()` still has no production caller and the backend builds the player with `enable_auto_mastering=False`. Severities are capped accordingly. Offline-CLI findings (E2-01, E2-05, E2-06, E5-*) are rated at offline-tool weight, per #4873.

## Findings

### CRITICAL (0)

_None._

### HIGH (1)

### E4-01: Enhanced stream decodes MP3/OGG/OPUS with libsndfile, which truncates valid VBR-without-Xing and concatenated MP3s into silent holes
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/core/seekable_source.py:66-78` (`can_seek_natively`), `:289-292` (`SeekableSource.resolve`); `auralis-web/backend/core/chunk_metadata.py:93-94`; reader `auralis-web/backend/core/chunk_file_loading.py:119-129`
- **Status**: NEW (related closed work: #4737/#5402 built the "convert only if libsndfile cannot open it" rule; #6134 moved the *scanner* to ffprobe but not the streaming reader)
- **Description**: `FFMPEG_FORMATS` declares `.mp3/.ogg/.opus` as FFmpeg-decoded, and `load_audio()`, `get_audio_info()`, the scanner (#6134) and `stream_normal` (which converts every `FFMPEG_FORMATS` entry; its comment says so deliberately) all follow that. The enhanced/chunked path does not. `can_seek_natively()` only asks "does `sf.SoundFile(path)` open?". With soundfile 0.14.0's bundled libsndfile 1.2.2 that is True for MP3, Ogg Vorbis and Ogg Opus, so those files are never converted and every chunk is read with `sf.SoundFile.seek/read` (libsndfile + mpg123). For an MP3 with no Xing/VBRI/LAME header (VBR from older encoders, cut or joined files) libsndfile sizes the file from the first frame's bitrate and from the first header's stream size. `sf.info().frames`, `sf.read()` and `seek()` then stop at that wrong length, while FFmpeg decodes the whole file. The reader raises no error: a short `read()` is returned, `load_chunk_from_file` accepts it, and the chunk pipeline pads with silence ("Chunk N was X samples short, padded with silence"). Past the bad length, `seek()` raises `psf_fseek() failed`, which falls into the per-chunk full-FFmpeg-decode fallback (works, but a full decode per chunk).
- **Evidence** (all reproduced; `ChunkedAudioProcessor(..., preset=None)` serves the original audio, so the holes are in the source read, not the DSP):

  | File (all valid; `ffmpeg-decode` = what `load_audio` returns) | ffprobe duration (metadata) | `sf.info`/`sf.read` | ffmpeg-decode |
  |---|---|---|---|
  | 40 s real music, `-q:a 4 -write_xing 0` (`music_vbr_noxing.mp3`) | 43.30 s | 24.72 s | 40.03 s |
  | 20 s, `-q:a 6 -write_xing 0` (`vbr6_noxing.mp3`) | 18.90 s | 4.72 s | 20.04 s |
  | `cat t.mp3 t.mp3` (`joined.mp3`) | 24.10 s | 12.00 s | 24.06 s |

  Streaming result for `music_vbr_noxing.mp3` (4 chunks): chunk 0 15.0 s of which 14.99 s audible; chunk 1 10.0 s with 4.72 s audible; **chunk 2 10.0 s with 0.0 s audible**; chunk 3 8.3 s with 5.03 s audible. The same file through `load_audio` is 40.03 s intact. For `joined.mp3`: chunk 0 has 7.0 s audible, chunk 1 is entirely silent (0.0 s) for a 24 s file. Log lines seen: `Chunk 1 was 253440 samples short, padded with silence`, `Soundfile loading failed, using fallback: Internal psf_fseek() failed.`, `Warning: Xing stream size off by more than 1%`. With the Xing header present (`music_vbr_xing.mp3`) and for CBR-without-Xing the routes agree (40.0 s / 40.03 s), and on a LAME-tagged file libsndfile and FFmpeg decode are sample-identical (max diff 4e-7, lag 0, seek diff 0.0), so this is a header-pathology bug and not a general MP3 problem. None of the 400 MP3s under `/home/matias` and `/mnt/data` has the mismatch, so it is rare in this library but real in the wild (joined files, header-less VBR, mid-corrupt files: `midcorrupt.mp3` makes libsndfile raise `Unspecified internal error` where FFmpeg decodes it).
- **Impact**: For such files the enhanced stream plays seconds of audio followed by silence, or silent holes of a whole 10 s chunk, while the UI shows the full ffprobe duration. The normal-mode stream of the same file is correct (it converts), so the two modes disagree about what the file contains. Nothing is logged above WARNING and no error reaches the client. A mid-corrupt MP3 turns into one full FFmpeg decode per chunk.
- **Suggested Fix**: Make the native/convert decision from the extension (`ext in SOUNDFILE_FORMATS`), not from "libsndfile happens to open it", in `can_seek_natively` / `SeekableSource.resolve` / `load_audio_metadata`, so `.mp3/.ogg/.opus` take the same decode-once temp-WAV route as `.m4a` and as `stream_normal`. Add a regression test using a `-write_xing 0` VBR MP3 and a `cat`-joined MP3. Sibling readers that open FFmpeg-format files with `sf.SoundFile` and would also see the wrong length: `auralis-web/backend/core/fingerprint_loading.py:37` (`probe_file_properties`) and `auralis/library/repositories/track_repository_lifecycle.py:~174` (`sf.info` first).

### MEDIUM (6)

### E2-01: Normalized-frequency floor `max(0.01, f/nyq)` mis-places the 60/120/150/200 Hz corners at 44.1 kHz (and the 300 Hz widening edge at >= 88.2 kHz) — the #4211/#4218 floor fix was never applied to its siblings
- **Severity**: MEDIUM (offline CLI path, precedent #4218 rated MEDIUM; the shipped-path sibling `adjust_stereo_width_multiband` is LOW and only bites at >= 88.2 kHz)
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/dsp/parallel_eq.py:117,186,250-257`; `auralis/dsp/utils/stereo.py:178-182` (the exciter's `max(0.01, ...)` at `core/stages/harmonic_exciter.py:68-69` and `core/dsp/harmonic_exciter.py:117-130` is a sibling in form only: its corners are >= 1 kHz, so it never clamps at supported rates)
- **Status**: NEW (the `.claude/issues/4211/INVESTIGATION.md` "out of scope, flagging for a separate finding" note was never filed; #4211/#4218 only lowered the 0.005 floor in `transient_shaper.py` and `sub_bass_control.py`'s HP)
- **Description**: `ParallelEQUtilities.apply_low_shelf_boost/apply_high_shelf_boost/apply_bandpass_boost` clamp the normalized corner with `min(0.99, max(0.01, freq_hz / nyquist))`. `0.01 * nyquist` is 220.5 Hz at 44.1 kHz (480 Hz at 96 kHz, 960 Hz at 192 kHz), so any configured corner below that is silently moved up to it. The offline pipeline's configured corners are `SUB_BASS_CUTOFF_HZ = 60`, `BASS_SHELF_HZ = 120`, `VOCAL_MASK_CUT_LOW_HZ = 150` (bandpass low edge) and `MID_BODY_LOW_HZ = 200` — all below 220 Hz. This is exactly the failure mode #4211/#4218 fixed for the transient shaper and the sub-bass HP (`1e-4` floor, "butter(order<=2) is stable down to ~1e-4"), which stayed behind in the sibling helpers. The corner is also sample-rate dependent (the same config gives a different EQ at 44.1 vs 96 kHz), which no config value can express.
  The shipped-path sibling is `adjust_stereo_width_multiband` (`ContinuousMode._apply_stereo_width`): its "lows (<300 Hz) stay mono" edge is `max(0.01, 300/nyq)`; this only clamps when `nyq > 30 kHz`, i.e. 88.2/96/192 kHz material, which the backend does process at the file's real rate (#5306).
- **Evidence**: probe an audit probe script (scratch, not retained) (2-s sines, measured steady-state gain) through the real `ParallelEQUtilities.apply_low_shelf_boost`:
  ```
  sr 44100   (config: sub-bass cut -6 dB @ 60 Hz ; bass shelf +6 dB @ 120 Hz)
     60 Hz  cut -5.95  shelf +5.98
    120 Hz  cut -5.33  shelf +5.64      <- a true 60 Hz corner gives about -0.25 dB here
    220 Hz  cut -2.51  shelf +3.52
    440 Hz  cut -0.26  shelf +0.50
  sr 96000
    220 Hz  cut -5.64  shelf +5.81
    440 Hz  cut -3.00  shelf +3.99
  ```
  Stereo (an audit probe script (scratch, not retained), pure-side sine, width factor 1.0, side gain achieved):
  ```
  sr 44100 : 300Hz 1.23x  400Hz 1.40x  600Hz 1.47x
  sr 96000 : 300Hz 1.03x  400Hz 1.12x  600Hz 1.40x
  sr 192000: 300Hz 1.00x  400Hz 1.00x  600Hz 1.01x  1000Hz 1.31x
  ```
- **Impact**: Offline CLI: the "sub-bass tighten (<60 Hz)" stage cuts the 100-250 Hz kick/bass body by up to 5 dB whenever it fires, and the always-on bass-balance shelf (`balance_db` +/- up to `MAX_BASS_BALANCE_DB`) acts as a 220 Hz shelf instead of a 120 Hz one — tonal balance of every master differs from what the fingerprint math (`BASS_TARGET_PCT` etc.) was calibrated for, and differs again by sample rate. Shipped path: at >= 88.2 kHz the multiband widening starts 1.6x-3.2x too high in frequency (conservative direction, no clipping risk).
- **Suggested Fix**: Use the same stability-only floor (`1e-4`, or clamp by `sosfreqz` stability) in `ParallelEQUtilities` and `adjust_stereo_width_multiband`, and add a corner-placement test (measured gain at fc/2 and 2*fc at 44.1/96 kHz) like the one #4211 should have had.

### E3-01: Gapless engine discards a valid prebuffer whenever the next track has a different sample rate
- **Severity**: MEDIUM (a gapless transition with a blocking decode is HIGH by the rubric; capped because `get_audio_chunk` is dormant in the shipped backend, where it only costs REST `next` latency)
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:148-159` (guard), `:219-222` (swap that makes the guard moot)
- **Status**: NEW (#2408 was only "no test for gapless prebuffer with different sample rates" and is closed; nothing covers this behaviour)
- **Description**: `advance_with_prebuffer()` throws the ready prebuffer away when `sample_rate != file_manager.sample_rate`, "to avoid pitch/speed error", and falls back to a blocking decode. The guard predates the no-resampling design (#5729). `AudioFileManager.sample_rate` follows the loaded file, and the swap always installs `file_manager.sample_rate = sample_rate`. The prebuffered path and the fallback path therefore install exactly the same state, and the only difference is a full decode on the transition. Any library with mixed 44.1/48/96 kHz material (for example consecutive albums) loses gapless at every rate change.
- **Evidence**: Audit probe script (scratch, not retained) (decode stubbed to a 0.3 s sleep, prebuffer pre-filled):
  - Different rate (44.1k to 48k): `advanced True seconds 0.3 decodes ['.../b48.wav'] sr now 48000`, with the log line `Sample rate mismatch: prebuffered=48000Hz, current=44100Hz - falling back to normal load to avoid pitch/speed error`.
  - Same rate: `advanced True seconds 0.0 decodes []`.
  - Code: `if current_sr is not None and sample_rate != current_sr: ... self.invalidate_prebuffer(); prebuffer_matches = False`, then `self.file_manager.sample_rate = sample_rate` at `:221`.
- **Impact**: For an audio-callback consumer, every transition across a rate boundary has a decode-length gap (tens of ms to seconds for long hi-res files) instead of a sample-exact swap. REST `next` blocks for the decode even though the prebuffer was ready. The prebuffer's decode work and memory are wasted.
- **Suggested Fix**: Drop the rate-equality guard. The swap already installs the new rate and `get_audio_chunk()` passes `file_manager.sample_rate` per chunk, so the realtime chain reconfigures (#5729). If a fixed-rate output is ever required, resample the prebuffer instead of discarding it.

### E6-01: Partial trailing 1 s frame is weighted like a full frame in the three variation dimensions
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/variation_analysis.rs:26-42` (`frame_analysis` uses `signal.chunks(frame_size)`), consumers `:83-107` (`compute_dynamic_range_variation`), `:112-130` (`compute_loudness_variation`), `:139-158` (`compute_peak_consistency`)
- **Status**: NEW (distinct root cause from open #6113, which is about digital-silence frames; a silence gate would not fix this)
- **Description**: The per-second frames are made with `chunks(frame_size)`, so the final, shorter-than-1-s remainder is analysed as a full frame. A 1-sample tail has RMS = |x|, crest = 0 dB, LUFS = that sample's level and peak = |x|. It is then one of ~N frames in the std-dev / CV. The 90 s body window is an exact multiple of 22050 samples (`audio[..., :int(22050*90)]`), so only tracks shorter than 90 s (and some opus decodes) are affected. For those, the window is the whole decode, whose length is arbitrary mod 22050 (`librosa.load` of a 48 kHz file returns `...001` samples).
- **Evidence**: `_load_windows` lengths: `t_48000.wav` (40 s, 48 kHz) -> 882001 samples (tail 1); `long.opus` -> tail 21907. Synthetic steady music (60 s, cut at 45 s + tail): tail 0 / 1 / 50 / 441 / 2205 samples -> `loudness_variation_std` 0.009 / 0.44 / 0.83 / 0.57 / 0.26; the 48 kHz-resampled file reads `loudness_variation_std` 16.56 vs 0.0043 for the 44.1 kHz copy of the same audio. Real mastered track (`output_fixed.wav`, 45 s excerpt at 22.05 kHz): `dynamic_range_variation` 0.154 (tail 0) -> 0.279 (tail 1) -> 0.233 (tail 10); `loudness_variation_std` 1.209 -> 1.550 (tail 100); `peak_consistency` 0.138 -> 0.187.
- **Impact**: For short tracks (interludes, intros, skits) the persisted `dynamic_range_variation`, `loudness_variation_std` and `peak_consistency` depend on the decoder's sample count rather than the audio (up to +80 % on a real master). `continuous_space._calculate_dynamic_range` takes 25 % of the dynamics coordinate from `log1p(loudness_variation_std)`, and the three dims are in the kNN distance. Likelihood is low (tail under ~0.1 s is roughly 10 % of short tracks), impact is a persisted wrong value.
- **Suggested Fix**: In `frame_analysis` drop (or merge into the previous frame) a trailing remainder shorter than, say, half a frame, as `mastering_prepare` already does for 400 ms loudness blocks; fold into the same `FINGERPRINT_ALGORITHM_VERSION` bump as #6112/#6113.

### E7-01: Retagging a file leaves empty albums, artists and genres behind (orphan sweep only runs on delete)
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_mutation.py:128-178` (`update_by_filepath`), `:180-220` (`update`), `auralis/library/repositories/orphan_pruning.py:51-84`, only caller `track_deletion.py:81`
- **Status**: NEW (sibling of closed #5596, which fixed only the delete path)
- **Description**: `prune_orphans()` is called solely from `delete_tracks_by_ids()`. The two update paths reassign `track.artists`, `track.genres` and `track.album` through `_update_artists` / `_update_genres` / `_assign_album` and commit, but never sweep the rows the track just left. The app's own metadata editor makes this the normal flow: `routers/metadata_tracks.py:195-206` documents artist/album/genre/albumartist edits as "intentionally file-only", so the DB learns the new album/artist only when the next scan hits `update_by_filepath`. Every such edit (and any retag in an external tagger) leaves the old album, artist and genre as zero-track rows. They stay listed, inflate `total_albums`/`total_artists`/`total_genres`, and only disappear when some unrelated track delete happens to run the global sweep.
- **Evidence**: Audit probe script (scratch, not retained) (scratch DB): add track (Old Artist / Old Album / Old Genre), `update_by_filepath` to New Artist / New Album / New Genre:
  ```
  albums 2 ['New Album', 'Old Album']
  artists ['New Artist', 'Old Artist']
  stats {'total_tracks': 1, 'total_albums': 2, 'total_artists': 2, 'total_genres': 2, ...}
  [('New Album', 1), ('Old Album', 0)]          # album list with track_count 0
  # after adding and deleting an unrelated track (runs prune_orphans):
  ['New Album']
  ```
- **Impact**: Library UI shows phantom empty albums/artists (and keeps their extracted artwork files on disk) and over-counts stats after any retag + rescan, until an unrelated delete. No data loss.
- **Suggested Fix**: Call `prune_orphans(session)` (it already commits/rolls back with the caller's transaction and queues artwork unlink for after-commit) inside `update_by_filepath` and `update` before `session.commit()` when artists, genres or album changed.

### E7-02: Album identity is the first track artist; the extracted `albumartist` tag is dropped, so compilations and "feat." albums split
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/metadata_extractor.py:63,208-253` (albumartist extracted, never mapped), `auralis/library/repositories/track_repository_lifecycle.py:125-142,198-203` (`_get_or_create_album(..., artists[0].id)`), `track_repository_mutation.py:99-113` (`_assign_album`, same `track.artists[0]`), unique index `uq_albums_title_artist` (migration v30)
- **Status**: NEW (closed #5457/#5595 introduced artist-keyed albums; none consider `albumartist`)
- **Description**: `TAG_MAPPINGS['albumartist']` is read into the metadata dict, but `audio_info_to_track_info()` never copies it into `track_info`. `add()` and both update paths then own the album by `artists[0]`, i.e. the first parsed name of the per-track artist tag (after `parse_featured_artists`). Since v30 the pair `(title, artist_id)` is the unique identity. Result: every compilation / soundtrack / split album where tracks carry different artists, and every album where one track lists a guest first ("B feat. A" vs "A"), is stored as several same-titled albums, each owning a subset of the tracks.
- **Evidence**: Audit probe script (scratch, not retained) (metadata dicts with `albumartist` set, run through `MetadataExtractor.audio_info_to_track_info` and `tracks.add`): tracks A/"Hits", B/"Hits", "C feat. A"/"Hits" (albumartist "Various Artists") and A, "A feat. B", B on "Solo Album" (albumartist "A") produce
  ```
  5 [('Hits', 'A'), ('Hits', 'B'), ('Hits', 'C'), ('Solo Album', 'A'), ('Solo Album', 'B')]
  ```
  `grep -rn albumartist auralis/library | grep -v metadata_editor` shows only the TAG_MAPPINGS line.
- **Impact**: Album grid shows duplicated same-titled albums and incomplete album pages for any compilation or multi-artist album; album artwork is extracted per fragment. The v30 uniqueness now makes the split permanent in the schema.
- **Suggested Fix**: Carry `albumartist` into `track_info` and key the album owner on it (fall back to `artists[0]` when absent) in `_get_or_create_album` callers (`add`, `_assign_album`); existing split albums need a one-off merge on next scan.

### E7-04: Fingerprint claim still reads a lost race (outdated queue) or a swallowed DB error as "queue empty"
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_scheduler_repository.py:230-262` (`claim_next_outdated_fingerprint`: `if rowcount != 1: return None`), `:150-210` and `:230` (`_guarded` turns any exception into `None`), consumers `auralis/services/fingerprint_queue.py:222-262` (`if not track: break`)
- **Status**: Regression of #6080 (incomplete fix: `46b152fad` is titled "(#6080, part)" and its message states "claim_next_outdated_fingerprint and a worker that hits one transient DB error are not changed"; #6080 is CLOSED and no open issue tracks the remainder)
- **Description**: The unfingerprinted queue now retries after an `IntegrityError` (up to 50 races). The outdated-fingerprint queue does not: all workers `find()` the same row from the shared cursor, only one `UPDATE ... SET fingerprint_version=0` gets `rowcount == 1`, and the losers return `None`, which `_worker_loop` Phase 2 reads as "no more outdated fingerprints" and leaves the phase for good. Separately, in both queues a transient failure (e.g. `database is locked` past the 60 s busy timeout during a heavy scan) is swallowed by `_guarded` and returned as `None`, ending that worker's phase while rows remain.
- **Evidence**: Audit probe script (scratch, not retained): three tracks with version-1 fingerprints (current version 11); a competing claim of the row returned by `find()` is simulated (monkeypatched `_find_after_cursor` sets that row to version 0 after find). `claim_next_outdated_fingerprint(11)` returns `None` although tracks 2 and 3 are still eligible; the next call returns a Track:
  ```
  claim -> None
  next claim -> <auralis.library.models.track.Track object ...>
  ```
- **Impact**: After a `FINGERPRINT_ALGORITHM_VERSION` bump the re-fingerprint pass loses most of its workers in the first round (pool collapses toward 1-3 effective workers) and `_on_worker_drained` counts them drained early, so reference-cloud refresh can run before re-extraction finishes; a transient error strands the worker until restart. No corruption.
- **Suggested Fix**: Apply the same bounded retry loop to `claim_next_outdated_fingerprint` (advance the cursor past the lost row and `find()` again), and make the claim methods distinguish "empty" from "error" (let the exception reach the worker's existing `except ... sleep(0.1)` instead of returning `None`).

### LOW (31)

### E1-01: Channels-first guard only catches 1-2 row arrays; (3..8, N) input is silently returned unprocessed
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_stage_dispatch.py:72-77` (`validate_and_normalize_input`), then `:91-98` (short-buffer early return)
- **Status**: NEW (residual gap in the fix for closed #6118; not a regression of what #6118 covers)
- **Description**: #6118 made `(2, N)` and `(1, N)` raise "looks channels-first". The heuristic is `shape[0] <= 2 and shape[1] >= MIN_SAMPLES`. A librosa-style multichannel load (`mono=False`) of 3-8 channels is `(C, N)` with `3 <= C <= 8`; it fails the `<= 2` test, then hits the `shape[0] < MIN_SAMPLES` short-buffer branch, which logs "Audio too short to master (6 samples, ~0.1ms ...)" and returns the input untouched. That is exactly the "silent no-op on a public API with a misleading millisecond warning" #6118 set out to remove, for every channel count except 1 and 2. The converse layout `(N, 3..8)` is accepted and processed natively with no downmix (stereo width/phase stages silently skipped), which is also outside the documented `(samples, channels)` stereo contract.
- **Evidence**: probe (an audit probe script (scratch, not retained)): `(2,88200)` -> `ValueError ... channels-first`; `(3,88200)`, `(4,88200)`, `(6,88200)`, `(8,88200)` -> returned `identical to input: True`, log line `Audio too short to master (6 samples, ~0.1ms at 44.1kHz); returning it unprocessed (need 1024 samples)`.
- **Impact**: A caller handing a channels-first multichannel array to the public processor gets unmastered audio of the right shape and no error. The backend and player always pass `(N, C)`, so no production trigger; library-API hardening only.
- **Suggested Fix**: Generalise the check to `shape[0] < MIN_SAMPLES <= shape[1]` (any 2-D array with a tiny first axis and a long second axis is channels-first), and either downmix or reject `> 2` channel `(N, C)` input explicitly.

### E1-02: A NaN-RMS chunk turns the realtime level-matcher's target gain into 10x (+20 dB) because `min(10.0, nan)` is 10.0
- **Severity**: LOW (latent: `AudioPlayer.get_audio_chunk()` has no production caller, and the loader sanitises NaN before the chain sees it)
- **Dimension**: Sample Integrity (NaN/Inf propagation)
- **Location**: `auralis/player/realtime/gain_smoother.py:23-25` (`AdaptiveGainSmoother.set_target`), fed from `auralis/player/realtime/level_matcher.py:105-120`
- **Status**: NEW (related to open #6106, which is the AGC burst design, not NaN handling; #5313 added a NaN repair only at the end of the chain)
- **Description**: `RealtimeLevelMatcher.process()` computes `current_rms = sqrt(mean(audio**2))`; with one NaN sample that is NaN, `current_rms == 0` is False, so `gain = current_target_rms / nan = nan` and `set_target(nan)` runs `max(0.0, min(10.0, nan))`. Python's `min(10.0, nan)` returns `10.0` (the `nan < 10.0` comparison is False), so a corrupt buffer becomes "apply the maximum +20 dB gain". The smoother then ramps toward 10x with its fast 0.02 attack and carries that state (`current_gain`) into the following buffer, where it decays at the slow 0.005 release. `RealtimeProcessor.process_chunk`'s final `validate_audio_finite` repairs only the NaN sample itself, so the neighbouring samples ship with the boosted gain (clamped only by the 0.95 ceiling).
- **Evidence**: probe (an audit probe script (scratch, not retained)): steady state gain 5.02, chunk peak 0.326; one chunk with a single NaN -> `gain_smoother.current_gain = 9.9999999948`, chunk peak 0.649 (2x); the next two clean chunks peak 0.469 and 0.326, gain 5.05 then 5.02, i.e. about 2 buffers (~46 ms) of wrong level from one NaN sample. Log: `NaN or Inf values detected and repaired in realtime chunk output ... 1 NaN`.
- **Impact**: Only if a non-finite sample reaches the realtime chain (upstream DSP bug, or a source that bypassed `validate_audio`): a +6 dB (to +20 dB, ceiling-limited) burst that outlasts the repaired buffer. Not reachable from decoded files today.
- **Suggested Fix**: In `set_target` (or before it in `process()`), treat a non-finite gain as "hold the current gain" (`if not math.isfinite(target): return`), and skip the matcher entirely for non-finite chunks. Sibling check: `AdaptiveGainSmoother.set_target` has no other caller, and `StreamingPeakCeiling.apply` already excludes non-finite peaks correctly.

### E2-02: `AdaptiveCompressor` soft-knee gain computer is discontinuous (and non-monotonic) at the top of the knee
- **Severity**: LOW (latent: the real-time `AutoMasterProcessor` is built only when `enable_auto_mastering` is set, and the backend builds the player with it off)
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/compressor.py:62-72`
- **Status**: NEW
- **Description**: The in-knee branch uses `soft_ratio = 1 + knee_ratio*(ratio-1)/ratio; gain_reduction = -over*(1 - 1/soft_ratio)`, which is not the quadratic knee that joins the linear region. At the top of the knee (`level = threshold + knee/2`) the knee branch returns `-knee*(r-1)/(2r-1)` while the above-knee branch returns `-knee*(r-1)/(2r)`. The static curve therefore drops by `knee*(r-1)*(1/(2r-1) - 1/(2r))` as the level crosses the knee edge: more input level produces *less* gain reduction.
- **Evidence**: probe an audit probe script (scratch, not retained), `knee2.py` (calls `_calculate_gain_reduction_vectorized` at `edge -/+ 1e-6 dB`):
  ```
  ratio 4.0 knee 6.0 : -2.571 dB -> -2.250 dB  (jump +0.32 dB)
  ratio 2.0 knee 4.0 : -1.333 dB -> -1.000 dB  (jump +0.33 dB)
  AutoMasterProcessor config (thr -24, ratio 1.3, knee 10): -1.875 -> -1.154 dB (jump +0.72 dB at -19 dBFS)
  scan -40..-5 dB: 1 non-monotone step, max rise 0.72 dB
  ```
- **Impact**: A 0.14-0.72 dB step in the target gain reduction whenever a sample crosses the knee edge. The attack/release follower (20/200 ms in `AutoMasterProcessor`) smooths it, so it shows up as slight level wobble on material hovering around the knee edge, not a click. Only audible if auto-mastering playback is ever enabled.
- **Suggested Fix**: Use the standard quadratic knee `-(1 - 1/r) * (x - T + W/2)**2 / (2*W)` inside the knee (continuous in value and slope at both edges), and pin continuity with a static-curve test.

### E2-03: `LowMidTransientEnhancer` designs its 4th-order band-pass in transfer-function (b, a) form: unstable at >= 176.4 kHz and mis-shaped from 192 kHz
- **Severity**: LOW (latent: only reachable through `AutoMasterProcessor`, off in the backend; and only for 176.4/192 kHz tracks)
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/dynamics/lowmid_transient_enhancer.py:48-57,108-111`
- **Status**: NEW
- **Description**: `signal.butter(4, [150/nyq, 1500/nyq], btype='band')` returns polynomial `(b, a)` coefficients, which `filtfilt` then applies. The low edge is 0.0016 of Nyquist at 192 kHz; an order-8 transfer function with poles that close to z = 1 is numerically ill-conditioned in direct form. Every other band filter in the engine uses `output='sos'` (the grep for `butter(` without `sos` returns only this file).
- **Evidence**: probe an audit probe script (scratch, not retained):
  ```
  sr     max|pole|    (b,a) response at 150/300 Hz   filtfilt RMS ratio vs SOS
  44100  0.99307     -3.0 / -0.0 dB                  1.000
  96000  0.99667     -3.0 / -0.0 dB                  1.000
  176400 1.00176     UNSTABLE
  192000 1.00161     -6.3 / +1.0 dB                  1.259
  ```
  (Poles outside the unit circle at 176.4/192/352.8/384 kHz.) `filtfilt` also raises on buffers under its pad length (~27 samples for this filter) where the SOS helper would degrade gracefully.
- **Impact**: At 176.4/192 kHz the "low-mid" band the enhancer expands is the wrong band (150 Hz corner 3 dB too low, +1 dB bump at 300 Hz) and the filter is formally unstable (filtfilt happens to stay finite on a few-second buffer, but a long run or feedback of state is not guaranteed). Hidden because the whole class is latent.
- **Suggested Fix**: Design with `output='sos'` and filter with `sosfiltfilt_safe`, like the rest of the DSP (the same swap also fixes the short-buffer raise).

### E2-04: `calculate_adaptive_peak_target` is still a three-step function of source loudness (0.30 dB and 0.20 dB level steps) after #5704 made the makeup gain continuous
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/utils/adaptive_loudness.py:112-140` (callers: `core/processing/adaptive_normalization.py:94` live on reference/hybrid jobs; `core/mastering_branches/continuous.py:251-253` offline; `player/realtime/auto_master.py:156` latent)
- **Status**: NEW (#5704 converted `calculate_adaptive_gain` only; the sibling in the same class was not in its scope)
- **Description**: `calculate_adaptive_peak_target(source_lufs)` returns 0.85 above -12 LUFS, 0.88 above -14 LUFS and 0.90 below, with hard `>` tests. `ContinuousMasteringBranch` turns that into `adapted_peak = clip(target_peak - 0.01, 0.84, 0.89)` and the final file gain, so the output peak level of two near-identical tracks straddling -12.0 or -14.0 LUFS differs by a fixed step. The class docstring promises "smooth" behaviour via `smooth_gate` for the gain; the peak target next to it uses exactly the categorical selector the continuous-space design removed.
- **Evidence**:
  ```
  -11.999 LUFS -> 0.85 (-1.412 dB)   -12.001 -> 0.88 (-1.110 dB)   step 0.30 dB
  -13.999 LUFS -> 0.88 (-1.110 dB)   -14.001 -> 0.90 (-0.915 dB)   step 0.20 dB
  ```
- **Impact**: 0.2-0.3 dB output-level step between otherwise indistinguishable tracks (offline CLI, and the whole-file reference/hybrid job path through `AdaptiveMode`). Below the usual JND for a single listen, but it is the category of defect the continuity guards (#4860, #5704, #5724) exist to prevent.
- **Suggested Fix**: Interpolate the three plateaus with the same `smooth_gate` knees `calculate_adaptive_gain` uses (centred on -12 and -14), and add the peak target to the #5704 continuity test.

### E2-05: Offline stages still switch on at a hard minimum effect: `bass_pct >= 0.05` in the transient shaper (full 4.7 dB attack boost appears from nothing), plus 0.3/0.5 dB `boost_db <` gates in five stages
- **Severity**: LOW (offline CLI subsystem, #4873)
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/stages/transient_shaper.py:57,74,85`; `auralis/core/stages/air_enhancement.py:59`; `clarity_boost.py:87`; `presence_enhancement.py:59`; `mid_warmth.py:52`
- **Status**: NEW (#5580 fixed the sub-bass HP gate and #5724 the stereo-expansion curve; these were not swept)
- **Description**: `transient_shaper.apply` computes a continuous `boost_db`, but then runs the bass band only `if bass_pct >= 0.05` (low-mid band: `low_mid_pct >= 0.05`), so a fingerprint moving from 0.0499 to 0.0501 turns the whole bass-band shaper from absent to full strength. Four more stages `return no_op(audio)` when their computed boost is under 0.3 dB (transient shaper: 0.5 dB), so the effect jumps from 0 to 0.3 dB at the gate. The CLAUDE/audit continuity rule is explicit: "a new hard `if x > threshold` gain step in a stage reopens the class".
- **Evidence**: probe an audit probe script (scratch, not retained) (80 Hz kick bursts on noise bed, `crest_db=10`, intensity 1, `boost_db=4.67`):
  ```
  transient_shaper bass_pct 0.0499 -> output identical to input (delta -inf dB)
  transient_shaper bass_pct 0.0501 -> delta vs dry = -9.6 dB re signal (4.67 dB attack boost on 60-250 Hz)
  ```
- **Impact**: Two thin-bass sources 0.0002 apart in `bass_pct` get audibly different attack character (4.7 dB of attack boost); the 0.3 dB gates are near JND. Offline tool weight only.
- **Suggested Fix**: Scale the band boost by a `smooth_gate`/S-curve of `bass_pct` (e.g. 0.03-0.07) instead of the comparison, and let the 0.3/0.5 dB gates fall away (the downstream filters already short-circuit on negligible gains).

### E2-06: `calculate_target_lufs` clamps the target to [-28, -2] after a bounded-lift curve, so the lift is unbounded and the target plateaus for sources below about -36 LUFS (and attenuates above -2)
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/parameter_generator_dynamics.py:40-65`
- **Status**: NEW
- **Description**: The function documents a "dynamics-aware maximum" lift: `gain_db = maximum_lift * tanh(desired_lift / maximum_lift)` with `maximum_lift = 8.25 - dynamics`, so lift <= ~8 dB. The final `np.clip(target_lufs, -28.0, -2.0)` then overrides it. For `input_lufs` below `-28 - maximum_lift` (about -36 LUFS) the target is pinned at -28.0, so the realised lift is `-28 - input` and grows without bound (limited only by `MAX_NORMALIZATION_GAIN_DB = 24`). Every source below -36 gets exactly the same target, which is the "clamp that flattens the range / plateau" the Dimension 2 monotonicity item names. At the top end `input_lufs = -1` is attenuated 1 dB although the curve intends no attenuation.
- **Evidence**: probe an audit probe script (scratch, not retained) (dynamic_range 0.2, per-chunk fingerprint path):
  ```
  in -35.0 -> target -27.00 (lift +8.0)    in -36.5 -> -28.00 (+8.5)
  in -40.0 -> -28.00 (+12.0)   in -50.0 -> -28.00 (+22.0)   in -60.0 -> -28.00 (+32.0, then capped to 24 downstream)
  in  -2.0 ->  -2.00 ( 0.0)    in  -1.0 ->  -2.00 (-1.0)
  ```
- **Impact**: Very quiet, high-dynamic sources (ambient, field recordings, classical intros) analysed by the per-chunk/whole-file fingerprint path are lifted by 12-24 dB instead of the designed <= 8.25 dB and all land on the same loudness. The brick-wall limiter then has to absorb whatever peaks result. Narrow input range, hence LOW. (The fixed-target streaming path uses `generate_targets_from_fingerprint`, a different linear 60 % blend toward -14 LUFS with the same lack of a lift cap.)
- **Suggested Fix**: Drop the lower clamp (the tanh already bounds the lift) or make it a soft limit on the lift, and keep only the upper ceiling; add a monotonic-and-bounded-lift test over `input_lufs` in [-60, -2].

### E2-07: Psychoacoustic EQ computes a per-frame spectrum analysis whose result nothing reads
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/eq/psychoacoustic_eq.py:162-172`; `auralis/dsp/eq/spectrum_gains.py:31-132`
- **Status**: NEW
- **Description**: `process_realtime_chunk` calls `analyze_spectrum(audio_chunk)` (Hann-windowed FFT, dB conversion and 25 masked band means) and passes the result to `calculate_adaptive_gains(spectrum_analysis, ...)`, but since #5703 removed the masking model `_calculate_target_gains(target_curve)` ignores it: gains are `curve * band.weight`, clipped and smoothed. The docstrings ("Calculate adaptive EQ gains based on spectrum analysis") and the #4101 windowing/coherent-gain comments still describe a computation that has no effect on the output.
- **Evidence**: grep: `spectrum_analysis` is read nowhere except being forwarded; probe an audit probe script (scratch, not retained): `analyze_spectrum` 0.175 ms of a 0.362 ms frame (48 %), 538 frames per 25-s backend window.
- **Impact**: About 90 ms of wasted CPU per 25-s chunk window (per chunk render, on the streaming hot path) and misleading documentation; no audio effect.
- **Suggested Fix**: Delete `analyze_spectrum`/`_calculate_band_energies` and the argument (or reinstate a real consumer); keep one test for the gain smoothing.

### E3-02: `stop()` racing `get_audio_chunk()` leaves the player STOPPED with a non-zero position
- **Severity**: LOW (microsecond window; `get_audio_chunk` is dormant in production)
- **Dimension**: Player State
- **Location**: `auralis/player/player_streaming_mixin.py:86-95`; `auralis/player/playback_controller.py:186-204,231-234`; `auralis/player/enhanced_audio_player.py:178-182`
- **Status**: NEW
- **Description**: `get_audio_chunk()` holds `_audio_lock` and checks `self.playback.is_playing()` (one `PlaybackController._lock` acquisition). It then calls `read_and_advance_position()` (a second acquisition). `AudioPlayer.stop()` takes no `_audio_lock`, so it can land between the two. `stop()` sets `state=STOPPED, position=0`, and then `read_and_advance_position` writes `position = min(0 + chunk_size, total)`. The "stop resets position to 0" invariant is overwritten, and one extra chunk is emitted after stop. The advance is not conditional on the state it was just checked against.
- **Evidence**: Audit probe script (scratch, not retained) forces the legal interleaving (`stop()` called inside the wrapper for `read_and_advance_position`): `state stopped position 1024 reported 0.0232...` (`get_playback_info()['position_seconds']`).
- **Impact**: After a stop the UI/info shows position 0.023 s, and the next `play()` resumes about one buffer (23 ms) into the track instead of at 0.
- **Suggested Fix**: Make the advance conditional inside the controller. Add a `read_and_advance_if_playing(advance_by, max_samples) -> int | None` under one `_lock` hold, and drop the separate `is_playing()` check in `get_audio_chunk`.

### E3-03: A `pause()` that lands inside `previous_track()`'s STOPPED window is lost
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:163-176` (flag cleared on a failed transition); `auralis/player/player_queue_navigation_mixin.py:163-203`; `auralis/player/playback_controller.py:267-287` (`load_and_stop`)
- **Status**: NEW (#5240/#5588 handle a pause before the swap or after the resume; this is the gap between them)
- **Description**: `previous_track()` goes through `load_file()`, whose swap hook calls `load_and_stop()` and forces `state = STOPPED`. Until `previous_track()` calls `playback.play()`, the state is STOPPED, and `PlaybackController.pause()` only transitions out of PLAYING. A user `pause()` in that window therefore returns False, and `AudioPlayer.pause()` then clears `_pause_requested`, so the resume check at `:200` never sees the user's request and playback resumes. The #5240 design ("a pause at any point up to here overrides the resume") does not hold in this window. The window covers `_schedule_fingerprint_load`, `gapless.start_prebuffering()` and the `file_loaded` callbacks. Backend REST `pause` (`_playback_lock`) is not serialized with REST `previous` (`_sequencer.lock`), so the two can overlap in production.
- **Evidence**: Audit probe script (scratch, not retained) (the user `pause()` is issued from the `file_loaded` callback): `user pause() during window -> False | flag False`, then `after previous_track: playing (user asked for pause)`.
- **Impact**: Rare ignored pause on a skip-back, so the track keeps playing after the user paused.
- **Suggested Fix**: Do not clear `_pause_requested` on a failed `pause()` while a navigation resume is pending. For example, keep a `_transition_in_flight` counter set by `next_track()` / `previous_track()`, and clear the flag on `play()` / `stop()` / end of the transition instead.

### E3-04: `RealtimeLevelMatcher`'s peak ceiling (and smoother) are still built for `config.sample_rate`; the #5729 fix covered only the auto-master and safety ceiling
- **Severity**: LOW (dormant `get_audio_chunk`)
- **Dimension**: Player State
- **Location**: `auralis/player/realtime/level_matcher.py:45` and `:38-41`, `:93-97`; `auralis/player/realtime/processor.py:147-176`
- **Status**: NEW (incomplete fix of closed #5729; the per-sample smoother alphas are also in open #6106)
- **Description**: `RealtimeProcessor.process_chunk()` forwards the track rate to `auto_master.set_sample_rate()` and `safety_ceiling.set_sample_rate()`. It calls `self.level_matcher.process(processed)` with no rate. The level matcher is the one stage that is ON in the shipped `PlayerConfig` (`enable_level_matching=True`, active whenever a reference is set, which `auto_reference_selection=True` does on every library load). Its `StreamingPeakCeiling` keeps the 44.1 kHz attack/release slopes, and its `AdaptiveGainSmoother` alphas are per-sample constants. This is the pattern that the Dim 3 checklist lists as a regression ("a rate-dependent stage built once for `config.sample_rate`").
- **Evidence**: Audit probe script (scratch, not retained) (shipped config, 96 kHz chunk): `safety_ceiling.sample_rate 96000 | level_matcher.peak_ceiling.sample_rate 44100 | level matcher attack slope/sample 0.01134 (2 ms at 96k would be 0.00521)`. The ceiling attack/release run 2.18x too fast in time on 96 kHz material.
- **Impact**: Mis-scaled limiter ramp times on non-44.1 kHz tracks in the level-matching path. This is subtle (limiter timing), and only reachable if the realtime chain is driven.
- **Suggested Fix**: Pass the rate into `RealtimeLevelMatcher.process()`, or give it `set_sample_rate()` that re-derives `peak_ceiling` (and the smoother alphas as per-second constants, together with #6106), and call it next to the auto-master call. Extend `test_realtime_track_sample_rate_5729.py` to assert it.

### E3-05: `get_queue_info()['has_next']` / `['has_previous']` ignore repeat, contradicting `next_track()` / `step_previous()`
- **Severity**: LOW (the REST field has no frontend consumer; the selectors recompute locally)
- **Dimension**: Player State
- **Location**: `auralis/player/components/queue_manager.py:231-232`; contrast `components/queue_navigation.py:38-57,120-141`, `queue_controller.py:196-202`
- **Status**: NEW
- **Description**: The atomic snapshot computes `has_next = idx < len-1` and `has_previous = idx > 0`. With `repeat_enabled` the queue wraps, so `peek_next()`, `has_next_track()` and `next_track()` all advance past the last track (and `step_previous()` wraps from the first). The snapshot, which is the REST `QueueInfoResponse.has_next/has_previous` source, reports "no next/previous" at the ends. The auto-advance gate (`has_next_track()`) and the snapshot disagree about the same queue.
- **Evidence**: Audit probe script (scratch, not retained): `at last track, repeat on -> has_next: False | has_next_track(): True | peek_next: {'filepath': '/a.flac'}`; `at first track, repeat on -> has_previous: False | step_previous -> ({'filepath': '/c.flac'}, 0, 2)`. The existing tests only cover repeat-off.
- **Impact**: Any consumer that disables next/previous controls from this field greys them out in repeat-all mode even though they work.
- **Suggested Fix**: `has_next = idx < len-1 or (repeat_enabled and len > 0)`; `has_previous = idx > 0 or (repeat_enabled and len > 0)`; add repeat-on cases to `test_queue_controller.py`.

### E3-06: `AudioPlayer.seek(float('nan'))` raises `ValueError` (the #6130 fix covered inf and huge values only)
- **Severity**: LOW (the HTTP model rejects NaN, so there is no remote trigger today)
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:217`
- **Status**: NEW (sibling of closed #6130)
- **Description**: `int(min(max(position_seconds * sample_rate, 0.0), float(max_samples)))`. `max(nan, 0.0)` and `min(nan, x)` both return NaN (comparisons are False), so `int(nan)` raises. The exception escapes `defer_notifications()` and `_audio_lock` (released), so there is no state corruption.
- **Evidence**: Audit probe script (scratch, not retained): `nan RAISES ValueError cannot convert float NaN to integer`; `inf`, `-inf`, `±1e308` all clamp correctly.
- **Impact**: Engine API contract hole for any non-HTTP caller. The backend's `SeekRequest` validator is the only guard.
- **Suggested Fix**: `if not math.isfinite(position_seconds): return False` (or treat as 0) before the clamp; add a NaN case to `test_seek_huge_position_6130.py`.

### E3-07: Every user `next_track()` is recorded and announced as a track *completion*; `total_play_time` is never written
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/player_queue_navigation_mixin.py:118`; `auralis/player/integration_reporting.py:86-94`; `auralis/player/integration_manager.py:96`
- **Status**: NEW
- **Description**: `next_track()` unconditionally calls `integration.record_track_completion()`, which bumps `tracks_played` and emits `{'action': 'track_completed'}`. The caller cannot tell a skip from a natural end, because `_auto_advance_next` and the REST `next` both go through the same method. `previous_track()` records nothing. `total_play_time` is initialised to 0.0 and has no writer anywhere in the tree, so `get_playback_info()['session']['total_play_time']` is permanently 0.
- **Evidence**: Audit probe script (scratch, not retained) (play track A, user skip): `events: ['track_completed'] tracks_played: 1 total_play_time: 0.0`. `grep -rn total_play_time auralis auralis-web/backend` shows only the init and the read.
- **Impact**: Wrong session statistics and a misleading `track_completed` event for any consumer that treats it as listening history. No production consumer today (see #6286).
- **Suggested Fix**: Record completion only from the auto-advance path (for example a `completed: bool` argument to `next_track()` set by `_auto_advance_next`), and either accumulate `total_play_time` from position or delete the field.

### E4-02: Truncated AIFF/AU files load silently as short clips; the "non-WAV truncation" check cannot fire and its test only mocks libsndfile
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/soundfile_loader.py:111-130` (frame-count comparison); pinning test `tests/auralis/io_module/test_soundfile_truncation_4131.py:35-48` (patches `sf.info` and `sf.read`)
- **Status**: NEW
- **Description**: Truncation is detected for WAV (RIFF-declared size vs file size) and, by assumption, for FLAC/AIFF/AU by comparing `len(sf.read())` to `sf.info().frames`. For AIFF and AU libsndfile clamps `info.frames` to what is actually in the file, so the two numbers are always equal and the check never triggers. The #4131 test only passes because it replaces both calls with a fake that reports the "full" frame count. FLAC is fine in practice (a cut FLAC raises `flac decoder lost sync`).
- **Evidence**: 96 kHz stereo AIFF (768054 bytes, FORM size field says 768054) cut to 100000 bytes: `sf.info(...).frames == 24986`, `load_audio` returns `(24986, 2)` with no error and no warning (the full file is 192000 frames, 13 % present). Same for the `.au` and `.aif` copies (24992 / 24986 frames). The equivalent 22.7 %-complete WAV at least logs `WARNING_TRUNCATED_FILE`. `get_audio_info` also reports the truncated duration, which is what the scanner would store.
- **Impact**: A partially copied or downloaded AIFF/AU plays as a short track with no diagnostic and is stored with the short duration. Corrupt-file handling is the checklist item. Small user base (AIFF/AU are rare in the library).
- **Suggested Fix**: Add a header-declared-size check for AIFF (`FORM` size at bytes 4-8, big endian) and AU (data size at bytes 8-12, `0xFFFFFFFF` means unknown), alongside `_get_wav_declared_size`, using the same 10 %/90 % thresholds. Rewrite the test with a really truncated AIFF/AU fixture instead of a mocked `sf`.

### E4-03: Native 5.1/7.1 downmix is attenuated by a content-dependent peak rescale, so the same mix is 0-6 dB quieter as FLAC/WAV than as M4A/OGG, and the FFmpeg path can emit samples above 1.0
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/processing.py:244-251` (peak renormalise in `downmix_to_stereo`); docstring `:179` ("matches `ffmpeg -ac 2` on the same layout"); FFmpeg side `auralis/io/loaders/ffmpeg_command.py:56-57`
- **Status**: NEW (#3743/#5735 fixed channel routing and coefficients, not level)
- **Description**: The coefficients match FFmpeg's, but the native path then multiplies the whole file by `input_peak / out_peak` whenever the summed downmix peaks above the loudest *input* channel (the input peak includes the LFE channel). FFmpeg's `-ac 2` applies no such rescale. The resulting level offset depends on how much Center/surround content a mix has, so identical 5.1 content is loaded at a different level depending on its container, and mastering targets/gain decisions downstream (which depend on input loudness) differ with it.
- **Evidence**: 5.1 file with L=R=C=0.5 sine, LFE and surrounds silent, as FLAC through `load_audio` versus `ffmpeg -i f.wav -ac 2`: native peak 0.50 / rms 0.3536; FFmpeg peak 0.8536 / rms 0.6036, a difference of 4.6 dB. A second, music-like synthetic 5.1: native rms 0.248 versus M4A (FFmpeg) rms 0.418 (-4.5 dB). In the M4A 5.0 test the FFmpeg path produced peak 1.067 (float32 temp WAV, not clipped at decode; only `saver.save`/the engine clip later, e.g. `simple_mastering`'s temp WAV via `save_audio`).
- **Impact**: Inconsistent input level between formats for surround sources; the FFmpeg route can feed |x| > 1.0 into the pipeline. Rare content, no corruption.
- **Suggested Fix**: Pick one convention for both paths: either drop the native peak rescale (and let the engine's input gain handle headroom), or apply the same fixed normalisation (divide by the matrix row sum) in both; fix the docstring claim accordingly.

### E4-04: FFmpeg protocol guard misses schemes libavformat actually parses (digit-first, one-letter, `+`/`.`-prefixed), so `1: Intro.mp3` fails with a misleading error
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_path_guard.py:23` (`_PROTOCOL_PREFIX_RE`), `:46-49` (`ffmpeg_input_path`)
- **Status**: NEW (incomplete fix of closed #5733, which anchors only names matching the regex)
- **Description**: libavformat treats any leading run of `[A-Za-z0-9+.-]` followed by `:` as a URL scheme (no minimum length, may start with a digit). The guard's regex requires a letter first and at least two scheme characters, so a relative regular file whose name starts like `1: Intro.mp3`, `A: Side.mp3`, `1-2: x.mp3`, `+x: y.mp3` or `.hidden: y.mp3` is neither anchored with `./` nor rejected; ffmpeg/ffprobe then report `Protocol not found`.
- **Evidence**: Relative names in cwd, `load_audio()`: all five raise `Corrupted or unsupported audio file: Could not probe sample rate / channel count...` and `get_audio_info()` gives `FFprobe failed: <file>: Protocol not found`. `Live: Concert.mp3`, `pipe:0.mp3`, `concat:a.mp3`, `file:x.mp3` (which the regex does match) load correctly.
- **Impact**: Narrow: only bare relative names (CLI use from the file's directory); library and upload paths are absolute, and relative folder scans keep a `/` in the path. The error text also blames the file rather than the name.
- **Suggested Fix**: Replace the regex with libavformat's rule (`^[A-Za-z0-9+.\-]*:`) for the anchoring decision, or anchor any non-absolute path with `./` / `os.path.abspath` before it reaches argv.

### E4-05: `check_ffmpeg()` / `check_ffprobe()` cache a transient failure for the process lifetime, and an `OSError` escapes as a raw exception
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_probe.py:85-122` (`check_ffmpeg`), `:125-141` (`check_ffprobe`); caller `auralis/io/loaders/ffmpeg_loader.py:50-57`
- **Status**: NEW
- **Description**: Both are `lru_cache(maxsize=1)` and return False on `TimeoutExpired` (10 s) or a non-zero exit, so one slow first spawn (cold disk, a scan starting 20 threads, antivirus on first launch) disables every FFmpeg format until restart, reported as `ERROR_FFMPEG_NOT_FOUND`. Only `FileNotFoundError` and `TimeoutExpired` are caught: a `PermissionError`/`OSError` (binary present but not executable) propagates out of `_validate_input` as a raw exception instead of a `ModuleError`. The two version probes also omit `stdin=subprocess.DEVNULL`, contrary to the checklist statement that every ffmpeg/ffprobe call passes it (harmless for `-version`).
- **Evidence**: With `subprocess.run` patched to raise `TimeoutExpired` once: `check_ffmpeg()` returns False, and the second call (ffmpeg really installed) still returns False. With `PermissionError`: `check_ffmpeg()` raises it.
- **Impact**: Rare, self-inflicted loss of M4A/AAC/WMA/MP3/OGG/OPUS decoding until app restart; confusing error text.
- **Suggested Fix**: Do not memoise the timeout/OSError outcomes (cache only a definitive result: found, or `FileNotFoundError`), map `OSError` to False, and pass `stdin=subprocess.DEVNULL`.

### E4-06: `Result`/`pcm16`/`pcm24` reject `.aif` although `.aif` is an accepted input extension
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/results.py:51-56`; contrast `auralis/io/formats.py:15-21`
- **Status**: NEW
- **Description**: The extension is upper-cased and passed straight to `sf.check_format`, which knows `AIFF` but not `AIF`. `Result('x.aif')` therefore fails with `TypeError: AIF format is not supported`, while the loader, scanner and upload allowlist all treat `.aif` as a supported audio format.
- **Evidence**: `pcm16('o.aif')` and `pcm24('o.aif')` raise `TypeError AIF format is not supported`; `.aiff`, `.wav`, `.flac`, `.au`, `.w64`, `.caf` pass. No production caller (`Result` is public API re-exported from `auralis/__init__.py`), so there is no runtime impact today.
- **Impact**: Public-API asymmetry only.
- **Suggested Fix**: Map extensions through a small alias table (`aif` to `AIFF`) before `check_format`.

### E5-01: True Peak guard is input-peak-keyed and now redundant; it silently costs up to ~0.8 dB on hot masters
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_assembly.py:105-141` (called at `auralis/core/mastering_chunk_loop.py:186`)
- **Status**: NEW
- **Also found by**: Dimension 2 (E2-08, same guard, same `mastering_chunk_assembly.py` code; folded in here). It measured the loss at up to 0.77 dB on hot sources.
- **Description**: With the prescan present (always, via `master_file`), `apply_true_peak_guard` multiplies every chunk by `0.9441 / (song_peak_linear * 1.0317)` whenever that is < 1. `song_peak_linear` is the INPUT file peak, not the processed signal, and the same constant is applied whether or not the processed signal is anywhere near the ceiling. Since #5694 the two-pass `two_pass_correction_gain` measures the actual final sample and 4x true peak and enforces 0.99 / -0.5 dBTP by construction. The guard therefore no longer protects anything and only changes level. It fires for any input with peak > ~0.9155 (-0.77 dBFS), which covers typical modern loud masters. Meanwhile the chain's own gains (limiter ceiling -1 dB × `file_gain = adapted_peak / song_peak`) already leave those files 1.3-2 dB under the ceiling, so the extra attenuation is pure loss. Quiet inputs are corrected up to -0.50 dBTP while hot inputs end at -2.0 to -2.8 dBTP. The docstring ("caps True Peak at -0.5 dBFS") is stale for the same reason.
- **Evidence**: Audit probe script (scratch, not retained) (24 s stereo, chunk 5 s / crossfade 1.5 s, mocked fingerprint), same input rendered with the guard and with it replaced by identity. None of these needed `correction_gain < 1`, so the ceiling was not at stake:

  | input peak | with guard | without guard |
  |---|---|---|
  | 0.92 | sample peak 0.8577, TP -1.33 dBTP | 0.8622, -1.28 |
  | 0.97 | 0.7715, -2.25 dBTP, rms -23.31 | 0.8177, -1.74, rms -22.80 |
  | 0.999 | 0.7274, -2.76 dBTP, rms -23.61 | 0.7940, -2.00, rms -22.85 |

  Probe `probe9.py` shows that for input peaks 0.03-0.3 the output TP is exactly -0.50 dBTP. Probe `probe14.py` (real fingerprint service, scratch HOME) agrees: input peak 0.999 gives TP -2.76 dBTP, while 0.25 and 0.6 give -0.50.
- **Impact**: On hot sources, the main use case for a "mastering" tool, the offline master comes out 0.5-0.8 dB quieter than the pipeline otherwise produces, for no safety benefit. Offline-tool weight, so LOW.
- **Suggested Fix**: Drop the song-peak branch of `apply_true_peak_guard`, or fold it into the measured correction. The pass-1 measurement already guarantees the ceiling. Keep the per-chunk 4x branch only for the direct `_process()` test path, and update the docstring.

### E5-02: Output sink is opened only after the full measurement pass, so a bad output path or format fails after half the work
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:90-109` (`_render_to_sink` pass 1 runs before `publish_atomically` / `sf.SoundFile(...)`)
- **Status**: NEW
- **Description**: Before the #5694 two-pass change the output `SoundFile` was opened before the first chunk. Opening it now happens in pass 2, so everything that validates the destination (format/extension vs `subtype='PCM_24'`, a parent directory that cannot be created, permissions, a full disk at open time) is checked only after the whole measurement render has been done. `master_file()` and `auto_master.py` single-file mode do no earlier check (folder mode only guards overlap with the input tree).
- **Evidence**: Audit probe script (scratch, not retained) (20 s file, 5 s chunks = 4 chunks, `_process` wrapped with a counter):
  - Output `t4_out.xyz` raises `TypeError: No format specified and unable to get format from file extension` after 4 `_process` calls.
  - Output `/nonexistent_dir_zz/forbidden/out.wav` raises `PermissionError` after 4 `_process` calls (the full pass 1).
  - The extension case surfaces as an opaque `TypeError`.
- **Impact**: A typo'd extension or unwritable destination on a long track wastes a full DSP pass (roughly half the render time) before reporting. No data loss and no corrupt output (staging is atomic), so LOW.
- **Suggested Fix**: Validate the destination before pass 1. For example, create the staged sink (or do `sf.check_format(fmt, 'PCM_24')` plus `mkdir`/write probe on the parent) up front and keep it, or move pass 1 inside `publish_atomically` so the staging file is opened first.

### E6-02: `MasteringFingerprint` ignores the shared `stereo_window()` downmix, so a >2-channel file loses its Center
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/mastering_fingerprint.py:143-148` (`left = y[0]`, `right = y[1]`, `mono = (left + right) / 2`); contrast `auralis/analysis/fingerprint/windows.py:44-64` (`stereo_window`)
- **Status**: NEW (sibling of closed #5711, which fixed only the 25D windows; #6143 aligned only the window position)
- **Description**: The 25D windows fold >2 channels with `stereo_window()` (BS.775 for 5.1/7.1) so Center and surrounds count. `MasteringFingerprint.from_audio_file` still takes the first two channels of `librosa.load(mono=False)` and averages them. The FFmpeg-routed formats are unaffected (`-ac 2` downmix), so the two fingerprints also disagree between formats.
- **Evidence**: 20 s, 6-channel WAV with the signal only in channel 3 (Center): `MasteringFingerprint.loudness_dbfs` -36.99, `crest_db` 14.14, centroid 11020 Hz; the 25D fingerprint of the same file: `lufs` -17.04, `crest_db` 6.52.
- **Impact**: The advisory mastering recommendation (`AdaptiveMasteringEngine.recommend_weighted`, reasoning text "Very quiet original") is wrong for dialogue-in-center surround files. Low reach (multichannel files in a desktop library, advisory output).
- **Suggested Fix**: Run `y` through `windows.stereo_window()` before the mono mix.

### E6-03: `_on_worker_drained()` is called twice per worker per run, so `on_drained` fires while other workers are still extracting
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/services/fingerprint_queue.py:252-256` (end of Phase 1) and `:276-279` (end of Phase 2); counter in `auralis/services/fingerprint_worker.py:113-139`
- **Status**: NEW (listed as a completeness check in the #5954 issue text, but commit `cfaef28fa` fixed only `should_stop` / join; the double count is untouched)
- **Description**: `_drained_workers` is incremented once after Phase 1 and again after Phase 2 per worker, and the callback fires when the total reaches `len(self.workers)`. A worker that finishes both phases quickly contributes 2 to the count while a slow worker is still inside Phase 1. The existing tests (`tests/auralis/test_refresh_cloud_hooks_3479.py`) model one report per worker per wave, which is not what the loop does.
- **Evidence**: Instance with 4 workers, `_processed_since_drain=10`; workers 0 and 1 each report twice (both phases done) while workers 2 and 3 are still extracting: `on_drained` fired 1 time. The startup wiring (`config/startup/components.py:137`) makes this callback `refresh_cloud`, so the reference cloud is seeded from a half-fingerprinted library. Also, when Phase 2 finds nothing, the second report leaves `_drained_workers == N`, so the next wave fires on its first drain.
- **Impact**: Reference-cloud refresh runs early on partial data (it runs again at the true end if tracks were processed after the early fire, so the end state is correct). Wasted work and a transiently wrong cloud only.
- **Suggested Fix**: Count each worker once per wave (a set of worker ids, cleared on fire) or only report after Phase 2.

### E6-04: `.25d` sidecar validation compares naive local-time strings, so a timezone change invalidates every sidecar
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/library/sidecar_manager.py:162` (writer, `datetime.fromtimestamp(st_mtime).isoformat()`) and `auralis/library/sidecar_validation.py:63` (reader, same expression)
- **Status**: NEW (same family as closed #4881, scanner naive-UTC vs naive-local; the sidecar pair was not touched)
- **Also found by**: Dimension 7 (E7-05, same naive-local-time mtime comparison in the sidecar pair; folded in here). Probe: valid under UTC, invalid under America/Sao_Paulo.
- **Description**: Both sides serialise the file mtime as naive local time, but the string is compared as text. Sidecars are written next to the audio and meant to be portable (NAS, external drive, another machine); a different `TZ` (travel, VM or container in UTC, library opened from another machine) changes the string for the same instant.
- **Evidence**: Wrote a sidecar under `TZ=UTC` (`SidecarManager.write`), then `is_valid()` -> `True` under `TZ=UTC` and `False` under `TZ=America/Argentina/Buenos_Aires`. The mismatch is logged at DEBUG only (`sidecar_validation.py:65`).
- **Impact**: The fast path is silently skipped and the track is re-analysed (about 1 s of DSP plus decode per track), and the sidecar is then overwritten in the new timezone, flipping back on the next change. No wrong data.
- **Suggested Fix**: Store and compare `st_mtime_ns` (or a UTC ISO string); accept the old format for one version.

### E6-05: Probe-window failures are handled inconsistently: an FFmpeg probe error discards the whole fingerprint, an empty probe silently disables the LUFS/crest correction
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/windowed_loading.py:118-123` (FFmpeg probes, no guard) vs `:154-163` (librosa probes in `try/except: pass`); `auralis/analysis/fingerprint/windowed_compute.py:117-139` (`_apply_probe_correction`, `except Exception: pass`)
- **Status**: NEW (the silent `except` is the unfixed half of the E6-07 suggestion; #6141 fixed only the sentinel)
- **Description**: `_apply_probe_correction` is documented as best-effort ("the body window alone is fine"), and the librosa branch skips a probe that fails to load. The FFmpeg branch does not: if the 25 % / 75 % probe decodes nothing, `load_with_ffmpeg` raises "Truncated audio file ... got 0.00s" and the outer `except` in `compute_windowed_fingerprint` returns `None` for the track. Separately, a probe that comes back with zero samples (no exception) makes `_rms_lufs_crest` raise on `np.max` of an empty array; the surrounding `except Exception: pass` swallows it with no log and skips the correction for all windows, even when the other probe is valid.
- **Evidence**: 130 s MP3 (Xing header intact) cut to 70 % / 60 % of its bytes: body decodes ("appears truncated 57.2 %" warning) but the 75 % probe raises, so `compute_windowed_fingerprint` -> `None` (a 90 % cut succeeds). `_apply_probe_correction({'lufs': -40, 'crest_db': 10}, body_at_-40dB, [empty, loud])` leaves `lufs -40.0`; with two valid probes it gives `-17.69`.
- **Impact**: A damaged or partly downloaded MP3/AAC/Opus that still plays is never fingerprinted (retried every start), and in the empty-probe case the stored LUFS silently keeps the single-window bias the correction exists to remove (up to 9 dB on ambient intros).
- **Suggested Fix**: Wrap each FFmpeg probe like the librosa branch, filter zero-length windows before the median, and log at WARNING when the correction is skipped.

### E6-06: `LoudnessMeter` true peak is biased up by Gibbs overshoot at every chunk edge
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/loudness_meter.py:190-197` (`_calculate_true_peak_linear`, per-chunk `signal.resample_poly`), accumulated at `:87-99`
- **Status**: NEW
- **Description**: `measure_chunk` oversamples each 400 ms block independently, and `resample_poly` zero-pads the block edges. A sustained tone that is non-zero at a block edge sees a step there and overshoots, which is then kept as the track's true peak.
- **Evidence**: Stereo 997 Hz sine at 0.5 (-6.02 dBFS, true peak -6.02): `finalize_measurement().true_peak_dbfs` = -5.00 / -4.94 / -5.06 for three phases (+1.0 dB); constant 0.5 block -> -4.93. Noise-like material is unaffected (noise -0.71 and clipped noise -0.66 match `ffmpeg ebur128` -0.7 / -0.6), so the bias appears only on tonal or sustained material.
- **Impact**: Reaches `QualityMetrics` / `LoudnessAssessor` (`max_true_peak_dbfs` -1.0 compliance and 20 % of the loudness score) and `MasteringEvaluator`. The quality gate is opt-in and nothing in production reads it (#5712), so offline evaluation only.
- **Suggested Fix**: Oversample with enough pre/post context from the neighbouring block (or carry filter state across blocks) and drop the edge samples before taking the max.

### E6-07: Two analysis metrics are computed on relative/negative dB values and are meaningless (no consumers)
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/spectrum_operations.py:124` (`rms_to_db` default ref) feeding `calculate_spectral_centroid` (`:150-170`); `auralis/analysis/dynamic_range.py:199-216` (`peak_distribution`); same default-ref pattern at `auralis/analysis/dynamic_range_dynamics.py:130` (`envelope_db`)
- **Status**: NEW
- **Description**: `AudioMetrics.rms_to_db(x)` with no `ref` normalises to the loudest element and clips at -80 dB. (1) `map_to_bands` therefore returns a per-chunk spectrum of values <= 0, and `calculate_spectral_centroid` computes `sum(f * s) / sum(s)` on those negative values, so the loudest band gets weight 0 and the quietest the most. (2) `peak_distribution` labels the same relative values `*_level_db`.
- **Evidence**: `SpectrumAnalyzer.analyze_file` on a 200 / 2000 / 8000 Hz tone: `peak_frequency` 196 / 1929 / 7933 (correct) but `spectral_centroid` 2797 / 2581 / 2415 Hz and the result is flat across tone frequency. `analyze_dynamic_range` on a sine peaking at -2.5 dBFS and at -22.5 dBFS gives identical `peak_distribution` (`max_peak_level_db` 0.0, `average_peak_level_db` -3.5 for both). Grep: no reader of `spectral_centroid`, `max_peak_level_db`, `average_peak_level_db` or `envelope_percentiles` outside `analysis/`.
- **Impact**: Wrong numbers in `detailed_metrics['spectrum_analysis']` / `['dynamic_range']` returned by `QualityMetrics.assess_quality`; no production consumer, so cosmetic. Sibling of the closed #5099 (`rms_to_db` self-referencing).
- **Suggested Fix**: Pass `ref=1.0` where the field is documented as a level, and compute the centroid on the linear magnitude (rolloff already converts back from dB), or delete the unused metrics.

### E6-08: `MasteringProfileDatabase.add_profile` prints to stdout on every engine construction
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/mastering_profile.py:196`
- **Status**: NEW (same class as closed #4122, `MasteringFingerprint.from_audio_file` print; this one was missed)
- **Description**: `print(f"Added profile: ...")` runs for each of the 7 built-in profiles each time `AdaptiveMasteringEngine()` is built, and the backend builds one per `ChunkedAudioProcessor` that asks for a recommendation (`auralis-web/backend/core/chunk_mastering.py:54`).
- **Evidence**: Code path above; no logger involved.
- **Impact**: 7 stdout lines per track recommendation in the backend / Electron process output. No functional effect.
- **Suggested Fix**: Use `debug()` from `auralis.utils.logging`.

### E6-09: `FingerprintService.get_or_compute` never writes a `.25d` for FFmpeg-only containers
- **Severity**: LOW
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:151-175` (header probe via `soundfile.info`)
- **Status**: NEW (follow-up to closed #6231; the comment "a real file always probes" is false for `.m4a/.aac/.wma`)
- **Description**: With no pre-loaded audio, the sidecar metadata comes from `soundfile.info`, which cannot open `.m4a/.aac/.wma`. The code then logs "Skipping .25d sidecar ... (#6231)" and never caches. The backend extractor (`auralis-web/backend/core/fingerprint_loading.py:200-220`) gets the duration from mutagen and does write sidecars for the same formats.
- **Evidence**: `sf.info('long.m4a')` -> "Format not recognised" (`wav/flac/mp3/ogg/opus` open fine).
- **Impact**: Latent: the player-side fingerprint thread is disabled in the shipped build (#5708) so this path is cold; if enabled, every M4A track outside the library is re-analysed (3 FFmpeg windows) on each load with a WARNING each time.
- **Suggested Fix**: Reuse `probe_file_properties` / mutagen (or `ffmpeg_probe._probe_audio`) for the sidecar metadata.

### E7-03: A tag removed from a file is never cleared in the DB on rescan
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/track_repository_mutation.py:140-169` (`update_by_filepath`: `if key in track_info`, `if 'artists' in track_info`, `if 'genres' in track_info`, `if track_info.get('album')`), `auralis/library/scanner/metadata_extractor.py:208-253` (absent tag == absent key)
- **Status**: NEW
- **Description**: `audio_info_to_track_info()` omits keys for tags that are missing. The update path only writes keys that are present, so deleting the album, artist, genre, year or track-number tag from a file and rescanning (the file's mtime changed, so the track is re-processed) updates the row's other fields but leaves the removed values in place. Title is the exception (falls back to the filename stem).
- **Evidence**: Audit probe script (scratch, not retained) (real FLAC with tags, tags deleted, mtime bumped, `LibraryScanner.scan_directories`):
  ```
  1: Song ['Band'] Rec ['Rock'] 1999 3
  Scan Results: 1 found, 0 added, 1 updated, 0 failed
  2: Song ['Band'] Rec ['Rock'] 1999 3        # all removed tags still present
  ```
- **Impact**: DB metadata (and album/artist browse pages) can't be corrected by removing a wrong tag; the stale values persist until the row is deleted and re-imported.
- **Suggested Fix**: When metadata extraction succeeded (non-empty dict), treat a missing key as cleared (`[]` / `None`) for artists, genres, album, year, track and disc; keep the conservative behavior only when extraction failed outright.

### E7-06: Upgraded databases lack the unique `filepath_key` index that fresh installs have
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/migrations/migration_v017_to_v018.sql:33` (non-unique `ix_tracks_filepath_key`) vs `auralis/library/models/track.py` (unique); acknowledged in `tests/auralis/library/test_schema_parity_5753.py` ("REAL DRIFT ... Fixing it needs a migration")
- **Status**: NEW (the drift is documented in a test but has no open issue; #6103, which it cites, is closed)
- **Description**: `filepath_key` is the dedup identity added for case-insensitive platforms (#4842). Fresh `create_all` databases enforce it with a UNIQUE index, migrated ones do not, so on upgraded Windows/macOS libraries two concurrent adds of case-variant spellings of one file (manual scan racing the auto-scanner is the only overlap not blocked by path reservation of identical roots) or `relocate_missing_track()` re-pointing onto an existing key can store two rows for one file, which the "unique" contract elsewhere assumes cannot happen (`get_by_path(...).first()`, `update_by_filepath`).
- **Evidence**: `test_schema_parity_5753.py` accepted entry `index tracks.ix_tracks_filepath_key: definition differs (upgraded unique=False)` ("REAL DRIFT ... an upgraded database can hold two rows with the same key"); the test passes (3 passed), confirming the drift is current.
- **Impact**: Rare duplicate track rows on upgraded libraries; behavior differs by how the database was born.
- **Suggested Fix**: Add a migration that de-duplicates by `filepath_key` (merge playlist/favorite/play-count onto the lowest id) and then creates the unique index; drop the accepted-difference entry.
## Relationships

- **Decode-route divergence**: E4-01, E4-02 and E4-03 share one root cause. There is no single rule for when a file goes through libsndfile and when through FFmpeg, so the enhanced stream, `stream_normal`, `load_audio` and the scanner each decide for themselves. Fixing E4-01 by extension (`SOUNDFILE_FORMATS`) closes the widest gap, and its suggested fix names two sibling readers that open FFmpeg-format files with `sf.SoundFile` (`fingerprint_loading.py:37`, `track_repository_lifecycle.py:~174`).
- **Partial-fix pairs**: each of E1-01/#6118, E3-04/#5729, E3-06/#6130, E4-04/#5733, E2-04/#5704, E6-02/#5711 and E7-04/#6080 can reuse the original fix's test with one more parametrised case. Fix them together by checking the sibling set the original issue named.
- **Sidecar clock**: E6-04 (merged with E7-05) and open #6004 both concern the central `.25d` store. A fix that stores UTC would also help the re-analysis cost of E6-09.
- **Peak handling in the offline CLI**: E5-01 (merged with E2-08) is redundant with the #5694 two-pass correction. E2-05's hard gates and E2-06's target plateau sit in the same stage chain and both reopen the continuous-space class.
- **Level matcher**: E1-02 (NaN to +20 dB), E3-04 (44.1 kHz ceiling) and open #6106 (AGC bursts) are three defects in `RealtimeLevelMatcher` and `AdaptiveGainSmoother`. Rework it once, and the dormant status of `get_audio_chunk` makes this low priority.
- **Fingerprint queue**: E7-04 and E6-03 are both worker-lifecycle accounting bugs. E7-04 can leave outdated fingerprints unrefreshed when a claim race is read as "queue empty", and E6-03 fires the reference-cloud refresh early.
- **Possibly stale open issue**: the DSP sub-audit found #5700 (OPEN) appears already fixed in code (`proxy_to_k_offset_db` in `continuous_mode.py`), and the Sample Integrity sub-audit confirmed the seam gain mismatch is at most 0.005 dB. Worth re-verifying and closing.

## Prioritized Fix Order

1. **E4-01 (HIGH)**: silent holes in the enhanced stream. Small change (decide by extension), clear regression test (`-write_xing 0` VBR MP3 and a `cat`-joined MP3).
2. **E7-04 (MEDIUM, regression of #6080)**: finishes a fix already half-landed. Return a distinct "lost race" result from `claim_next_outdated_fingerprint` and stop `_guarded` from masking DB errors as "queue empty".
3. **E7-01 and E7-02 (MEDIUM)**: library data quality that users see (empty albums, split compilations), and E7-03 and E7-06 in the same repository files. Do these together.
4. **E6-01 (MEDIUM)**: fingerprint tail-frame weighting. Fix before the next `FINGERPRINT_ALGORITHM_VERSION` bump so it costs one re-analysis, not two. E6-02 can ride along.
5. **E2-01 (MEDIUM, offline CLI)**: sub-bass and bass corners are mis-placed at 44.1 kHz. Apply the #4211/#4218 floor fix to `ParallelEQUtilities` and to `adjust_stereo_width_multiband`.
6. **E3-01 (MEDIUM, latent)**: remove the sample-rate guard in `advance_with_prebuffer`, since the swap installs the new rate either way.
7. **Partial-fix LOWs** (E1-01, E3-04, E3-06, E4-04, E2-04, E6-05): quick wins, each next to an existing test.
8. **Remaining LOWs**: latent realtime-chain items (E1-02, E2-02, E2-03, E3-02, E3-03), low-impact I/O (E4-02, E4-03, E4-05, E4-06) and housekeeping (E6-07, E6-08, E2-07, E5-02). Batch as time allows.

## Known / Existing (confirmed present, not re-filed)

These OPEN issues were re-confirmed by the sub-audits and are not part of the counts above.

#### Dimension 1


- Existing: #6106 (OPEN) — `RealtimeLevelMatcher` per-buffer AGC with per-sample smoother produces ~5 ms bursts on level steps. Still present as described (the E1-02 NaN path above is a separate defect in the same class).
- Existing: #5700 (OPEN) — per-chunk loudness normalisation mixes the fingerprint RMS proxy with the K-weighted meter. The production fixed-target path is a constant track-level gain (verified: seam gain mismatch <= 0.005 dB on real music); the per-chunk fingerprint path still carries the proxy-offset logic noted in `_resolve_parameters`.

#### Dimension 2


- Existing: #6107 (OPEN) — any fingerprint failure (missing wheel, Rust error, sub-22050-sample chunk: `Fingerprint skipped: audio too short`) makes `ContinuousMode._resolve_parameters` return `None` and the chunk comes back unmastered with success status. Reproduced again in the fuzz (all fingerprint-path runs under 22050 samples).
- Existing: #6119 (OPEN) — stereo "width" scales still mixed: `calculate_stereo_width` feeds a fingerprint side-energy ratio into a width-factor target (e.g. a width-0.9 source gets a 0.775 factor, i.e. widened further; a near-mono source is narrowed). Note that on the fixed-target streaming path `convert_targets_to_parameters` pins the factor to `WIDTH_FACTOR_UNITY`, so the stereo stage is a no-op there; the issue's effect is limited to per-chunk fingerprint and whole-file job renders.
- Existing: #6122 (OPEN) — config fields with no reader. Still true for `AdaptiveConfig.chunk_size_ms`, `latency_budget_ms` and `UnifiedConfig.max_length` (validated, never read outside `config/` and tests).
- Existing: #5976 (OPEN) — the fast-start / fixed-targets branches in `AudioProcessingPipeline.apply_enhancement` toggle `content_analyzer.use_fingerprint_analysis`, which the live adaptive path never reads.
- Existing: #6114 (OPEN) — whole-file jobs fingerprint and quality-gate the full decoded buffer (no analysis windows).
- Stale-open candidate: #5700 (OPEN, "per-chunk normalization mixes fingerprint RMS proxy with K-weighted loudness") — the fix is present in `continuous_mode.py` (`proxy_to_k_offset_db`, `_resolve_parameters`) and the fixed-target path compares proxy-vs-proxy; worth re-verifying and closing.
#### Dimension 3

- #6109 (OPEN): the last chunk is zero-padded at the gapless seam, so every auto-advance has up to one chunk of silence. Related to E3-01: this is the other half of why the dormant gapless path is not sample-exact.
- #6106 (OPEN): `RealtimeLevelMatcher` is a per-buffer AGC with a per-sample smoother (alphas not time-based). See E3-04 for the separate sample-rate wiring gap.
- #5708 (OPEN): the production `load_file()` decodes, prebuffers and fingerprints tracks that nothing consumes. The same cost appears on the first `add_to_queue()` (the queue listener starts a prebuffer pass of `tracks[0]`, which is also the track `load_file` is decoding) and in `_auto_select_reference` (a full reference decode per library load).
- #6082 (OPEN): track-changing operations are serialised by four unrelated locks. For example, `previous_track()` moves `current_index` before its blocking `load_file()`. An auto-advance at the same moment peeks from the already-moved index and can leave audio and queue index disagreeing.
- #6085 (OPEN): the `defer_notifications()` contract for lock-held `on_swap` / `on_loaded` hooks relies on caller discipline. I checked every current hook (`seek`, the `position` setter, `next_track._on_swap`, `load_file`, `load_track_from_library`) and all are wrapped correctly.
- #6128 (OPEN): the previous track's fingerprint, adaptive params and DSP state stay active after a track change. The same applies to seek/stop, since nothing resets the compressor, level-matcher or ceiling envelopes.
- #6129 (OPEN): playback state events are dispatched unordered after the lock is released.
- #6286 (OPEN): the `AudioPlayer` backward-compatible property and callback surfaces have no production consumer (the context for E3-05 and E3-07).

#### Dimension 4

- Existing: #5730 - non-canonical multichannel WAV/FLAC (3/4/5/7 ch) re-enter FFmpeg ignoring `cancel_event`/`temp_folder` (`soundfile_loader.py:96-98`; code unchanged).
- Existing: #5734 - FFmpeg decode temp (`auralis_*.wav` in the system temp dir, tmpfs on Linux) is not swept after a hard kill and sits outside the decode budget.
- Existing: #5739 - FFmpeg-format inputs are fully decoded into RAM before the chunked render.
- Existing: #5732 - Vorbis/MP4 multi-valued artist/genre tags are truncated to the first value (confirmed: FLAC `ARTIST=A,B` yields `'A'`).
- Existing: #6180 - FFmpeg version floor is 4.0 and only warns.
- Existing: #5980 - metadata editor has no AIFF branch.

#### Dimension 5

- **#5738 (OPEN)**: Rust `process_chunks` is dead code. Grep confirms the only `process_chunks` callers in `auralis/`, `auralis-web/backend` and `scripts/` are the unrelated Python `mastering_chunk_loop.process_chunks`; no Python caller of the Rust function has appeared.

#### Dimension 6


- Existing: #6112 (OPEN) `spectral_flatness` / `harmonic_ratio` level dependence (absolute `1e-10` per-bin floor). Re-probed on music: flatness 0.0085 at 0 dB, 0.0486 at -30 dB, 0.12 at -40 dB, 0.70 at -60 dB; `harmonic_ratio` mirrors it. It is the only level-dependent dimension of the 23 non-loudness ones.
- Existing: #6113 (OPEN) digital-silence frames inflate the variation dims. Re-confirmed on real audio (`output.flac` body, 1 s zeros: `loudness_variation_std` 2.99 -> 6.65, `dynamic_range_variation` 0.22 -> 0.37; `output_fixed.wav` 0.88 -> 5.68). A 0.5 s gap changes little because the frame still has signal. Synthetic perfectly-steady music also zeroed `rhythm_stability` on any dip of 0.1 s or more of silence (librosa-parity beat trimming), but real masters did not reproduce it, so it is not filed.
- Existing: #6144 (OPEN) non-finite input produces a validator-passing fingerprint; #6107 (OPEN) fingerprint failure or missing wheel becomes a silent mastering bypass (`_analyze_unchecked` returns `{}` on any exception, logged only at ERROR); #6114 (OPEN) whole-file jobs fingerprint the full track (`ContinuousMode._resolve_parameters` calls `analyze()` on the full buffer); #6004 (OPEN) central `.25d` store has no eviction; #5700 (OPEN) proxy vs K-weighted loudness mismatch (the `proxy_to_k_offset_db` mitigation is in place); #6128, #5976, #6119 not touched by this audit.
- Existing: #6273 (OPEN, LOW) analysis files over 300 lines; not re-measured.

#### Dimension 7


- `skip_existing=False` neither updates nor re-adds existing tracks yet reports them as added: **Existing #6146** (OPEN).
- Repository `False`/`0`/`None` sentinels make a failed write indistinguishable from not-found (`remove_track` returns True even when no row matched): **Existing #5264** (OPEN, LOW). Also underlies E7-04's "error looks like empty".
- Multi-valued artist/genre tags truncated to a single value: **Existing #5732** (OPEN).
- ILIKE misses non-ASCII case variants; genre/playlist ordering is BINARY: **Existing #6115** (OPEN).
- Central `.25d` store has no eviction and survives library reset: **Existing #6004** (OPEN).
- Residual of #5698: a track directly inside the root of a persistent, now-empty mount-point directory still reads as "gone" to `cleanup_missing_files` (documented in `_track_file_is_missing`); `relocate_missing_track` deliberately treats a gone parent as missing, so an unmounted volume's rows can be re-pointed to a same-size/duration copy elsewhere. Documented design trade-offs, not filed.
- Observation (docs, not a defect): `TrackRepository.search()` docstring says it searches genre, but the filter covers title, artist and album only.