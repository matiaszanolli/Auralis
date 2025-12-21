/**
 * usePlayEnhanced Hook
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Manages WebSocket-based PCM audio streaming for enhanced audio playback.
 * Integrates PCMStreamBuffer, AudioPlaybackEngine, and Redux state management.
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

import { useCallback, useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import {
  startStreaming,
  updateStreamingProgress,
  completeStreaming,
  setStreamingError,
  resetStreaming,
  selectStreaming,
  setCurrentTrack,
} from '@/store/slices/playerSlice';
import {
  decodeAudioChunkMessage,
} from '@/utils/audio/pcmDecoding';
import type {
  AudioStreamStartMessage,
  AudioChunkMessage,
  AudioStreamEndMessage,
  AudioStreamErrorMessage,
} from '@/contexts/WebSocketContext';

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
  playEnhanced: (trackId: number, preset: string, intensity: number) => Promise<void>;

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
   * Fingerprint analysis status (idle, analyzing, complete, failed, error)
   * Shows user feedback during audio analysis phase
   */
  fingerprintStatus: 'idle' | 'analyzing' | 'complete' | 'failed' | 'error';

  /**
   * Fingerprint analysis message for user display
   */
  fingerprintMessage: string | null;
}

export const usePlayEnhanced = (): UsePlayEnhancedReturn => {
  const dispatch = useDispatch();
  const wsContext = useWebSocketContext();
  const streamingState = useSelector(selectStreaming);

  // Internal service references
  const pcmBufferRef = useRef<PCMStreamBuffer | null>(null);
  const playbackEngineRef = useRef<AudioPlaybackEngine | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  // Subscription cleanup refs
  const unsubscribeStreamStartRef = useRef<(() => void) | null>(null);
  const unsubscribeChunkRef = useRef<(() => void) | null>(null);
  const unsubscribeStreamEndRef = useRef<(() => void) | null>(null);
  const unsubscribeErrorRef = useRef<(() => void) | null>(null);
  const unsubscribeFingerprintRef = useRef<(() => void) | null>(null);

  // Pending chunks queue - handles race condition where chunks arrive before stream_start
  const pendingChunksRef = useRef<AudioChunkMessage[]>([]);

  // Streaming metadata
  const streamingMetadataRef = useRef<{
    sampleRate: number;
    channels: number;
    totalChunks: number;
    processedChunks: number;
  } | null>(null);

  // State for UI
  const [currentTime, setCurrentTime] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [fingerprintStatus, setFingerprintStatus] = useState<'idle' | 'analyzing' | 'complete' | 'failed' | 'error'>('idle');
  const [fingerprintMessage, setFingerprintMessage] = useState<string | null>(null);

  /**
   * Cleanup streaming resources (but NOT subscriptions - managed by mount effect)
   */
  const cleanupStreaming = useCallback(() => {
    // Clear playback engine and buffer references
    // Note: We don't unsubscribe here - subscriptions are managed by the mount effect
    pcmBufferRef.current = null;
    playbackEngineRef.current = null;
    streamingMetadataRef.current = null;

    // Clear pending chunks queue
    pendingChunksRef.current = [];
  }, []);

  /**
   * Handle audio_stream_start message from backend
   */
  const handleStreamStart = useCallback((message: AudioStreamStartMessage) => {
    try {
      console.log('[usePlayEnhanced] Stream started:', {
        trackId: message.data.track_id,
        chunks: message.data.total_chunks,
        duration: message.data.total_duration,
      });

      // Initialize PCMStreamBuffer
      const buffer = new PCMStreamBuffer();
      buffer.initialize(message.data.sample_rate, message.data.channels);
      pcmBufferRef.current = buffer;

      // Create AudioContext with the SAME sample rate as the streaming audio
      // This is critical - if AudioContext runs at 48000Hz but audio is 44100Hz,
      // playback will be ~9% faster and we'll have buffer underruns.
      const sourceSampleRate = message.data.sample_rate;
      if (!audioContextRef.current || audioContextRef.current.sampleRate !== sourceSampleRate) {
        // Close existing context if sample rate differs
        if (audioContextRef.current) {
          console.log('[usePlayEnhanced] Closing AudioContext (sample rate mismatch)',
            audioContextRef.current.sampleRate, '→', sourceSampleRate);
          audioContextRef.current.close();
        }
        // Create new AudioContext with matching sample rate
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        audioContextRef.current = new AudioContextClass({ sampleRate: sourceSampleRate });
        console.log('[usePlayEnhanced] Created AudioContext with sample rate:', sourceSampleRate);
      }

      // Initialize AudioPlaybackEngine
      const engine = new AudioPlaybackEngine(
        audioContextRef.current,
        buffer
      );
      playbackEngineRef.current = engine;

      // Register state change callback
      engine.onStateChanged((state) => {
        if (state === 'paused') {
          setIsPaused(true);
        } else if (state === 'playing') {
          setIsPaused(false);
        }
      });

      // Register underrun callback
      engine.onUnderrun(() => {
        console.warn('[usePlayEnhanced] Buffer underrun detected');
      });

      // Store metadata
      streamingMetadataRef.current = {
        sampleRate: message.data.sample_rate,
        channels: message.data.channels,
        totalChunks: message.data.total_chunks,
        processedChunks: 0,
      };

      // Update Redux state
      dispatch(
        startStreaming({
          trackId: message.data.track_id,
          totalChunks: message.data.total_chunks,
          intensity: 1.0, // Will be set by caller
        })
      );

      // Process any chunks that arrived before stream_start (race condition handling)
      if (pendingChunksRef.current.length > 0) {
        console.log('[usePlayEnhanced] Processing queued chunks:', pendingChunksRef.current.length);
        const queuedChunks = [...pendingChunksRef.current];
        pendingChunksRef.current = []; // Clear queue before processing

        for (const queuedMessage of queuedChunks) {
          try {
            const { samples, metadata } = decodeAudioChunkMessage(
              queuedMessage,
              message.data.sample_rate,
              message.data.channels
            );
            buffer.append(samples, metadata.crossfadeSamples);
            streamingMetadataRef.current!.processedChunks++;
          } catch (queuedError) {
            console.error('[usePlayEnhanced] Error processing queued chunk:', queuedError);
          }
        }
      }

      // Start playback immediately when stream begins
      // (buffer should have minimum 2 seconds of data before starting)
      // Note: For stereo audio, we need sampleRate * channels * seconds interleaved samples
      const minBufferSeconds = 2;
      const minBufferSamples = message.data.sample_rate * message.data.channels * minBufferSeconds;
      if (buffer.getAvailableSamples() >= minBufferSamples) {
        engine.startPlayback();
        setIsPaused(false);
      }
    } catch (error) {
      const errorMsg = `Failed to initialize streaming: ${error instanceof Error ? error.message : String(error)}`;
      console.error('[usePlayEnhanced]', errorMsg);
      dispatch(setStreamingError(errorMsg));
    }
  }, [dispatch]);

  /**
   * Handle audio_chunk message from backend
   */
  const handleChunk = useCallback((message: AudioChunkMessage) => {
    try {
      // If stream not yet initialized, queue the chunk instead of dropping it
      if (!pcmBufferRef.current || !streamingMetadataRef.current) {
        console.log('[usePlayEnhanced] Queuing chunk until stream initialized:', {
          chunkIndex: message.data?.chunk_index,
          queueLength: pendingChunksRef.current.length + 1,
        });
        pendingChunksRef.current.push(message);
        return;
      }

      // Decode PCM samples from base64
      const { samples, metadata } = decodeAudioChunkMessage(
        message,
        streamingMetadataRef.current.sampleRate,
        streamingMetadataRef.current.channels
      );

      // Append to circular buffer
      pcmBufferRef.current.append(samples, metadata.crossfadeSamples);

      // Update tracking
      streamingMetadataRef.current.processedChunks++;
      const bufferedSamples = pcmBufferRef.current.getAvailableSamples();
      const progress =
        (streamingMetadataRef.current.processedChunks / streamingMetadataRef.current.totalChunks) * 100;

      // Update Redux
      dispatch(
        updateStreamingProgress({
          processedChunks: streamingMetadataRef.current.processedChunks,
          bufferedSamples,
          progress: Math.min(progress, 100),
        })
      );

      // Auto-start playback when sufficient buffer accumulated (2 seconds minimum)
      // Note: For stereo audio, we need sampleRate * channels * seconds interleaved samples
      const engine = playbackEngineRef.current;
      const minBufferSamples = streamingMetadataRef.current.sampleRate * streamingMetadataRef.current.channels * 2;
      if (engine && !engine.isPlaying() && bufferedSamples >= minBufferSamples) {
        console.log('[usePlayEnhanced] Starting playback with buffer:', (bufferedSamples / (streamingMetadataRef.current.sampleRate * streamingMetadataRef.current.channels)).toFixed(1) + 's');
        engine.startPlayback();
        setIsPaused(false);
      }

      // Calculate buffered duration correctly (divide by sampleRate * channels for stereo)
      const bufferedDuration = bufferedSamples / (streamingMetadataRef.current.sampleRate * streamingMetadataRef.current.channels);

      console.debug('[usePlayEnhanced] Chunk received:', {
        chunkIndex: metadata.chunkIndex,
        frames: `${metadata.frameIndex + 1}/${metadata.frameCount}`,
        samples: metadata.sampleCount,
        buffered: `${bufferedDuration.toFixed(1)}s`,
      });
    } catch (error) {
      const errorMsg = `Failed to process audio chunk: ${error instanceof Error ? error.message : String(error)}`;
      console.error('[usePlayEnhanced]', errorMsg);
      dispatch(setStreamingError(errorMsg));
    }
  }, [dispatch]);

  /**
   * Handle audio_stream_end message from backend
   */
  const handleStreamEnd = useCallback((message: AudioStreamEndMessage) => {
    console.log('[usePlayEnhanced] Stream ended:', {
      trackId: message.data.track_id,
      totalSamples: message.data.total_samples,
      duration: message.data.duration,
    });

    // Mark as complete in Redux
    dispatch(completeStreaming());
  }, [dispatch]);

  /**
   * Handle audio_stream_error message from backend
   */
  const handleStreamError = useCallback((message: AudioStreamErrorMessage) => {
    const errorMsg = `Streaming error: ${message.data.error} (${message.data.code})`;
    console.error('[usePlayEnhanced]', errorMsg);
    dispatch(setStreamingError(errorMsg));
    cleanupStreaming();
  }, [dispatch, cleanupStreaming]);

  /**
   * Handle fingerprint_progress message from backend
   */
  const handleFingerprintProgress = useCallback((message: any) => {
    const { status, message: progressMessage } = message.data || {};

    console.log('[usePlayEnhanced] Fingerprint progress:', { status, message: progressMessage });

    setFingerprintStatus(status || 'idle');
    setFingerprintMessage(progressMessage || null);

    // Auto-clear success message after 2 seconds
    if (status === 'complete') {
      setTimeout(() => {
        setFingerprintStatus('idle');
        setFingerprintMessage(null);
      }, 2000);
    }
  }, []);

  /**
   * Start enhanced audio playback
   * Note: Subscriptions are handled on mount, so we just need to prepare
   * the playback state and send the message.
   */
  const playEnhanced = useCallback(
    async (trackId: number, preset: string, intensity: number) => {
      try {
        // Stop any existing playback
        playbackEngineRef.current?.stopPlayback();
        pcmBufferRef.current = null;
        streamingMetadataRef.current = null;
        pendingChunksRef.current = [];

        // Reset streaming state
        dispatch(resetStreaming());

        // Reset fingerprint status
        setFingerprintStatus('idle');
        setFingerprintMessage(null);

        // Check WebSocket connection before proceeding
        if (!wsContext.isConnected) {
          throw new Error('WebSocket not connected. Please wait for connection and try again.');
        }

        // Load track data from backend so we can set currentTrack
        // This ensures the player bar shows the correct track info
        const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8765';
        try {
          const response = await fetch(`${apiBaseUrl}/api/library/tracks`);
          if (response.ok) {
            const data = await response.json();
            const track = data.tracks?.find((t: any) => t.id === trackId);
            if (track) {
              // Set the track as current in Redux state
              dispatch(setCurrentTrack(track));
              console.log('[usePlayEnhanced] Set current track:', track.title);
            }
          }
        } catch (err) {
          console.warn('[usePlayEnhanced] Failed to load track data:', err);
          // Continue anyway - playback will still work
        }

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

        console.log('[usePlayEnhanced] Play enhanced requested:', {
          trackId,
          preset,
          intensity,
        });
      } catch (error) {
        const errorMsg = `Failed to start enhanced playback: ${error instanceof Error ? error.message : String(error)}`;
        console.error('[usePlayEnhanced]', errorMsg);
        dispatch(setStreamingError(errorMsg));
      }
    },
    [wsContext, dispatch]
  );

  /**
   * Stop playback
   */
  const stopPlayback = useCallback(() => {
    playbackEngineRef.current?.stopPlayback();
    dispatch(resetStreaming());
    cleanupStreaming();
    setCurrentTime(0);
    setIsPaused(false);
  }, [dispatch, cleanupStreaming]);

  /**
   * Pause playback
   */
  const pausePlayback = useCallback(() => {
    playbackEngineRef.current?.pausePlayback();
    setIsPaused(true);
  }, []);

  /**
   * Resume playback
   */
  const resumePlayback = useCallback(() => {
    playbackEngineRef.current?.resumePlayback();
    setIsPaused(false);
  }, []);

  /**
   * Set playback volume
   */
  const setVolume = useCallback((volume: number) => {
    playbackEngineRef.current?.setVolume(Math.max(0, Math.min(1, volume)));
  }, []);

  /**
   * Subscribe to streaming messages on mount
   * This allows the Player's usePlayEnhanced to handle streams initiated
   * by other components (like library track clicks) that send play_enhanced
   * messages directly via WebSocket.
   */
  useEffect(() => {
    // Subscribe to streaming messages immediately on mount
    unsubscribeStreamStartRef.current = wsContext.subscribe(
      'audio_stream_start',
      handleStreamStart as any
    );
    unsubscribeChunkRef.current = wsContext.subscribe(
      'audio_chunk',
      handleChunk as any
    );
    unsubscribeStreamEndRef.current = wsContext.subscribe(
      'audio_stream_end',
      handleStreamEnd as any
    );
    unsubscribeErrorRef.current = wsContext.subscribe(
      'audio_stream_error',
      handleStreamError as any
    );
    unsubscribeFingerprintRef.current = wsContext.subscribe(
      'fingerprint_progress',
      handleFingerprintProgress as any
    );

    console.log('[usePlayEnhanced] Subscribed to streaming messages on mount');

    // Cleanup on unmount
    return () => {
      unsubscribeStreamStartRef.current?.();
      unsubscribeChunkRef.current?.();
      unsubscribeStreamEndRef.current?.();
      unsubscribeErrorRef.current?.();
      unsubscribeFingerprintRef.current?.();
      console.log('[usePlayEnhanced] Unsubscribed from streaming messages on unmount');
    };
  }, [wsContext, handleStreamStart, handleChunk, handleStreamEnd, handleStreamError, handleFingerprintProgress]);

  /**
   * Update playback time periodically
   */
  useEffect(() => {
    if (!playbackEngineRef.current) return;

    const interval = setInterval(() => {
      setCurrentTime(playbackEngineRef.current?.getCurrentPlaybackTime() || 0);
    }, 100); // Update 10x per second

    return () => clearInterval(interval);
  }, []);

  /**
   * Cleanup on unmount - stop playback but DON'T unsubscribe (handled above)
   */
  useEffect(() => {
    return () => {
      // Only stop playback engine, don't call full stopPlayback which cleans up subscriptions
      playbackEngineRef.current?.stopPlayback();
      dispatch(resetStreaming());
    };
  }, [dispatch]);

  return {
    playEnhanced,
    stopPlayback,
    pausePlayback,
    resumePlayback,
    setVolume,
    isStreaming: streamingState.state === 'streaming' || streamingState.state === 'buffering',
    streamingState: streamingState.state,
    streamingProgress: streamingState.progress,
    bufferedSamples: streamingState.bufferedSamples,
    processedChunks: streamingState.processedChunks,
    totalChunks: streamingState.totalChunks,
    error: streamingState.error,
    currentTime,
    isPaused,
    fingerprintStatus,
    fingerprintMessage,
  };
};
