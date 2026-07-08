/**
 * usePlayNormal Hook
 * ~~~~~~~~~~~~~~~~~~
 *
 * Manages WebSocket-based PCM audio streaming for original (unprocessed) audio playback.
 * Used for comparing normal vs enhanced audio. Same architecture as usePlayEnhanced —
 * both compose the shared `useAudioStreamingCore` (fixes #4019).
 *
 * Usage:
 * ```typescript
 * const {
 *   playNormal,
 *   stopPlayback,
 *   pausePlayback,
 *   resumePlayback,
 *   isStreaming,
 *   streamingProgress,
 *   bufferedSamples,
 *   error
 * } = usePlayNormal();
 *
 * // Start normal (unprocessed) playback
 * await playNormal(trackId);
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
 * @module hooks/enhancement/usePlayNormal
 */

const DEBUG = import.meta.env.DEV;

import { useCallback, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch } from '@/store';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { getApiUrl } from '@/config/api';
import PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import {
  startStreaming,
  setStreamingError,
  resetStreaming,
  selectNormalStreaming,
  setCurrentTrackAndSyncQueue,
} from '@/store/slices/playerSlice';
import {
  decodeAudioChunkMessage,
} from '@/utils/audio/pcmDecoding';
import type {
  AudioStreamStartMessage,
} from '@/contexts/WebSocketContext';
import { useAudioStreamingCore, type StreamingMetadata } from './useAudioStreamingCore';

/**
 * Return type for usePlayNormal hook
 */
export interface UsePlayNormalReturn {
  /**
   * Start normal (unprocessed) audio playback for a track
   * @param trackId ID of track to play
   */
  playNormal: (trackId: number) => Promise<void>;

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
}

