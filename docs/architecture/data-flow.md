# Architecture: Data Flow

Four flows traced through the code, each step naming the symbol where it happens. Paths are
relative to `auralis-web/frontend/src/` (frontend), `auralis-web/backend/` (backend) and the repo
root (`auralis/`). Read [overview.md](overview.md) first for the layer model.

---

## Flow 1: Enhanced playback (the hot path)

A user plays a track with enhancement on.

**Frontend: request**

1. `hooks/player/usePlayTrack.ts::usePlayTrack` sets the queue with `POST /api/player/queue`
   (`ENDPOINTS.QUEUE`), then calls `startTrack` from the single shared session.
2. `contexts/PlaybackSessionContext.tsx::PlaybackSessionProvider` picks the stream type from the
   live enhancement setting: `playEnhanced(trackId, preset, intensity)` when enabled, else
   `playNormal(trackId)` (Flow 2). Both come from `hooks/enhancement/usePlayEnhanced.ts`.
3. `hooks/enhancement/useEnhancedPlayCommand.ts::useEnhancedPlayCommand` resets the buffer and
   Redux streaming state, sends `{ type: 'play_enhanced', data: { track_id, preset, intensity } }`
   over the socket, and loads the track row with `GET /api/library/tracks/{id}` in the background.

**Backend: socket and stream task**

4. `routers/system.py::websocket_endpoint` runs the `/ws` receive loop. On connect,
   `ws_handlers/connection.py::setup_connection` starts the heartbeat and pushes
   `enhancement_settings_changed` and `player_state`. Each frame is validated, rate-limited, and
   routed by `ws_handlers/connection.py::dispatch_message`.
5. `ws_handlers/playback_commands.py::handle_play_enhanced` validates the request, resolves
   preset and intensity (`ws_handlers/enhancement_params.py::resolve_enhancement_params`), records
   them per connection in `StreamState.active_stream_settings`, cancels any prior stream for the
   connection, and starts a task with `ws_handlers/stream_cancel.py::attach_stream`.
6. The task is `routers/system_streams.py::stream_audio`, which builds an `AudioStreamController`
   (`core/audio_stream_controller.py`) and calls `stream_enhanced_audio`, delegating to
   `core/stream_enhanced.py::stream_enhanced_audio`.
7. `core/stream_enhanced_lifecycle.py::run_enhanced_stream` is the shared skeleton for a play and
   a seek: take a stream slot (`core/stream_permit.py::acquire_stream_permit`, bounded by
   `MAX_CONCURRENT_STREAMS`), resolve and validate the track path
   (`core/stream_track_resolution.py`), then construct `ChunkedAudioProcessor` on a worker thread
   with a timeout.

**Backend: the track-level plan**

8. `ChunkedAudioProcessor.__init__` (`core/chunked_processor.py`) reads metadata without decoding
   (`core/chunk_metadata.py`), then `core/chunk_processor_init.py::init_fingerprint_and_processor`
   calls `MasteringTargetService.load_fingerprint` (`core/mastering_target_service.py`): database,
   then `.25d` sidecar, then extraction from the audio. The result is the fingerprint and the
   mastering targets for the whole track.
9. The same function acquires a `HybridProcessor` as an exclusive lease from `ProcessorFactory`
   (`core/processor_factory.py`; `core/processor_registry.py::get_processor_factory` returns one
   factory per consumer). `ProcessorLeaseMixin.acquire` builds the processor with the targets
   installed through `HybridProcessor.set_fixed_mastering_targets`. The stream keeps that one
   instance for its whole life and returns it in `ChunkedAudioProcessor.close`.
10. The stream sends `audio_stream_start` (`core/stream_lifecycle.py::send_stream_start`) carrying
    sample rate, channels, `total_chunks` (from `content_chunk_count`), and the stream type.

**Backend: the chunk loop**

11. `core/stream_enhanced_chunks.py::pump_chunks` hands an enhanced flavour to
    `core/stream_pump.py::run_chunk_pump`. For each chunk it waits on the pause and flow gates
    (`core/stream_gates.py::wait_for_stream_gates`), produces chunk N, starts chunk N+1 as a
    look-ahead task, and sends chunk N.
