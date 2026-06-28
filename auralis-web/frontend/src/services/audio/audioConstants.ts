/**
 * AudioPlaybackEngine tuning constants (#4031).
 *
 * Previously these were bare literals scattered through AudioPlaybackEngine.ts
 * with their relationships only hinted at in comments. Centralised here so the
 * buffer geometry and its dependence on the backend chunk cadence are explicit.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

export const PLAYBACK_ENGINE_CONFIG = {
  /** AnalyserNode FFT size for the visualization tap. */
  fftSize: 2048,
  /** AnalyserNode smoothing for the visualization tap. */
  smoothingTimeConstant: 0.8,
  /** Samples per ScriptProcessor/worklet feed callback (interleaved per channel). */
  bufferSize: 4096,
  /** Minimum buffered samples before playback starts (~1 s at 48 kHz stereo). */
  minBufferSamples: 96000,
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
} as const;
