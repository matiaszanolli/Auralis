/**
 * usePlayEnhanced Hook
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Manages WebSocket-based PCM audio streaming for enhanced audio playback.
 * Integrates PCMStreamBuffer, AudioPlaybackEngine, and Redux state management.
 * Same architecture as usePlayNormal — both compose the shared
 * `useAudioStreamingCore` (fixes #4019).
 *
 * This hook is a thin composition (#4077) over four focused sub-hooks:
 * - useAudioStreamingCore     — shared buffer/engine/chunk plumbing
 * - useFingerprintStatus      — fingerprint-analysis status state machine
 * - useEnhancedStreamStart    — the audio_stream_start (re)initialisation handler
 * - useEnhancedSeek           — seekTo + seek acknowledgement
 * - useEnhancedPlayCommand    — the playEnhanced command
 *
 * Usage:
 * ```typescript
 * const { playEnhanced, stopPlayback, pausePlayback, resumePlayback,
 *   isStreaming, streamingProgress, bufferedSamples, error } = usePlayEnhanced();
 *
 * await playEnhanced(trackId, 'adaptive', 1.0);
 * pausePlayback();
 * resumePlayback();
 * stopPlayback();
 * ```
 *
 * @module hooks/enhancement/usePlayEnhanced
 */

import { useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch } from '@/store';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import {
  resetStreaming,
  selectEnhancedStreaming,
} from '@/store/slices/playerSlice';
import type { EnhancementPreset } from '@/types/domain';
import { useAudioStreamingCore } from './useAudioStreamingCore';
import { useFingerprintStatus, type FingerprintStatus } from './useFingerprintStatus';
import { useEnhancedStreamStart, type CurrentTrackInfo } from './useEnhancedStreamStart';
import { useEnhancedSeek } from './useEnhancedSeek';
import { useEnhancedPlayCommand } from './useEnhancedPlayCommand';

/**
 * Return type for usePlayEnhanced hook
 */
export interface UsePlayEnhancedReturn {
  /**
   * Start enhanced audio playback for a track
   * @param trackId ID of track to play
   * @param preset Enhancement preset (adaptive, gentle, warm, bright, punchy)
   * @param intensity Enhancement intensity (0.0-1.0)
   */
  playEnhanced: (trackId: number, preset: EnhancementPreset, intensity: number) => Promise<void>;

  /** Seek to a specific position (seconds) in the current track. */
  seekTo: (position: number) => void;

  /** Stop playback completely. */
  stopPlayback: () => void;

  /** Pause playback (can be resumed). */
  pausePlayback: () => void;

  /** Resume from pause. */
  resumePlayback: () => void;

  /** Set playback volume (0-1). */
  setVolume: (volume: number) => void;

  /** Whether currently streaming. */
  isStreaming: boolean;

  /** Streaming state (idle, buffering, streaming, error, complete). */
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';

  /** Streaming progress 0-100. */
  streamingProgress: number;

  /** Number of buffered samples. */
  bufferedSamples: number;

  /** Number of chunks processed. */
  processedChunks: number;

  /** Total number of chunks. */
  totalChunks: number;

  /** Error message if streaming failed. */
  error: string | null;

  /** Current playback time in seconds. */
  currentTime: number;

  /** Whether playback is currently paused. */
  isPaused: boolean;

  /** Whether currently seeking. */
  isSeeking: boolean;

  /**
   * Fingerprint analysis status (idle, analyzing, complete, failed, error,
   * cached, queued). Shows user feedback during the audio analysis phase.
   */
  fingerprintStatus: FingerprintStatus;

  /** Fingerprint analysis message for user display. */
  fingerprintMessage: string | null;
}

