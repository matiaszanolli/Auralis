# Chunk, Cache and Streaming Architecture

How audio is chunked, rendered, cached and streamed. This document owns the chunk geometry, the
cache keys and the invalidation rules. The orchestration around them (stream lifecycle, processor
leases, startup and shutdown) is in [backend-api.md](../../subsystems/backend-api.md); the wire
messages are in [WEBSOCKET_API.md](../../../auralis-web/backend/WEBSOCKET_API.md).

## Chunk model: 15 / 10 / 5

The single source of truth is
[`auralis-web/backend/core/chunk_boundaries.py`](../../../auralis-web/backend/core/chunk_boundaries.py).
Import the constants; never restate the numbers in code.

| Constant | Value | Meaning |
|---|---|---|
| `CHUNK_DURATION` | 15.0 s | length of each rendered chunk window |
| `OVERLAP_DURATION` | 5.0 s | audio a chunk window shares with its predecessor |
| `CHUNK_INTERVAL` | 10.0 s | derived: `CHUNK_DURATION - OVERLAP_DURATION`, the start-to-start stride |
| `CONTEXT_DURATION` | 5.0 s | extra audio loaded on each side of a window so the DSP has lead-in and tail |

Chunk `i` renders the window `[10i, 10i + 15)` s, loaded with up to 5 s of context on each side
(clamped to the track) and trimmed back off after DSP. Emitted audio then skips the 5 s the
previous chunk already covered, so the delivered segments tile the timeline exactly with no
crossfade:

| Chunk | Emits | Length |
|---|---|---|
| 0 | `[0, 15)` | 15 s (`CHUNK_DURATION`) |
| 1 | `[15, 25)` | 10 s (`CHUNK_INTERVAL`) |
| i >= 1 | `[10i + 5, 10i + 15)` | 10 s |

`emitted_chunk_start(i)` and `emitted_chunk_length(i)` give these numbers, and
`chunk_for_position(position, total_chunks, ...)` maps a seek position onto the chunk that emits
it (a position within 0.5 s of its chunk's end advances to the next chunk, and one at or past the
track end is clamped back so audible audio remains). `ChunkBoundaryManager`
(`core/chunk_boundary_manager.py`) derives load windows and context trims from the same constants.

**Chunk counting is overlap-aware.** `content_chunk_count(total_duration)` is the only counter
for the enhanced and seek streams: `max(1, ceil((duration - OVERLAP_DURATION) / CHUNK_INTERVAL))`.
`ceil(duration / CHUNK_DURATION)` is wrong. Its one twin is `normal_chunk_count(total_frames,
sample_rate)` for the normal (unprocessed) stream, which reads 15 s chunks back to back with no
context and no overlap (`NORMAL_CHUNK_STRIDE`, `normal_stream_plan`).

A chunk that cannot be loaded or rendered is replaced by `FALLBACK_SILENCE_SECONDS` (0.1 s) of
silence, and the render path marks it so it is never cached as a real render.

## Rendering

`ChunkedAudioProcessor` (`core/chunked_processor.py`) is one stream's renderer: it loads a chunk
window with context from a `SeekableSource`, runs the leased `HybridProcessor` through
`AudioProcessingPipeline`, smooths level across the boundary (`level_manager.py`), trims to the
emitted segment (`chunk_segment_extraction.py`) and writes it to the on-disk cache. The
`chunk_*` modules are its collaborators; `chunk_streaming.py` holds the entry points
(`process_chunk`, `process_chunk_safe`, `get_wav_chunk_path`).

- Analysis is whole-track, rendering is per chunk: the fingerprint and mastering targets are
  resolved once per track (`core/mastering_target_service.py`), and chunks only render against that
  plan.
- A source libsndfile cannot seek (m4a, aac, wma, or an MP3 without a usable header) is converted
  once to a temp WAV shared by every holder of the file (`core/seekable_source.py`,
  `converted_wav_registry.py`).
- Single flight: one DSP render per chunk cache key across all streams
  (`core/chunk_single_flight.py`).
- Enhanced streaming pre-warms the first 3 chunks (the first 35 s) of the track so a first play or a toggle back to
  enhanced starts from cache (`core/proactive_buffer.py`).

## Cache tiers

Three layers, all referring to the same files on disk.

| Layer | Class | Holds | Bound |
|---|---|---|---|
| On-disk chunk files | `ChunkCacheManager` (`core/chunk_cache_manager.py`) with `ChunkPathCache` (`core/chunk_path_cache.py`) | the durable WAVs; a lookup checks an in-memory path map, then `Path.exists()` plus `is_wav_complete()` on the file name | 512 MB (`MAX_CHUNK_DISK_BYTES`) |
| Tier 1 (hot) | `StreamlinedCacheManager` (`cache/manager.py`) | the current and next processed chunk, for instant playback and toggle | `TIER1_MAX_CHUNKS` = 2 (about 5 MB at 44.1 kHz stereo) |
| Tier 2 (warm) | `StreamlinedCacheManager` | the whole track, for instant seeks and back-navigation | `TIER2_MAX_SIZE_MB` = 240, measured from real file sizes |

