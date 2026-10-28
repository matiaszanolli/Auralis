import { PLAYBACK_ENGINE_CONFIG } from './audioConstants';

/**
 * Create or get a shared AnalyserNode for visualization
 * Stores in global for useAudioVisualization hook to access
 */
export function createGlobalAnalyser(audioContext: AudioContext): AnalyserNode {
  const existing = window.__auralisAnalyser;
  // Reuse only when the cached node belongs to the same, non-closed context.
  // When usePlayEnhanced replaces an AudioContext (e.g. sample-rate change), the
  // stale analyser belongs to the closed old context; connecting a gainNode from
  // the new context to it throws DOMException: InvalidStateError (fixes #2488).
  if (existing && existing.context === audioContext && audioContext.state !== 'closed') {
    return existing;
  }

  const analyser = audioContext.createAnalyser();
  analyser.fftSize = PLAYBACK_ENGINE_CONFIG.fftSize;
  analyser.smoothingTimeConstant = PLAYBACK_ENGINE_CONFIG.smoothingTimeConstant;
  window.__auralisAnalyser = analyser;

  return analyser;
}
