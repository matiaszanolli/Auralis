# Chunk, Cache & Streaming Architecture (Current)

**Last verified**: 2026-07-09
**Status**: Current — replaces the multi-tier-buffer / MSE / 30s-chunk designs

This is a short, code-verified description of how audio is chunked, cached, and streamed today. Several older docs under `docs/guides/` and `docs/features/cache-system/` describe a 30-second chunk model, an L1/L2/L3 "multi-tier buffer" with branch prediction, and browser MediaSource Extensions (MSE) streaming. **None of that was ever adopted or has since been removed** — those docs are superseded and point here.

## Chunk model — 15 / 10 / 5

The single source of truth is [`auralis-web/backend/core/chunk_boundaries.py`](../../../auralis-web/backend/core/chunk_boundaries.py). Do not hardcode these numbers elsewhere; import them.

| Constant | Value | Meaning |
|---|---|---|
| `CHUNK_DURATION` | **15.0 s** | actual length of each chunk |
| `CHUNK_INTERVAL` | **10.0 s** | playback advance per chunk (`CHUNK_DURATION − OVERLAP_DURATION`) |
| `OVERLAP_DURATION` | **5.0 s** | overlap between adjacent chunks (for equal-power crossfade) |
| `CONTEXT_DURATION` | **5.0 s** | extra context fed to the processor for quality |

So chunk 0 = 0–15 s, chunk 1 = 10–25 s, chunk 2 = 20–35 s, … Each chunk is 15 s long and starts 10 s after the previous one, leaving a 5 s overlap.

**Chunk counting is overlap-aware.** Use `content_chunk_count(total_duration)` from `chunk_boundaries.py` — chunk 0 emits `CHUNK_DURATION` of new audio and every later chunk emits `CHUNK_INTERVAL`. Naïve `ceil(duration / CHUNK_DURATION)` is wrong (see the `content_chunk_count` docstring / #4124). Chunking itself lives in `core/chunked_processor.py` (`ChunkedAudioProcessor`).

## Cache — streamlined, not multi-tier

There is **no** CPU-style L1/L2/L3 hierarchy, no branch prediction, and no fixed `CHUNK_SIZE_MB` tiers. The real pieces:

- **In-memory chunk cache** — `SimpleChunkCache` in [`auralis-web/backend/core/audio_stream_controller.py`](../../../auralis-web/backend/core/audio_stream_controller.py), 512 MB cap.
- **On-disk chunk cache** — `ChunkCacheManager` in [`auralis-web/backend/core/chunk_cache_manager.py`](../../../auralis-web/backend/core/chunk_cache_manager.py): cached WAV/fingerprint chunks under `/tmp/auralis_chunks`, bounded to `MAX_CHUNK_DISK_BYTES` (512 MB) with a global reaper throttled to every `PRUNE_EVERY_N_WRITES` (32) writes (#3834). Cached chunk files are 16-bit PCM WAV, not float32.
- **Cache management/stats API** — `StreamlinedCacheManager` in [`auralis-web/backend/cache/manager.py`](../../../auralis-web/backend/cache/manager.py), exposed via [`auralis-web/backend/routers/cache_streamlined.py`](../../../auralis-web/backend/routers/cache_streamlined.py).

## Streaming — WebSocket binary PCM end-to-end

There is **no** MSE, no `MSEPlayer`, and no `/api/mse/...` route. REST audio-streaming endpoints have been removed entirely — audio is streamed over the WebSocket only.

- **Backend**: `core/audio_stream_controller.py` streams processed chunks as binary PCM frames over the `/ws` WebSocket. The message protocol (`audio_stream_start` → N × `audio_chunk`(+meta) → `audio_stream_end`) is documented in [`auralis-web/backend/WEBSOCKET_API.md`](../../../auralis-web/backend/WEBSOCKET_API.md).
- **Frontend**: binary PCM frames land in [`services/audio/PCMStreamBuffer.ts`](../../../auralis-web/frontend/src/services/audio/PCMStreamBuffer.ts) and play through [`services/audio/AudioPlaybackEngine.ts`](../../../auralis-web/frontend/src/services/audio/AudioPlaybackEngine.ts) (Web Audio API), driven by the `usePlayEnhanced` hook.

## See also

- [`CLAUDE.md`](../../../CLAUDE.md) — the architecture-flow summary matches this doc (15s chunks / 10s interval / 5s overlap).
- `docs/troubleshooting/PRESET_SWITCHING_LIMITATION.md` and `DEBUG_PLAYBACK.md` — historical diagnoses written against the removed REST/MSE path (already superseded-flagged).
