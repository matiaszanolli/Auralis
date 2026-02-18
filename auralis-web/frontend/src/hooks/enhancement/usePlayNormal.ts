/**
 * usePlayNormal Hook
 * ~~~~~~~~~~~~~~~~~~
 *
 * Manages WebSocket-based PCM audio streaming for original (unprocessed) audio playback.
 * Used for comparing normal vs enhanced audio. Same architecture as usePlayEnhanced.
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
  selectNormalStreaming,
  selectIsPlaying,
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
  const dispatch = useDispatch();
  const wsContext = useWebSocketContext();
  const streamingState = useSelector(selectNormalStreaming);
  const isPlaying = useSelector(selectIsPlaying);

  // Internal service references
  const pcmBufferRef = useRef<PCMStreamBuffer | null>(null);
  const playbackEngineRef = useRef<AudioPlaybackEngine | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  // Subscription cleanup refs
  const unsubscribeStreamStartRef = useRef<(() => void) | null>(null);
  const unsubscribeChunkRef = useRef<(() => void) | null>(null);
  const unsubscribeStreamEndRef = useRef<(() => void) | null>(null);
  const unsubscribeErrorRef = useRef<(() => void) | null>(null);

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

  /**
   * Cleanup streaming resources
   */
  const cleanupStreaming = useCallback(() => {
    // Unsubscribe from WebSocket messages
    unsubscribeStreamStartRef.current?.();
    unsubscribeChunkRef.current?.();
    unsubscribeStreamEndRef.current?.();
    unsubscribeErrorRef.current?.();

    // Clear references
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
      // Only process messages intended for this hook (#2104)
      if (message.data.stream_type && message.data.stream_type !== 'normal') return;

      console.log('[usePlayNormal] Stream started:', {
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
      // playback will be ~9% faster with raised pitch.
      const sourceSampleRate = message.data.sample_rate;
      if (!audioContextRef.current || audioContextRef.current.sampleRate !== sourceSampleRate) {
        // Close existing context if sample rate differs
        if (audioContextRef.current) {
          console.log('[usePlayNormal] Closing AudioContext (sample rate mismatch)',
            audioContextRef.current.sampleRate, '→', sourceSampleRate);
          audioContextRef.current.close();
        }
        // Create new AudioContext with matching sample rate
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        audioContextRef.current = new AudioContextClass({ sampleRate: sourceSampleRate });
        console.log('[usePlayNormal] Created AudioContext with sample rate:', sourceSampleRate);
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
        console.warn('[usePlayNormal] Buffer underrun detected');
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
          streamType: 'normal',
          trackId: message.data.track_id,
          totalChunks: message.data.total_chunks,
          intensity: 1.0, // Original audio (no processing)
        })
      );

      // Process any chunks that arrived before stream_start (race condition handling)
      if (pendingChunksRef.current.length > 0) {
        console.log('[usePlayNormal] Processing queued chunks:', pendingChunksRef.current.length);
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
            console.error('[usePlayNormal] Error processing queued chunk:', queuedError);
          }
        }
      }

      // Start playback immediately when stream begins (if pending chunks filled enough buffer).
      // Use the same channel-aware threshold as handleChunk: sampleRate * channels * 2 (issue #2268).
      const minBufferSamples = message.data.sample_rate * message.data.channels * 2;
      if (buffer.getAvailableSamples() >= minBufferSamples) {
        engine.startPlayback();
        setIsPaused(false);
      }
    } catch (error) {
      const errorMsg = `Failed to initialize streaming: ${error instanceof Error ? error.message : String(error)}`;
      console.error('[usePlayNormal]', errorMsg);
      dispatch(setStreamingError({ streamType: 'normal', error: errorMsg }));
    }
  }, [dispatch]);

  /**
   * Handle audio_chunk message from backend
   */
  const handleChunk = useCallback((message: AudioChunkMessage) => {
    try {
      // Only process messages intended for this hook (#2104)
      if (message.data.stream_type && message.data.stream_type !== 'normal') return;

      // If stream not yet initialized, queue the chunk instead of dropping it
      if (!pcmBufferRef.current || !streamingMetadataRef.current) {
        console.log('[usePlayNormal] Queuing chunk until stream initialized:', {
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
          streamType: 'normal',
          processedChunks: streamingMetadataRef.current.processedChunks,
          bufferedSamples,
          progress: Math.min(progress, 100),
        })
      );

      // Auto-start playback when sufficient buffer accumulated.
      // Mirror usePlayEnhanced: require sampleRate * channels * 2 samples (2 seconds of
      // stereo audio) to avoid underruns on stereo content (issue #2268).
      const engine = playbackEngineRef.current;
      const minBufferSamples = streamingMetadataRef.current.sampleRate * streamingMetadataRef.current.channels * 2;
      if (engine && !engine.isPlaying() && bufferedSamples >= minBufferSamples) {
        engine.startPlayback();
        setIsPaused(false);
      }

      console.debug('[usePlayNormal] Chunk received:', {
        chunkIndex: metadata.chunkIndex,
        frames: `${metadata.frameIndex + 1}/${metadata.frameCount}`,
        samples: metadata.sampleCount,
        buffered: `${(bufferedSamples / streamingMetadataRef.current.sampleRate).toFixed(1)}s`,
      });
    } catch (error) {
      const errorMsg = `Failed to process audio chunk: ${error instanceof Error ? error.message : String(error)}`;
      console.error('[usePlayNormal]', errorMsg);
      dispatch(setStreamingError({ streamType: 'normal', error: errorMsg }));
    }
  }, [dispatch]);

  /**
   * Handle audio_stream_end message from backend
   */
  const handleStreamEnd = useCallback((message: AudioStreamEndMessage) => {
    // Only process messages intended for this hook (#2104)
    if (message.data.stream_type && message.data.stream_type !== 'normal') return;

    console.log('[usePlayNormal] Stream ended:', {
      trackId: message.data.track_id,
      totalSamples: message.data.total_samples,
      duration: message.data.duration,
    });

    // Mark as complete in Redux
    dispatch(completeStreaming('normal'));
  }, [dispatch]);

  /**
   * Handle audio_stream_error message from backend
   */
  const handleStreamError = useCallback((message: AudioStreamErrorMessage) => {
    // Only process messages intended for this hook (#2104)
    if (message.data.stream_type && message.data.stream_type !== 'normal') return;

    const errorMsg = `Streaming error: ${message.data.error} (${message.data.code})`;
    console.error('[usePlayNormal]', errorMsg);
    dispatch(setStreamingError({ streamType: 'normal', error: errorMsg }));
    cleanupStreaming();
  }, [dispatch, cleanupStreaming]);

  /**
   * Start normal audio playback
   */
  const playNormal = useCallback(
    async (trackId: number) => {
      try {
        // CRITICAL: Clean up any existing subscriptions BEFORE creating new ones
        // This prevents subscription accumulation when playNormal is called multiple times
        unsubscribeStreamStartRef.current?.();
        unsubscribeChunkRef.current?.();
        unsubscribeStreamEndRef.current?.();
        unsubscribeErrorRef.current?.();

        // Stop any existing playback
        playbackEngineRef.current?.stopPlayback();
        pcmBufferRef.current = null;
        streamingMetadataRef.current = null;

        // Reset streaming state
        dispatch(resetStreaming('normal'));

        // Check WebSocket connection before proceeding
        if (!wsContext.isConnected) {
          throw new Error('WebSocket not connected. Please wait for connection and try again.');
        }

        // Load track data from backend so we can set currentTrack
        const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8765';
        try {
          const response = await fetch(`${apiBaseUrl}/api/library/tracks`);
          if (response.ok) {
            const data = await response.json();
            const track = data.tracks?.find((t: any) => t.id === trackId);
            if (track) {
              dispatch(setCurrentTrack(track));
              console.log('[usePlayNormal] Set current track:', track.title);
            }
          }
        } catch (err) {
          console.warn('[usePlayNormal] Failed to load track data:', err);
          // Continue anyway - playback will still work
        }

        // Subscribe to streaming messages (fresh subscriptions after cleanup)
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

        // Send play_normal message to backend
        wsContext.send({
          type: 'play_normal',
          data: {
            track_id: trackId,
          },
        });

        console.log('[usePlayNormal] Play normal requested:', { trackId });
      } catch (error) {
        const errorMsg = `Failed to start normal playback: ${error instanceof Error ? error.message : String(error)}`;
        console.error('[usePlayNormal]', errorMsg);
        dispatch(setStreamingError({ streamType: 'normal', error: errorMsg }));
        cleanupStreaming();
      }
    },
    [wsContext, dispatch, handleStreamStart, handleChunk, handleStreamEnd, handleStreamError, cleanupStreaming]
  );

  /**
   * Stop playback
   */
  const stopPlayback = useCallback(() => {
    playbackEngineRef.current?.stopPlayback();
    dispatch(resetStreaming('normal'));
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
   * Update playback time periodically
   * Note: Always create the interval on mount; the callback safely handles
   * a null ref via optional chaining until the engine is created on stream start.
   */
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(playbackEngineRef.current?.getCurrentPlaybackTime() || 0);
    }, 100); // Update 10x per second

    return () => clearInterval(interval);
  }, []);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      stopPlayback();
    };
  }, [stopPlayback]);

  /**
   * Watch Redux isPlaying state and control AudioPlaybackEngine accordingly.
   * This allows usePlaybackControl.pause()/stop() to stop the engine immediately
   * without waiting for buffered audio to drain (issue #2252).
   */
  useEffect(() => {
    if (!playbackEngineRef.current) return;

    if (isPlaying) {
      // Resume playback if paused
      if (isPaused) {
        playbackEngineRef.current.resumePlayback();
        setIsPaused(false);
      }
    } else {
      // Pause playback immediately when isPlaying becomes false
      playbackEngineRef.current.pausePlayback();
      setIsPaused(true);
    }
  }, [isPlaying, isPaused]);

  return {
    playNormal,
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
  };
};