12. Producing a chunk: `core/stream_chunk_ops.py::process_chunk_only` awaits
    `ChunkedAudioProcessor.process_chunk_safe` under `CHUNK_PROCESS_TIMEOUT`. That runs
    `core/chunk_streaming.py::process_chunk` on the dedicated streaming pool
    (`core/executors.py::run_in_stream_executor`), holding the processor's lock for the chunk.
13. `process_chunk` serves a cached WAV when one exists (`core/chunk_path_cache.py`). On a miss,
    `core/chunk_single_flight.py` ensures one render per cache key across streams, and
    `core/chunk_render_miss.py::render_chunk` renders and caches it.
14. `core/chunk_render.py::process_chunk_core` loads the window with context
    (`core/chunk_file_loading.py::load_chunk_from_file`), calls
    `core/audio_processing_pipeline.py::AudioProcessingPipeline.process_audio` (validate, apply,
    sample-count and finiteness guards, intensity blend), trims the context off, and extracts the
    non-overlapping segment (`core/chunk_segment_extraction.py::extract_chunk_segment`). The
    cached WAV is the raw segment; level smoothing across chunks happens at serve time
    (`chunk_render.smooth_level_transition`, `core/level_manager.py`).
15. The DSP itself: `auralis/core/hybrid_processor.py::HybridProcessor.process` takes its lock,
    validates input, and dispatches (`auralis/core/processing/mode_dispatch.py::process_adaptive_mode`)
    to `auralis/core/processing/continuous_mode.py::ContinuousMode.process`. With fixed targets
    installed it converts them straight to parameters
    (`auralis/core/processing/fixed_target_params.py`) and applies the stage sequence in
    `continuous_stages.py`; it does not fingerprint the chunk. Stage detail:
    [dsp-engine.md](../subsystems/dsp-engine.md).
16. Delivery: `core/stream_protocol.py::send_pcm_chunk` converts to float32 and splits the chunk
    into binary frames of about 300 KB. Each frame is an `audio_chunk_meta` JSON message
    (`seq`, `stream_epoch`, `chunk_index`, `frame_index`, `sample_count`, `stream_type`) followed
    immediately by the raw PCM frame. After the last chunk, `send_stream_completion` sends
    `audio_stream_end`.

**Frontend: receive and play**

17. `hooks/websocket/socketFrameParser.ts::handleSocketFrame` stashes each `audio_chunk_meta`
    (checking `seq` for gaps) and fuses the next binary frame into a synthetic `audio_chunk`
    message with `pcm_binary`.
18. `hooks/enhancement/useStreamSubscriptions.ts` routes `audio_stream_start`, `audio_chunk`,
    `audio_stream_end` and `audio_stream_error` to the handlers. On start,
    `useEnhancedStreamStart.ts` builds the `PCMStreamBuffer` and `AudioPlaybackEngine`.
    `useStreamChunkHandler.ts` calls `audioChunkIngest.ts::ingestChunk`, which decodes with
    `utils/audio/pcmDecoding.ts::decodeAudioChunkMessage` (raw float32) and appends to the ring
    buffer.
19. Flow control: when the ring fills, the handler sends `buffer_full`; the server parks on its
    flow gate until the client sends `buffer_ready`.
20. Once enough is buffered, `services/audio/AudioPlaybackEngine.ts::startPlayback` starts the
    `BufferScheduler`, which feeds an `AudioWorkletNode` (`public/audio-worklet-processor.js`,
    created in `services/audio/WorkletOutput.ts`) through gain and an analyser to the
    AudioContext destination.

**Properties worth knowing**

- DSP never blocks the event loop: renders run on the streaming pool, and a chunk that exceeds its
  timeout ends the stream rather than reusing a processor an orphaned thread may still hold.
- One `HybridProcessor` per stream keeps compressor, EQ and limiter state continuous across chunk
  seams. A second stream of the same track gets its own instance.
- No crossfade at seams: each chunk is rendered with context and trimmed so emitted segments tile
  the timeline. Geometry: `core/chunk_boundaries.py` (`content_chunk_count`,
  `emitted_chunk_start`, `chunk_for_position`).
