/**
 * usePlayEnhanced Hook
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Manages WebSocket-based PCM audio streaming for enhanced audio playback.
 * Integrates PCMStreamBuffer, AudioPlaybackEngine, and Redux state management.
 * Same architecture as usePlayNormal — both compose the shared
 * `useAudioStreamingCore` (fixes #4019).
 *
 * Usage:
 * ```typescript
 * const {
 *   playEnhanced,
 *   stopPlayback,
 *   pausePlayback,
 *   resumePlayback,
 *   isStreaming,
 *   streamingProgress,
 *   bufferedSamples,
 *   error
 * } = usePlayEnhanced();
 *
 * // Start enhanced playback
 * await playEnhanced(trackId, 'adaptive', 1.0);
 *
 * // Control playback
 * pausePlayback();
 * resumePlayback();
 * stopPlayback();
 * ```
 *
 * Features:
 * - Real-time PCM streaming via WebSocket
 * - Circular buffer management (5MB capacity)
 * - Web Audio API playback with gain control
 * - Pause/resume functionality
 * - Buffer underrun detection
 * - Comprehensive error handling
 * - Redux state synchronization
 * - Automatic cleanup on unmount
 *
 * @module hooks/enhancement/usePlayEnhanced
 */

const DEBUG = import.meta.env.DEV;

import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch } from '@/store';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type { FingerprintProgressMessage } from '@/types/websocket';
import { getApiUrl } from '@/config/api';
import PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import {
  startStreaming,
  setStreamingError,
  resetStreaming,
  selectEnhancedStreaming,
  setCurrentTrackAndSyncQueue,
} from '@/store/slices/playerSlice';
import {
  decodeAudioChunkMessage,
} from '@/utils/audio/pcmDecoding';
import type {
  AudioStreamStartMessage,
} from '@/contexts/WebSocketContext';
import type { EnhancementPreset } from '@/types/domain';
import { useAudioStreamingCore } from './useAudioStreamingCore';

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

  /**
   * Seek to a specific position in the current track
   * @param position Position in seconds to seek to
   */
  seekTo: (position: number) => void;

  /**
   * Stop playback completely
   */
  stopPlayback: () => void;

  /**
   * Pause playback (can be resumed)
   */
  pausePlayback: () => void;

  /**
   * Resume from pause
   */
  resumePlayback: () => void;

  /**
   * Set playback volume (0-1)
   */
  setVolume: (volume: number) => void;

  /**
   * Whether currently streaming
   */
  isStreaming: boolean;

  /**
   * Streaming state (idle, buffering, streaming, error, complete)
   */
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';

  /**
   * Streaming progress 0-100
   */
  streamingProgress: number;

  /**
   * Number of buffered samples
   */
  bufferedSamples: number;

  /**
   * Number of chunks processed
   */
  processedChunks: number;

  /**
   * Total number of chunks
   */
  totalChunks: number;

  /**
   * Error message if streaming failed
   */
  error: string | null;

  /**
   * Current playback time in seconds
   */
  currentTime: number;

  /**
   * Whether playback is currently paused
   */
  isPaused: boolean;

  /**
   * Whether currently seeking
   */
  isSeeking: boolean;

  /**
   * Fingerprint analysis status (idle, analyzing, complete, failed, error)
   * Shows user feedback during audio analysis phase
   */
  fingerprintStatus: 'idle' | 'analyzing' | 'complete' | 'failed' | 'error' | 'cached' | 'queued';

  /**
   * Fingerprint analysis message for user display
   */
  fingerprintMessage: string | null;
}

