/**
 * useEnhancedStreamStart Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Owns the `audio_stream_start` handler for enhanced playback: it (re)builds the
 * PCMStreamBuffer + AudioPlaybackEngine + AudioContext for a new stream, handles
 * the seek-resume fast path, drains any chunks that raced ahead of stream_start,
 * and starts playback once the engine's minimum buffer is satisfied. The handler
 * is registered on `core.handleStreamStartRef` so the shared streaming core
 * dispatches to it.
 *
 * Extracted from usePlayEnhanced (#4077).
 *
 * @module hooks/enhancement/useEnhancedStreamStart
 */

const DEBUG = import.meta.env.DEV;

import { useCallback } from 'react';
import type { MutableRefObject } from 'react';
import type { AppDispatch } from '@/store';
import PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';
import AudioPlaybackEngine from '@/services/audio/AudioPlaybackEngine';
import {
  startStreaming,
  setStreamingError,
} from '@/store/slices/playerSlice';
import { decodeAudioChunkMessage } from '@/utils/audio/pcmDecoding';
import type { AudioStreamStartMessage } from '@/contexts/WebSocketContext';
import type { StreamingCoreReturn } from './useAudioStreamingCore';

/** Track parameters retained so a seek can restart the stream (shared by the
 *  enhanced play/seek/stream-start hooks). */
export interface CurrentTrackInfo {
  trackId: number;
  preset: string;
  intensity: number;
}

export interface UseEnhancedStreamStartParams {
  core: StreamingCoreReturn;
  dispatch: AppDispatch;
  currentTrackInfoRef: MutableRefObject<CurrentTrackInfo | null>;
  setIsSeeking: (seeking: boolean) => void;
}

/**
 * Registers the enhanced `audio_stream_start` handler on the shared core. Returns
 * nothing — the handler is wired via `core.handleStreamStartRef`.
 */
export function useEnhancedStreamStart({
  core,
  dispatch,
  currentTrackInfoRef,
  setIsSeeking,
}: UseEnhancedStreamStartParams): void {
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
}