export const usePlayEnhanced = (): UsePlayEnhancedReturn => {
  const dispatch = useDispatch<AppDispatch>();
  const wsContext = useWebSocketContext();
  const streamingState = useSelector(selectEnhancedStreaming);

  // Seeking flag lives here (not in useEnhancedSeek) because the streaming
  // core's cleanup callback below also needs to clear it (#2873).
  const [isSeeking, setIsSeeking] = useState(false);

  // Current track info for seek operations — shared by the play/seek/stream-start
  // sub-hooks.
  const currentTrackInfoRef = useRef<CurrentTrackInfo | null>(null);

  // Fingerprint status machine (owns its own fingerprint_progress subscription).
  // Created before the core so the core can cancel its auto-clear timer on
  // disconnect (#2536).
  const fingerprint = useFingerprintStatus(wsContext);

  const core = useAudioStreamingCore(wsContext, {
    streamType: 'enhanced',
    sendType: 'play_enhanced',
    logPrefix: '[usePlayEnhanced]',
    // Auto-start once the engine's own minimum is satisfied — avoids the engine
    // entering 'error' state when a fixed threshold undershoots it (#2478).
    getStartThreshold: (_metadata, engine) => engine.getMinBufferSamples(),
    throttleProgress: true,
    detectOutOfSequence: true,
    closeContextOnCleanup: false,
    onCleanupExtra: () => {
      // Ensure isSeeking doesn't stick if cleanup runs mid-seek (#2873)
      setIsSeeking(false);
    },
    onDisconnectExtra: () => {
      // Cancel orphaned fingerprint timeout so a stale callback cannot fire
      // against the next stream context after disconnect (fixes #2536).
      fingerprint.cancelFingerprintTimeout();
    },
  });

  // Register the enhanced audio_stream_start handler on the core.
  useEnhancedStreamStart({ core, dispatch, currentTrackInfoRef, setIsSeeking });

  const { seekTo } = useEnhancedSeek({ wsContext, core, currentTrackInfoRef, setIsSeeking });

  const playEnhanced = useEnhancedPlayCommand({
    wsContext,
    dispatch,
    core,
    currentTrackInfoRef,
    resetFingerprint: fingerprint.resetFingerprint,
  });

  /**
   * Reset Redux streaming state on MOUNT to clear any stale state left by a
   * previous instance (prevents phantom progress bar on remount — #2533), and
   * dispose the engine/buffer/context on unmount. Subscriptions are owned by the
   * sub-hooks and the shared core, so nothing to unsubscribe here.
   */
  useEffect(() => {
    dispatch(resetStreaming('enhanced'));
    return () => {
      // Fully dispose the engine (disconnects the gainNode too, not just the
      // processor) before closing the context (#4445).
      core.playbackEngineRef.current?.dispose();
      core.playbackEngineRef.current = null;
      // Release the ~100 MB PCM buffer on unmount — cleanupStreaming is not
      // called here (it would setState on a dead component), so dispose the
      // buffer directly instead of leaving it for GC (#4147).
      core.pcmBufferRef.current?.dispose();
      core.pcmBufferRef.current = null;
      // Close AudioContext to release browser audio resources (fixes #2294)
      core.audioContextRef.current?.close();
      core.audioContextRef.current = null;
      dispatch(resetStreaming('enhanced'));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch]);

  return {
    playEnhanced,
    seekTo,
    stopPlayback: core.stopPlayback,
    pausePlayback: core.pausePlayback,
    resumePlayback: core.resumePlayback,
    setVolume: core.setVolume,
    isStreaming: streamingState.state === 'streaming' || streamingState.state === 'buffering',
    streamingState: streamingState.state,
    streamingProgress: streamingState.progress,
    bufferedSamples: streamingState.bufferedSamples,
    processedChunks: streamingState.processedChunks,
    totalChunks: streamingState.totalChunks,
    error: streamingState.error,
    currentTime: core.currentTime,
    isPaused: core.isPaused,
    isSeeking,
    fingerprintStatus: fingerprint.fingerprintStatus,
    fingerprintMessage: fingerprint.fingerprintMessage,
  };
};