- Seek: the client sends `seek`; `ws_handlers/seek_command.py::handle_seek` cancels the running
  stream and starts `core/stream_seek.py::stream_enhanced_audio_from_position`, which reuses
  `run_enhanced_stream` and `pump_chunks` from the chunk that contains the target, trimming the
  head of the first chunk.
- On a play, `core/proactive_buffer.py::buffer_presets_for_track` warms the first chunks in the
  background, and `core/stream_fingerprint.py::check_or_queue_fingerprint` queues a fingerprint
  for tracks that have none (Flow 3).

---

## Flow 2: Normal (unenhanced) playback

Same socket, same client pipeline, no DSP.

1. The session sends `{ type: 'play_normal', data: { track_id } }` (`playNormal`, through
   `useEnhancedPlayCommand` with the normal wire type).
2. `ws_handlers/playback_commands.py::handle_play_normal` starts
   `routers/system_streams.py::stream_normal`, which calls
   `core/stream_normal.py::stream_normal_audio`.
3. The stream takes a permit and resolves the path as in Flow 1. A format libsndfile cannot read
   (`auralis/io/formats.py::FFMPEG_FORMATS`) is converted once to a temp WAV through
   `core/converted_wav_registry.py::acquire_conversion`.
4. `core/chunk_boundaries.py::normal_stream_plan` computes the plan. The normal stream has no
   context and no overlap: its stride is the whole chunk (`NORMAL_CHUNK_STRIDE`) and
   `normal_chunk_count` counts them.
5. `audio_stream_start` is sent with `preset: "none"` and stream type `normal`.
   `core/stream_normal_chunks.py::pump_normal_chunks` runs the same `run_chunk_pump` loop with a
   flavour that reads each chunk from disk (`core/stream_normal_reads.py::read_audio_chunk`) with a
   look-ahead read.
6. Delivery and the frontend path are identical to steps 16 to 20. The client tells the two
   streams apart by `stream_type`.

---

## Flow 3: Library scan and background fingerprinting

**Scan**

1. `hooks/library/useLibraryScan.ts` registers the folder in the path allowlist
   (`POST /api/settings/scan-folders`) and posts the scan (`ENDPOINTS.LIBRARY_SCAN`); the
   auto-scanner (`services/library_auto_scanner.py::LibraryAutoScanner`) runs the same
   pipeline from the configured folders at startup, on filesystem events, and on a polling timer.
2. `routers/library_scan.py::scan_library` creates a `LibraryScanner` and runs
   `scan_directories` on a worker thread (`asyncio.to_thread`), waiting through
   `routers/library_scan_lifecycle.py::_await_scan` under `SCAN_TIMEOUT_S`.
3. `auralis/library/scanner/scanner.py::LibraryScanner.scan_directories` claims a scan slot
   (`auralis/library/scan_coordinator.py`), walks the folders (`file_discovery.py`), and feeds
   batches to `batch_processor.py::BatchProcessor`, which extracts metadata and audio facts and
   writes tracks through the repositories.
4. Progress crosses from the scanner thread to the event loop in
   `services/scan_events.py::make_progress_callback` and is broadcast as `library_scan_started`
   and `scan_progress` (`websocket/outbound_messages.py::broadcast_typed`). The frontend side is
   `hooks/library/useScanProgress.ts`.
5. After the scan, `routers/library_scan_events.py::publish_scan_result` enqueues added and
   updated tracks for fingerprinting
   (`services/scan_fingerprint_enqueue.py::enqueue_scanned_for_fingerprinting`), prunes tracks
   whose files are gone (`services/missing_tracks.py`) when every folder was readable, and
   broadcasts `scan_complete` and `library_updated`
   (`services/scan_complete_broadcast.py::broadcast_scan_complete`).

**Fingerprinting** (two cooperating workers; both end in `auralis_dsp.compute_fingerprint`)

