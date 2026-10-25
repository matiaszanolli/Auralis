/**
 * AudioPlaybackEngine tuning constants (#4031).
 *
 * Previously these were bare literals scattered through AudioPlaybackEngine.ts
 * with their relationships only hinted at in comments. Centralised here so the
 * buffer geometry and its dependence on the backend chunk cadence are explicit.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

export const PLAYBACK_ENGINE_CONFIG = {
  /** AnalyserNode FFT size for the visualization tap. */
  fftSize: 2048,
  /** AnalyserNode smoothing for the visualization tap. */
  smoothingTimeConstant: 0.8,
  /** Samples per ScriptProcessor/worklet feed callback (interleaved per channel). */
  bufferSize: 4096,
  /**
   * Minimum buffered audio before playback starts, in SECONDS of stream
   * time (#6232). The old raw interleaved count (96000) was calibrated for
   * 48 kHz stereo: 0.5 s at 96 kHz stereo, 2.2 s at 44.1 kHz mono.
   * BufferScheduler converts to samples with the stream's own
   * sampleRate*channels.
   */
  minBufferSeconds: 1.0,
  /**
   * Pause threshold: when the buffer drops below this, playback pauses to let it
   * refill. Must stay BELOW the backend chunk interval (CHUNK_INTERVAL = 10 s)
   * so a single late chunk doesn't trigger an avoidable pause.
   */
  lowWaterMarkSeconds: 5.0,
  /** Resume threshold: playback resumes once the buffer rises above this. */
  highWaterMarkSeconds: 8.0,
  /** Polling interval (ms) for the buffer feed loop. */
  feedIntervalMs: 50,
  /**
   * How much audio the feeder keeps queued inside the AudioWorklet. The worklet
   * queue has no bound of its own, so the main thread tops it up to this level
   * instead of pushing faster than real time (#5657). Must stay well below
   * lowWaterMarkSeconds, which is measured over ring + worklet queue.
   */
  workletLookaheadSeconds: 3.0,
  /** Frames sent to the worklet per feed tick at most (4 process blocks). */
  maxFeedFramesPerTick: 16384,
} as const;

/**
 * Backend chunk timing the frontend constants depend on (#6232). These are
 * MIRRORS of auralis-web/backend values — named here so the dependency is
 * visible and greppable, and so the derived values below explain themselves.
 * When the backend changes one, update the mirror here in the same commit.
 *  - CHUNK_INTERVAL: seconds between chunk sends (backend CHUNK_INTERVAL).
 *  - CHUNK_PROCESS_TIMEOUT_S: worst-case per-chunk processing budget.
 *  - STREAM_SEMAPHORE_WAIT_S: the stream-start semaphore wait on top of it.
 */
export const BACKEND_STREAM_TIMING = {
  chunkIntervalSeconds: 10,
  chunkProcessTimeoutSeconds: 30,
  streamSemaphoreWaitSeconds: 5,
} as const;

/**
 * Stream-start watchdog budget (#4433, #6232): must exceed one full chunk
 * cycle — the backend may spend CHUNK_PROCESS_TIMEOUT processing the first
 * chunk plus the semaphore wait — with margin for the interval itself.
 */
export const STREAM_START_WATCHDOG_DERIVED_MS =
  (BACKEND_STREAM_TIMING.chunkProcessTimeoutSeconds
    + BACKEND_STREAM_TIMING.streamSemaphoreWaitSeconds
    + BACKEND_STREAM_TIMING.chunkIntervalSeconds) * 1000;

/**
 * Fallback sample rate for metadata-less calls (#6232): one named default
 * shared by BufferScheduler, WorkletOutput and PCMStreamBuffer instead of
 * three hand-typed values (44100, 44100, 48000).
 */
export const DEFAULT_STREAM_SAMPLE_RATE = 44100;
