/**
 * useEnhancedSeek Hook
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Owns the seek control for enhanced playback: the `seekTo` command (stops the
 * current engine, clears the buffer, and asks the backend to restart streaming
 * from the target position) and the `seek_started` subscription that clears the
 * seeking flag as soon as the backend acknowledges — a fallback if the follow-up
 * audio_stream_start (is_seek=true) is lost on reconnect (#2873).
 *
 * The `isSeeking` state itself is owned by the composing hook (usePlayEnhanced)
 * because the shared streaming core's cleanup callback also needs to clear it;
 * this hook receives `setIsSeeking` and drives it.
 *
 * Extracted from usePlayEnhanced (#4077).
 *
 * @module hooks/enhancement/useEnhancedSeek
 */

const DEBUG = import.meta.env.DEV;

import { useCallback, useEffect } from 'react';
import type { MutableRefObject } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type { StreamingCoreReturn } from './useAudioStreamingCore';
import type { CurrentTrackInfo } from './useEnhancedStreamStart';

type WebSocketContextValue = ReturnType<typeof useWebSocketContext>;

export interface UseEnhancedSeekParams {
  wsContext: WebSocketContextValue;
  core: StreamingCoreReturn;
  currentTrackInfoRef: MutableRefObject<CurrentTrackInfo | null>;
  setIsSeeking: (seeking: boolean) => void;
}

export interface UseEnhancedSeekReturn {
  /** Seek to a position (seconds) by restarting the stream from there. */
  seekTo: (position: number) => void;
}

export function useEnhancedSeek({
  wsContext,
  core,
  currentTrackInfoRef,
  setIsSeeking,
}: UseEnhancedSeekParams): UseEnhancedSeekReturn {
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
  }, [wsContext, currentTrackInfoRef, setIsSeeking, core.playbackEngineRef, core.pcmBufferRef, core.streamingMetadataRef, core.pendingChunksRef, core.lastReceivedChunkIndexRef]);

  // Subscribe to seek_started to clear isSeeking as soon as the backend
  // acknowledges the seek request (fallback for a lost audio_stream_start #2873).
  useEffect(() => {
    const unsubscribe = wsContext.subscribe('seek_started', () => setIsSeeking(false));
    DEBUG && console.log('[usePlayEnhanced] Subscribed to seek_started on mount');
    return () => {
      unsubscribe?.();
      DEBUG && console.log('[usePlayEnhanced] Unsubscribed from seek_started on unmount');
    };
  }, [wsContext, setIsSeeking]);

  return { seekTo };
}
