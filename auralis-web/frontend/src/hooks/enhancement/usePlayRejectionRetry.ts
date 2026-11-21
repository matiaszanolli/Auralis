/**
 * usePlayRejectionRetry Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * A `play_enhanced` / `play_normal` the backend rejects comes back as an `error` frame naming the
 * command, and nothing ever follows it: no audio_stream_start, no audio_stream_error. Before #6582
 * nothing consumed that frame, so after a skip burst over the WebSocket limiter the UI, queue
 * pointer and seek target named the last requested track while the audio was an earlier one the
 * limiter had let through.
 *
 * This wraps the play command: a rate-limited play is sent again once after the limiter's window
 * (the seek path's policy, #5885), unless the user has stopped or asked for another track since.
 * Any other rejection, or a second rate limit, surfaces as a streaming error instead of leaving the
 * player buffering until the start watchdog fires.
 *
 * @module hooks/enhancement/usePlayRejectionRetry
 */

import { useCallback, useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import { useSelector } from 'react-redux';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useMessageSubscriptions } from '@/hooks/websocket/useWebSocketMessages';
import { useLatest } from '@/hooks/shared/useLatest';
import { selectEnhancedStreaming, setStreamingError } from '@/store/slices/playerSlice';
import type { AppDispatch } from '@/store';
import type { StartPlayback, PlaybackWireType } from './useEnhancedPlayCommand';
import type { CurrentTrackInfo } from './useEnhancedStreamStart';
import { SEEK_RETRY_DELAY_MS } from './useEnhancedSeek';

type PlayArgs = Parameters<StartPlayback>;

interface PendingPlay {
  args: PlayArgs;
  /** Already re-sent once after a rate-limit rejection. */
  retried: boolean;
}

const wireCommand = (wireType: PlaybackWireType | undefined): string =>
  wireType === 'normal' ? 'play_normal' : 'play_enhanced';

export function usePlayRejectionRetry(
  subscribe: ReturnType<typeof useWebSocketContext>['subscribe'],
  dispatch: AppDispatch,
  startPlayback: StartPlayback,
  currentTrackInfoRef: MutableRefObject<CurrentTrackInfo | null>
): StartPlayback {
  const pendingRef = useRef<PendingPlay | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const streamingStateRef = useLatest(useSelector(selectEnhancedStreaming).state);

  const clearRetry = useCallback(() => {
    if (retryTimerRef.current !== null) clearTimeout(retryTimerRef.current);
    retryTimerRef.current = null;
  }, []);
  useEffect(() => clearRetry, [clearRetry]);

  const send = useCallback(
    (pending: PendingPlay) => {
      pendingRef.current = pending;
      return startPlayback(...pending.args);
    },
    [startPlayback]
  );

  const play = useCallback<StartPlayback>(
    (...args) => {
      clearRetry(); // a new request supersedes a scheduled retry of an older one
      return send({ args, retried: false });
    },
    [clearRetry, send]
  );

  useMessageSubscriptions(subscribe, {
    error: (message) => {
      const rejected = pendingRef.current;
      if (rejected === null || message.command !== wireCommand(rejected.args[3])) return;
      pendingRef.current = null;
      if (message.error !== 'rate_limit_exceeded' || rejected.retried) {
        dispatch(setStreamingError({
          streamType: 'enhanced',
          error: `Failed to start playback: ${message.message || message.error}`,
        }));
        return;
      }
      clearRetry();
      retryTimerRef.current = setTimeout(() => {
        retryTimerRef.current = null;
        // The user stopped, or asked for another track, in the meantime.
        if (streamingStateRef.current === 'idle') return;
        if (currentTrackInfoRef.current?.trackId !== rejected.args[0]) return;
        void send({ args: rejected.args, retried: true });
      }, SEEK_RETRY_DELAY_MS);
    },
  });

  return play;
}
