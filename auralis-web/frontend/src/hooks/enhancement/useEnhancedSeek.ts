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
 * A seek the backend rejects (`error` frame whose `command` is 'seek') would
 * otherwise leave `isSeeking` set forever: neither seek_started nor
 * audio_stream_start ever comes for it, and the local reset already stopped
 * the engine. The rejection clears the flag, and a rate-limited one is re-sent
 * once after the limiter's window so the target is not silently lost (#5885).
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

import { useCallback, useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useMessageSubscriptions } from '@/hooks/websocket/useWebSocketMessages';
import type { StreamingCoreReturn } from './useAudioStreamingCore';
import type { CurrentTrackInfo } from './useEnhancedStreamStart';

type WebSocketContextValue = ReturnType<typeof useWebSocketContext>;

/** The backend limiter counts messages per 1 s window (#5885). */
export const SEEK_RETRY_DELAY_MS = 1000;

interface PendingSeek {
  trackId: number;
  position: number;
  /** Already re-sent once after a rate-limit rejection. */
  retried: boolean;
}

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
  // The seek awaiting seek_started, so a rejection can be matched to it.
  const pendingSeekRef = useRef<PendingSeek | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearRetry = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  useEffect(() => clearRetry, [clearRetry]);

  const sendSeek = useCallback((seek: PendingSeek) => {
    DEBUG && console.log('[usePlayEnhanced] Seeking to:', seek.position, 'seconds');
    pendingSeekRef.current = seek;

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

    // preset/intensity are deliberately OMITTED (#5604): the backend resolves
    // them from this connection's active_stream_settings (#4742), which the
    // preset/intensity reissue in useEnhancementControl keeps current — for
    // local commands and for Settings saves via the broadcast (#5874). The
    // play-time snapshot in currentTrackInfoRef is stale the
    // moment the user moves a slider — sending it here re-mastered the seek
    // stream with the old values and un-did the live change.
    wsContext.send({
      type: 'seek',
      data: {
        track_id: seek.trackId,
        position: seek.position,
      },
    });
  }, [wsContext, setIsSeeking, core.playbackEngineRef, core.pcmBufferRef, core.streamingMetadataRef, core.pendingChunksRef, core.lastReceivedChunkIndexRef]);

  const seekTo = useCallback((position: number) => {
    if (!currentTrackInfoRef.current) {
      DEBUG && console.warn('[usePlayEnhanced] Cannot seek: no track info available');
      return;
    }

    if (!wsContext.isConnected) {
      DEBUG && console.warn('[usePlayEnhanced] Cannot seek: WebSocket not connected');
      return;
    }

    // A new target supersedes a scheduled retry of an older one.
    clearRetry();
    sendSeek({ trackId: currentTrackInfoRef.current.trackId, position, retried: false });
  }, [wsContext.isConnected, currentTrackInfoRef, clearRetry, sendSeek]);

  // seek_started clears isSeeking as soon as the backend acknowledges the seek
  // request (fallback for a lost audio_stream_start #2873). The shared
  // subscription hook keys off `subscribe` only, so a status flicker does not
  // resubscribe (#4668).
  useMessageSubscriptions(wsContext.subscribe, {
    seek_started: () => {
      pendingSeekRef.current = null;
      setIsSeeking(false);
    },
    error: (message) => {
      const rejected = pendingSeekRef.current;
      if (message.command !== 'seek' || rejected === null) return;
      pendingSeekRef.current = null;
      setIsSeeking(false);
      if (message.error !== 'rate_limit_exceeded' || rejected.retried) return;
      clearRetry();
      retryTimerRef.current = setTimeout(() => {
        retryTimerRef.current = null;
        // The user moved on (stopped, changed track) in the meantime.
        if (currentTrackInfoRef.current?.trackId !== rejected.trackId) return;
        sendSeek({ ...rejected, retried: true });
      }, SEEK_RETRY_DELAY_MS);
    },
  });

  return { seekTo };
}