export const usePlayEnhanced = (): UsePlayEnhancedReturn => {
  const dispatch = useDispatch<AppDispatch>();
  const wsContext = useWebSocketContext();
  const streamingState = useSelector(selectEnhancedStreaming);

  // Subscription cleanup refs for the two events not owned by the shared core
  // (fingerprint_progress, seek_started).
  const unsubscribeFingerprintRef = useRef<(() => void) | null>(null);
  const unsubscribeSeekStartedRef = useRef<(() => void) | null>(null);
  const handleFingerprintProgressRef = useRef<((m: FingerprintProgressMessage) => void) | null>(null);

  // Timer ref for fingerprint status auto-clear (fixes #2353)
  const fingerprintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // State for UI
  const [isSeeking, setIsSeeking] = useState(false);
  const [fingerprintStatus, setFingerprintStatus] = useState<'idle' | 'analyzing' | 'complete' | 'failed' | 'error' | 'cached' | 'queued'>('idle');
  const [fingerprintMessage, setFingerprintMessage] = useState<string | null>(null);

  // Current track info for seek operations
  const currentTrackInfoRef = useRef<{
    trackId: number;
    preset: string;
    intensity: number;
  } | null>(null);

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
      // Cancel orphaned fingerprint timeout so stale callback cannot fire against
      // the next stream context after disconnect (fixes #2536).
      if (fingerprintTimeoutRef.current !== null) {
        clearTimeout(fingerprintTimeoutRef.current);
        fingerprintTimeoutRef.current = null;
      }
    },
  });

  /**
   * Handle audio_stream_start message from backend
   */
  const handleStreamStart = useCallback((message: AudioStreamStartMessage) => {
    try {
      // Only process messages intended for this hook (#2104)
      if (message.data.stream_type && message.data.stream_type !== 'enhanced') return;

      // Check if this is a seek operation
      const isSeek = message.data.is_seek === true;
      const seekPosition = message.data.seek_position || 0;

      DEBUG && console.log('[usePlayEnhanced] Stream started:', {
        trackId: message.data.track_id,
        chunks: message.data.total_chunks,
        duration: message.data.total_duration,
        isSeek,
        seekPosition: isSeek ? seekPosition : undefined,
      });

      // If this is a seek, clear the seeking flag
      if (isSeek) {
        setIsSeeking(false);
      }

      // Resume guard: if we already have a live engine+buffer (e.g. after WS
      // reconnect), skip recreation and let new chunks append seamlessly (#3185).
      if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) {
        DEBUG && console.log('[usePlayEnhanced] Resuming stream into existing buffer');
        if (core.streamingMetadataRef.current) {
          core.streamingMetadataRef.current.totalChunks = message.data.total_chunks;
          core.streamingMetadataRef.current.processedChunks = 0;
        }
        core.pendingChunksRef.current = [];
        dispatch(startStreaming({
          streamType: 'enhanced',
          trackId: message.data.track_id,
          totalChunks: message.data.total_chunks,
          intensity: 1.0,
        }));
        return;
      }

      // Initialize PCMStreamBuffer. Dispose any prior buffer first so replacing
      // the ref never strands a ~100 MB Float32Array for GC (#4147).
      core.pcmBufferRef.current?.dispose();
      const buffer = new PCMStreamBuffer();
      buffer.initialize(message.data.sample_rate, message.data.channels);
      core.pcmBufferRef.current = buffer;

      // Create AudioContext with the SAME sample rate as the streaming audio
      // This is critical - if AudioContext runs at 48000Hz but audio is 44100Hz,
      // playback will be ~9% faster and we'll have buffer underruns.
      const sourceSampleRate = message.data.sample_rate;
      if (!core.audioContextRef.current || core.audioContextRef.current.sampleRate !== sourceSampleRate) {
        // Close existing context if sample rate differs
        if (core.audioContextRef.current) {
          DEBUG && console.log('[usePlayEnhanced] Closing AudioContext (sample rate mismatch)',
            core.audioContextRef.current.sampleRate, '→', sourceSampleRate);
          core.audioContextRef.current.close();
        }
        // Create new AudioContext with matching sample rate
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        core.audioContextRef.current = new AudioContextClass({ sampleRate: sourceSampleRate });
        DEBUG && console.log('[usePlayEnhanced] Created AudioContext with sample rate:', sourceSampleRate);
      }

      // Dispose the previous engine's permanently-wired gainNode before
      // replacing the ref. In enhanced mode the AudioContext persists across
      // track switches (closeContextOnCleanup: false), so a stranded gainNode
      // would stay connected to the analyser for the whole session (#4445).
      core.playbackEngineRef.current?.dispose();

      // Initialize AudioPlaybackEngine
      const engine = new AudioPlaybackEngine(
        core.audioContextRef.current,
        buffer
      );
      core.playbackEngineRef.current = engine;

      // When streaming resumes from a seek position, tell the engine where to
      // start its time counter so the UI shows the correct position instead of
      // always starting from 0:00 (fixes #2259).
      if (isSeek && seekPosition > 0) {
        engine.setSeekOffset(seekPosition);
      }

      // Register state change callback
      engine.onStateChanged((state) => {
        if (state === 'paused') {
          core.setIsPaused(true);
        } else if (state === 'playing') {
          core.setIsPaused(false);
        }
      });

      // Register underrun callback
      engine.onUnderrun(() => {
        DEBUG && console.warn('[usePlayEnhanced] Buffer underrun detected');
      });

      // Store metadata
      core.streamingMetadataRef.current = {
        sampleRate: message.data.sample_rate,
        channels: message.data.channels,
        totalChunks: message.data.total_chunks,
        processedChunks: 0,
      };

      // Reset chunk tracking for new stream
      core.lastReceivedChunkIndexRef.current = -1;
      core.lastDispatchedProgressRef.current = -1; // Reset progress throttle (fixes #2535)
      core.flowPausedRef.current = false; // Reset flow control for new stream

      // Update Redux state
      dispatch(
        startStreaming({
          streamType: 'enhanced',
          trackId: message.data.track_id,
          totalChunks: message.data.total_chunks,
          intensity: currentTrackInfoRef.current?.intensity ?? 1.0,
        })
      );

      // Process any chunks that arrived before stream_start (race condition handling)
      if (core.pendingChunksRef.current.length > 0) {
        DEBUG && console.log('[usePlayEnhanced] Processing queued chunks:', core.pendingChunksRef.current.length);
        const queuedChunks = [...core.pendingChunksRef.current];
        core.pendingChunksRef.current = []; // Clear queue before processing

        for (const queuedMessage of queuedChunks) {
          try {
            const { samples, metadata } = decodeAudioChunkMessage(
              queuedMessage,
              message.data.sample_rate,
              message.data.channels
            );
            buffer.append(samples, metadata.crossfadeSamples);
            core.streamingMetadataRef.current!.processedChunks++;
          } catch (queuedError) {
            console.error('[usePlayEnhanced] Error processing queued chunk:', queuedError);
          }
        }
      }

      // Start playback immediately when stream begins only if the engine's own
      // minimum is already satisfied — avoids the engine entering 'error' state
      // when hook threshold (2 s) was below engine threshold (240 000 samples, fixes #2478).
      if (buffer.getAvailableSamples() >= engine.getMinBufferSamples()) {
        engine.startPlayback();
        core.setIsPaused(false);
      }
    } catch (error) {
      const errorMsg = `Failed to initialize streaming: ${error instanceof Error ? error.message : String(error)}`;
      console.error('[usePlayEnhanced]', errorMsg);
      dispatch(setStreamingError({ streamType: 'enhanced', error: errorMsg }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch]);
  core.handleStreamStartRef.current = handleStreamStart;

  /**
   * Handle fingerprint_progress message from backend
   */
  const handleFingerprintProgress = useCallback((message: FingerprintProgressMessage) => {
    const { status, message: progressMessage } = message.data || {};

    DEBUG && console.log('[usePlayEnhanced] Fingerprint progress:', { status, message: progressMessage });

    setFingerprintStatus(status || 'idle');
    setFingerprintMessage(progressMessage || null);

    // Auto-clear success message after 2 seconds; store handle so it can be
    // cancelled on unmount to avoid setState on a dead component (fixes #2353).
    if (status === 'complete') {
      if (fingerprintTimeoutRef.current !== null) {
        clearTimeout(fingerprintTimeoutRef.current);
      }
      fingerprintTimeoutRef.current = setTimeout(() => {
        fingerprintTimeoutRef.current = null;
        setFingerprintStatus('idle');
        setFingerprintMessage(null);
      }, 2000);
    }
  }, []);
  handleFingerprintProgressRef.current = handleFingerprintProgress;

  /**
   * Start enhanced audio playback
   * Note: Subscriptions are handled on mount, so we just need to prepare
   * the playback state and send the message.
   */
  const playEnhanced = useCallback(
    async (trackId: number, preset: EnhancementPreset, intensity: number) => {
      try {
        // Stop any existing playback
        core.playbackEngineRef.current?.stopPlayback();
        // Release the prior ~100 MB buffer before dropping the ref (#4147)
        core.pcmBufferRef.current?.dispose();
        core.pcmBufferRef.current = null;
        core.streamingMetadataRef.current = null;
        core.pendingChunksRef.current = [];
        core.lastReceivedChunkIndexRef.current = -1;

        // Reset streaming state
        dispatch(resetStreaming('enhanced'));

        // Reset fingerprint status
        setFingerprintStatus('idle');
        setFingerprintMessage(null);

        // Check WebSocket connection before proceeding
        if (!wsContext.isConnected) {
          throw new Error('WebSocket not connected. Please wait for connection and try again.');
        }

        // Load track data from backend so we can set currentTrack (fixes #2258)
        // AbortController cancels fetch on unmount/re-invocation (#2780)
        core.abortRef.current?.abort();
        core.abortRef.current = new AbortController();
        try {
          const response = await fetch(getApiUrl(`/api/library/tracks/${trackId}`), {
            signal: core.abortRef.current.signal,
          });
          if (response.ok) {
            const track = await response.json();
            // #3587: keep queue.currentIndex aligned with player.currentTrack
            // for the duration before backend WS confirmation arrives.
            dispatch(setCurrentTrackAndSyncQueue(track));
            DEBUG && console.log('[usePlayEnhanced] Set current track:', track.title);
          }
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') return;
          DEBUG && console.warn('[usePlayEnhanced] Failed to load track data:', err);
          // Continue anyway - playback will still work
        }

        // Store track info for seek operations
        currentTrackInfoRef.current = {
          trackId,
          preset,
          intensity,
        };

        // Set buffering state immediately for instant user feedback
        dispatch(startStreaming({
          streamType: 'enhanced',
          trackId,
          totalChunks: 0, // Will be updated when stream starts
          intensity,
        }));

        // Send play_enhanced message to backend
        // Subscriptions are already set up on mount
        wsContext.send({
          type: 'play_enhanced',
          data: {
            track_id: trackId,
            preset,
            intensity,
          },
        });

        DEBUG && console.log('[usePlayEnhanced] Play enhanced requested (buffering...):', {
          trackId,
          preset,
          intensity,
        });
      } catch (error) {
        const errorMsg = `Failed to start enhanced playback: ${error instanceof Error ? error.message : String(error)}`;
        console.error('[usePlayEnhanced]', errorMsg);
        dispatch(setStreamingError({ streamType: 'enhanced', error: errorMsg }));
      }
    },
    [wsContext, dispatch]
  );

  /**
   * Seek to a specific position in the current track
   * Sends a seek message to backend which restarts streaming from that position
   */
  const seekTo = useCallback((position: number) => {
    if (!currentTrackInfoRef.current) {
      DEBUG && console.warn('[usePlayEnhanced] Cannot seek: no track info available');
      return;
    }

    if (!wsContext.isConnected) {
      DEBUG && console.warn('[usePlayEnhanced] Cannot seek: WebSocket not connected');
      return;
    }

    const { trackId, preset, intensity } = currentTrackInfoRef.current;

    DEBUG && console.log('[usePlayEnhanced] Seeking to:', position, 'seconds');

    // Set seeking state
    setIsSeeking(true);

    // Stop current playback and clear buffer
    core.playbackEngineRef.current?.stopPlayback();
    core.pcmBufferRef.current?.reset();

    // Reset streaming metadata for new seek stream
    if (core.streamingMetadataRef.current) {
      core.streamingMetadataRef.current.processedChunks = 0;
    }

    // Clear pending chunks
    core.pendingChunksRef.current = [];
    core.lastReceivedChunkIndexRef.current = -1;

    // Send seek message to backend
    wsContext.send({
      type: 'seek',
      data: {
        track_id: trackId,
        position,
        preset,
        intensity,
      },
    });
  }, [wsContext, core.playbackEngineRef, core.pcmBufferRef, core.streamingMetadataRef, core.pendingChunksRef, core.lastReceivedChunkIndexRef]);

  /**
   * Subscribe to the two events not owned by the shared core (fingerprint
   * progress, seek acknowledgement) on mount (or WebSocket reconnect).
   */
  useEffect(() => {
    unsubscribeFingerprintRef.current = wsContext.subscribe(
      'fingerprint_progress',
      (m) => handleFingerprintProgressRef.current?.(m as FingerprintProgressMessage)
    );

    // Subscribe to seek_started to clear isSeeking as soon as the backend
    // acknowledges the seek request. This acts as a fallback if the subsequent
    // audio_stream_start (with is_seek=true) is lost on reconnect (#2873).
    unsubscribeSeekStartedRef.current = wsContext.subscribe(
      'seek_started',
      () => setIsSeeking(false)
    );

    DEBUG && console.log('[usePlayEnhanced] Subscribed to fingerprint/seek messages on mount');

    return () => {
      unsubscribeFingerprintRef.current?.();
      unsubscribeSeekStartedRef.current?.();
      DEBUG && console.log('[usePlayEnhanced] Unsubscribed from fingerprint/seek messages on unmount');
    };
  }, [wsContext]);

  /**
   * Cleanup on unmount - stop playback but DON'T unsubscribe (handled above
   * and by the shared core). Also resets Redux streaming state on MOUNT to
   * clear any stale state left by a previous instance (prevents phantom
   * progress bar on remount — fixes #2533).
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
      // Cancel pending fingerprint status timer to avoid setState on dead component (#2353)
      if (fingerprintTimeoutRef.current !== null) {
        clearTimeout(fingerprintTimeoutRef.current);
        fingerprintTimeoutRef.current = null;
      }
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
    fingerprintStatus,
    fingerprintMessage,
  };
};
