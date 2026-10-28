/**
 * useOutgoingChannel - send / queue / stream re-issue for the shared WebSocket.
 *
 * Split out of useWebSocketConnection.ts (#5840): everything that writes to the
 * socket or tracks the active stream command, as opposed to the connection
 * lifecycle that stays in the connection hook. State is the module-level
 * `connState` singleton plus the two refs the connection hook owns.
 *
 * @module hooks/websocket/useOutgoingChannel
 */

import { useCallback, type MutableRefObject } from 'react';
import type { WebSocketManager } from '@/utils/errorHandling';
import {
  connState,
  positionRefreshedOnReplay,
  type OutgoingWebSocketMessage,
} from '@/hooks/websocket/websocketConnectionCore';

export interface OutgoingChannel {
  send: (message: OutgoingWebSocketMessage) => void;
  setResumePositionGetter: (streamType: string, getter: (() => number) | null) => void;
  reissueActiveStreamAs: (
    type: 'play_enhanced' | 'play_normal',
    dataOverrides?: Record<string, unknown>,
    startPositionOverride?: number
  ) => boolean;
}

export function useOutgoingChannel(
  wsManagerRef: MutableRefObject<WebSocketManager | null>,
  messageQueueRef: MutableRefObject<OutgoingWebSocketMessage[]>
): OutgoingChannel {
  /**
   * Send message (or queue it if disconnected).
   */
  const send = useCallback((message: OutgoingWebSocketMessage) => {
    if (wsManagerRef.current?.isConnected()) {
      // Track last active streaming command for reconnect resume (issue #2385).
      // Only track when connected: queued commands are replayed from the queue on
      // reconnect and must not be re-issued a second time via this mechanism.
      if (message?.type === 'play_enhanced' || message?.type === 'play_normal') {
        connState.lastStreamCommand = message;
        connState.streamActive = true;
      } else if (message?.type === 'seek') {
        // A seek restarts the tracked track's stream, even after it ended (#5876).
        connState.streamActive = connState.lastStreamCommand !== null;
      } else if (message?.type === 'stop' || message?.type === 'pause') {
        connState.lastStreamCommand = null;
        connState.streamActive = false;
      }
      wsManagerRef.current.send(JSON.stringify(message));
    } else {
      // Queue message for sending when connected
      console.warn('WebSocket not connected, queueing message');
      // An explicit stop/pause while disconnected cancels any pending stream resume
      // so that reconnect does not silently restart stopped/paused playback (issue #2385).
      if (message?.type === 'stop' || message?.type === 'pause') {
        connState.lastStreamCommand = null;
        connState.streamActive = false;
      }
      messageQueueRef.current.push(message);
    }
  }, []);

  // #3730: stable identity for setResumePositionGetter so the memoized context
  // value doesn't break on every render. The singleton getter map is
  // module-level so this callback never needs to close over component state.
  const setResumePositionGetter = useCallback(
    (streamType: string, getter: (() => number) | null) => {
      if (getter) {
        connState.resumeGetters[streamType] = getter;
      } else {
        delete connState.resumeGetters[streamType];
      }
    },
    []
  );

  // #3759 + #3763: re-issue the active stream with updated config.
  // Used when the user changes enhancement enabled/preset/intensity
  // mid-stream — backend binds those at processor construction so we
  // restart the stream from the current resume position. Reuses the
  // existing #3185 plumbing (lastStreamCommand + resumeGetters).
  const reissueActiveStreamAs = useCallback(
    (
      type: 'play_enhanced' | 'play_normal',
      dataOverrides: Record<string, unknown> = {},
      // #4655: an explicit resume point (e.g. a chunk-failure recovery_position)
      // takes priority over the live resumeGetters lookup below, which reports
      // *current playback position* — not the same quantity when recovering
      // from a mid-stream error the client hasn't played up to yet.
      startPositionOverride?: number
    ): boolean => {
      // Nothing to re-issue once the session ended (#5876): flipping
      // enhancement while stopped or after the track finished must not start
      // the last track again.
      const last = connState.lastStreamCommand;
      if (!last || !connState.streamActive) return false;
      const prevData = (last.data ?? {}) as Record<string, unknown>;
      const trackId = prevData.track_id;
      if (trackId == null) return false;

      const resumePos = startPositionOverride ?? connState.resumeGetters[type]?.() ?? 0;
      const next: OutgoingWebSocketMessage = {
        type,
        data: {
          track_id: trackId,
          ...dataOverrides,
          start_position: resumePos,
        },
      };

      if (wsManagerRef.current?.isConnected()) {
        connState.lastStreamCommand = next;
        wsManagerRef.current.send(JSON.stringify(next));
      } else {
        // While disconnected, queue so the reconnect path picks the
        // most-recent config; update the tracked command so we don't
        // double-send on reconnect.
        connState.lastStreamCommand = next;
        if (startPositionOverride === undefined) positionRefreshedOnReplay.add(next);
        messageQueueRef.current.push(next);
      }
      return true;
    },
    []
  );

  return { send, setResumePositionGetter, reissueActiveStreamAs };
}