export const usePlayNormal = (): UsePlayNormalReturn => {
  const dispatch = useDispatch<AppDispatch>();
  const wsContext = useWebSocketContext();
  const streamingState = useSelector(selectNormalStreaming);

  /**
   * Handle audio_stream_start message from backend
   */
  const handleStreamStart = useCallback((message: AudioStreamStartMessage) => {
    try {
      // Only process messages intended for this hook (#2104)
      if (message.data.stream_type && message.data.stream_type !== 'normal') return;

      const isSeek = message.data.is_seek === true;

      DEBUG && console.log('[usePlayNormal] Stream started:', {
        trackId: message.data.track_id,
        chunks: message.data.total_chunks,
        duration: message.data.total_duration,
        isSeek,
      });

      // Resume guard: if we already have a live engine+buffer (e.g. after WS
      // reconnect), skip recreation and let new chunks append seamlessly (#3185).
      if (isSeek && core.playbackEngineRef.current && core.pcmBufferRef.current) {
        DEBUG && console.log('[usePlayNormal] Resuming stream into existing buffer');
        if (core.streamingMetadataRef.current) {
          core.streamingMetadataRef.current.totalChunks = message.data.total_chunks;
          core.streamingMetadataRef.current.processedChunks = 0;
        }
        core.pendingChunksRef.current = [];
        dispatch(startStreaming({
          streamType: 'normal',
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
      // playback will be ~9% faster with raised pitch.
      const sourceSampleRate = message.data.sample_rate;
      if (!core.audioContextRef.current || core.audioContextRef.current.sampleRate !== sourceSampleRate) {
        // Close existing context if sample rate differs
        if (core.audioContextRef.current) {
          DEBUG && console.log('[usePlayNormal] Closing AudioContext (sample rate mismatch)',
            core.audioContextRef.current.sampleRate, '→', sourceSampleRate);
          core.audioContextRef.current.close();
        }
        // Create new AudioContext with matching sample rate
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        core.audioContextRef.current = new AudioContextClass({ sampleRate: sourceSampleRate });
        DEBUG && console.log('[usePlayNormal] Created AudioContext with sample rate:', sourceSampleRate);
      }

      // Initialize AudioPlaybackEngine
      const engine = new AudioPlaybackEngine(
        core.audioContextRef.current,
        buffer
      );
      core.playbackEngineRef.current = engine;

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
        DEBUG && console.warn('[usePlayNormal] Buffer underrun detected');
      });

      // Store metadata
      core.streamingMetadataRef.current = {
        sampleRate: message.data.sample_rate,
        channels: message.data.channels,
        totalChunks: message.data.total_chunks,
        processedChunks: 0,
      };

      // Reset flow control for new stream
      core.flowPausedRef.current = false;

      // Update Redux state
      dispatch(
        startStreaming({
          streamType: 'normal',
          trackId: message.data.track_id,
          totalChunks: message.data.total_chunks,
          intensity: 1.0, // Original audio (no processing)
        })
      );

      // Process any chunks that arrived before stream_start (race condition handling)
      if (core.pendingChunksRef.current.length > 0) {
        DEBUG && console.log('[usePlayNormal] Processing queued chunks:', core.pendingChunksRef.current.length);
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
            console.error('[usePlayNormal] Error processing queued chunk:', queuedError);
          }
        }
      }

      // Start playback immediately when stream begins (if pending chunks filled enough buffer).
      // Use the same channel-aware threshold as handleChunk: sampleRate * channels * 2 (issue #2268).
      const minBufferSamples = message.data.sample_rate * message.data.channels * 2;
      if (buffer.getAvailableSamples() >= minBufferSamples) {
        engine.startPlayback();
        core.setIsPaused(false);
      }
    } catch (error) {
      const errorMsg = `Failed to initialize streaming: ${error instanceof Error ? error.message : String(error)}`;
      console.error('[usePlayNormal]', errorMsg);
      dispatch(setStreamingError({ streamType: 'normal', error: errorMsg }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch]);

  const core = useAudioStreamingCore(wsContext, {
    streamType: 'normal',
    sendType: 'play_normal',
    logPrefix: '[usePlayNormal]',
    // Mirror usePlayEnhanced's channel-aware threshold formula (issue #2268):
    // sampleRate * channels * 2 (2 seconds of stereo audio) avoids underruns.
    getStartThreshold: (metadata: StreamingMetadata) => metadata.sampleRate * metadata.channels * 2,
    throttleProgress: false,
    detectOutOfSequence: false,
    closeContextOnCleanup: true,
  });
  core.handleStreamStartRef.current = handleStreamStart;

  /**
   * Start normal audio playback
   */
  const playNormal = useCallback(
    async (trackId: number) => {
      try {
        // Stop any existing playback
        core.playbackEngineRef.current?.stopPlayback();
        // Release the prior ~100 MB buffer before dropping the ref (#4147)
        core.pcmBufferRef.current?.dispose();
        core.pcmBufferRef.current = null;
        core.streamingMetadataRef.current = null;

        // Reset streaming state
        dispatch(resetStreaming('normal'));

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
            DEBUG && console.log('[usePlayNormal] Set current track:', track.title);
          }
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') return;
          DEBUG && console.warn('[usePlayNormal] Failed to load track data:', err);
          // Continue anyway - playback will still work
        }

        // Send play_normal message to backend
        wsContext.send({
          type: 'play_normal',
          data: {
            track_id: trackId,
          },
        });

        DEBUG && console.log('[usePlayNormal] Play normal requested:', { trackId });
      } catch (error) {
        const errorMsg = `Failed to start normal playback: ${error instanceof Error ? error.message : String(error)}`;
        console.error('[usePlayNormal]', errorMsg);
        dispatch(setStreamingError({ streamType: 'normal', error: errorMsg }));
        core.cleanupStreaming();
      }
    },
    // core.cleanupStreaming has a stable identity (see useAudioStreamingCore) —
    // depend on it directly rather than the whole `core` object, which is a
    // fresh literal every render and would otherwise churn playNormal's identity.
    [wsContext, dispatch, core.cleanupStreaming]
  );

  /**
   * Cleanup on unmount.
   * Calls the engine stop + cleanupStreaming() directly rather than the full
   * stopPlayback(), which would re-run cleanupStreaming a second time (after an
   * explicit stopPlayback()) and fire React state setters on an unmounting
   * component (#3975). cleanupStreaming is idempotent and touches only refs.
   */
  useEffect(() => {
    return () => {
      core.playbackEngineRef.current?.stopPlayback();
      core.cleanupStreaming();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [core.cleanupStreaming]);

  return {
    playNormal,
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
  };
};