Tier 1 and Tier 2 store paths to chunk WAVs, not audio. Tier 2 eviction is size-driven only: it
drops the least recently used whole non-current track, and falls back to least-recently-used
chunks of the current track when it is the only one present. Only processed chunks are built;
originals are never prebuilt.

`StreamlinedCacheWorker` (`core/streamlined_worker.py`, `streamlined_tiers.py`) renders ahead in the
background once a second against a consistent playback snapshot: the next chunk (Tier 1), then the
rest of the track (Tier 2), then the previous track. It uses its own small processor cache and
render leases (`streamlined_processor_cache.py`, `streamlined_processor_disposal.py`).

The cache is also exposed through the `/api/cache` routes (`routers/cache_streamlined.py`): stats,
per-track status, per-track clear, clear all, health.

## Cache file format and keys

Cached chunks are **16-bit PCM WAV** (`PCM_16`), not the float32 sent on the WebSocket. Files are
written to a staging name and atomically replaced into place (`core/encoding/atomic_io.py`), so a
reader never sees a half-written chunk; `is_wav_complete` rejects a truncated file.

Chunk file name (`WAVEncoder.get_chunk_path`, `core/encoding/wav_encoder.py`):

```
v{CACHE_VERSION}_track_{track_id}_{file_signature}_{preset}_{intensity}_{targets_hash}_chunk_{index}.wav
```

The in-memory key is the same fields without the `v{N}_track_` prefix and `.wav`
(`ChunkCacheManager.get_chunk_cache_key`); one key format is shared by every caller so a hit
recorded by one is visible to the others. Components:

| Field | Source | Effect |
|---|---|---|
| `CACHE_VERSION` (currently 5) | `WAVEncoder.CACHE_VERSION` | bump to orphan every chunk when rendering changes |
| `file_signature` | `FileSignatureService.generate`: 8 hex chars from mtime, size, path and the first and last 64 KiB | an edited or replaced source gets new keys |
| `preset` | `adaptive` is the only preset | |
| `intensity` | `intensity_cache_key`: rounded to 0.1 | nearby values share a chunk |
| `targets_hash` | `get_targets_hash`: MD5 of the mastering targets, `none` when absent | chunks rendered with different targets never mix |

The Tier 1 and Tier 2 index uses `CachedChunk.make_key`:
`{track_id}_{preset or original}_{intensity}_{chunk_idx}_{file_signature}`.

## Invalidation and clearing

- **Source changed**: a new file signature yields new keys; old files age out through the reaper.
- **Rendering changed**: bump `CACHE_VERSION`.
- **Disk cap**: `ChunkDiskPruneMixin` (`core/chunk_disk_prune.py`) deletes the oldest files by
  mtime until the directory is under the cap. It runs once per 32 cache writes
  (`PRUNE_EVERY_N_WRITES`), process-wide and single-scan, and deleting a file another stream still
  references is safe: that stream sees a miss and re-renders.
- **User clear** (`/api/cache/clear`, `DELETE /api/cache/track/{id}`, library reset):
  `core/cache_cleanup.py::clear_track_caches` / `clear_all_caches` clear the tier indexes, delete the
  chunk files from the directory (whoever wrote them), and drop warm processors and the track's
  mastering-target entry. `clear_all_caches` also clears thumbnails and sweeps dead fingerprint-store
  entries. Clearing sweeps the directory even when the cache manager is absent.
- **Startup**: the chunk directory is wiped on every start, unless another live backend process owns
  it (an owner marker file), in which case only stale partial writes are removed
  (`config/startup/tempfiles.py::_cleanup_temp_directories`). Leftover decode and stream temp WAVs
  from dead processes are reclaimed too.
- **Location**: `auralis_chunks` under the system temp directory, created owner-only
  (`config/limits.py::chunk_cache_dir`).

## Streaming: WebSocket binary PCM end to end

There is no MSE and no REST audio route. `AudioStreamController`
(`core/audio_stream_controller.py`) streams chunks as float32 PCM frames over `/ws`: sequence
`audio_stream_start`, then N pairs of `audio_chunk_meta` (JSON) and a binary frame, then
`audio_stream_end`. The enhanced stream renders the next chunk while sending the current one
(look-ahead) and honors pause and `buffer_full` / `buffer_ready` flow control; a seek restarts the
stream from `chunk_for_position`. Full protocol: WEBSOCKET_API.md.

The frontend feeds binary frames into
[`PCMStreamBuffer.ts`](../../../auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts) and plays
them through
[`AudioPlaybackEngine.ts`](../../../auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts)
(Web Audio API), driven by the `usePlayEnhanced` hook.