- Backlog pool, started in the lifespan (`config/startup/fingerprint.py`):
  `auralis/services/fingerprint_queue.py::FingerprintExtractionQueue` runs worker threads that pull
  from the database. Each claims the next unfingerprinted track, then outdated ones
  (`FINGERPRINT_ALGORITHM_VERSION`), through
  `auralis/library/repositories/fingerprint_scheduler_repository.py::FingerprintSchedulerRepository`,
  which claims atomically with a placeholder row so two workers never take one track.
  `auralis/services/fingerprint_extractor.py::FingerprintExtractor.extract_and_store` uses a valid
  `.25d` sidecar if one exists, otherwise computes the fingerprint, stores it with the fingerprint
  repository, and writes the sidecar. When the workers drain, the callback wired in
  `config/startup/components.py` refreshes the reference cloud
  (`auralis/learning/reference_seeder.py::refresh_cloud`).
- On-demand queue:
  `analysis/fingerprint_queue.py::FingerprintQueue` is a single asyncio worker fed by
  `enqueue(track_id)` from the scan step above, from `core/stream_fingerprint.py` when a stream
  starts without a fingerprint, and from the similarity and fingerprint-queue routers. It calls
  `analysis/fingerprint_generator.py::FingerprintGenerator.get_or_generate`, which returns the
  database row or computes one on a thread pool (`analysis/fingerprint_executor.py`) through
  `auralis/analysis/fingerprint/windowed_compute.py::compute_windowed_fingerprint`.
- The similarity graph is not rebuilt automatically: it is built on request
  (`routers/similarity_graph.py::build_similarity_graph`).

Dimensions, storage and the similarity stack: [fingerprinting.md](../subsystems/fingerprinting.md).
The scanner, repositories and migrations: [library.md](../subsystems/library.md).

---

## Flow 4: REST browse (the common request)

Listing tracks:

1. A component calls `hooks/library/useLibraryQuery.ts::useLibraryQuery('tracks')`. Its fetchers
   (`useLibraryQueryFetchers.ts`, `libraryQueryRequest.ts::fetchLibraryPage`) share a request
   guard and abort controller so a newer request supersedes older ones, and call
   `utils/apiRequest.ts::get`, the app's only HTTP transport (timeout, abort and error
   normalisation live there).
2. The request is `GET /api/library/tracks` (`ENDPOINTS.LIBRARY_TRACKS`).
3. Middleware, outermost first (`config/middleware/__init__.py::setup_middleware`): CORS, security
   headers, no-cache, origin check, trusted host, rate limit, unhandled-exception.
4. `routers/tracks.py::get_tracks` runs. The router was created by
   `config/routes.py::setup_routers` with `get_component('repository_factory')` and binds it per
   request through `routers/repo_deps.py::RepositoryFactoryDeps.get_repos` (503 if the factory is
   not up).
5. `asyncio.to_thread(repos.tracks.get_all, ...)` (or `repos.tracks.search` when `search` is
   set) runs the query off the event loop through `TrackRepository`, with relationships
   eager-loaded.
6. `routers/serializers_library.py::serialize_tracks` and `routers/pagination.py::paginated` shape
   the body for `TrackListResponse`.
7. The hook stores the page in component state; `fetchMore` continues from the offset.
   TanStack Query backs the hooks that use it (`useInfiniteAlbums`, fingerprint and cache-stats
   hooks); `useLibraryQuery` does not.

Mutations (play, enqueue, favourite, rename a playlist, scan) also broadcast over the socket with
`websocket/outbound_messages.py::broadcast_typed`, which calls
`websocket/connection_manager.py::ConnectionManager.broadcast`, so every connected renderer
updates.

---

## State sync

| Direction | Mechanism | Examples |
|-----------|-----------|----------|
| Client to server | REST calls and WebSocket commands | `play_enhanced`, `seek`, `POST /api/playlists` |
| Server to client | WebSocket broadcasts | `player_state`, `position_changed`, `scan_progress`, `library_updated` |

The backend is authoritative for playback and queue state:
`core/state_manager.py::PlayerStateManager` broadcasts `player_state` snapshots, and the server
pushes one on every connect and reconnect (`setup_connection`). The frontend applies them in
`hooks/player/usePlayerStateSync.ts`. The renderer may update optimistically for responsiveness but
reconciles to the snapshot. Message definitions:
[WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md).

---

## Related

- [overview.md](overview.md): layers, design rules, invariants
- [module-map.md](module-map.md): where each step lives on disk
- [Player](../subsystems/player.md) and [Library](../subsystems/library.md) subsystems
- The `trace-flow` skill traces any other action
