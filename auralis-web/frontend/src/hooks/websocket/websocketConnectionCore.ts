/**
 * websocketConnectionCore - transport singletons + pure framing helpers
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The React-free core of the single WebSocket connection, split out of
 * `useWebSocketConnection` (#4297). The singleton state and shared types now
 * live in `websocketConnectionState`, inbound-frame parsing in
 * `socketFrameParser` (#5840); both are re-exported here so existing importers
 * keep one import site. This module keeps the on-reconnect queue replay and
 * stream resume.
 */

import type { WebSocketManager } from '@/utils/errorHandling';
import {
  connState,
  positionRefreshedOnReplay,
  resetStreamFrameTracking,
  type OutgoingWebSocketMessage,
} from './websocketConnectionState';

export * from './websocketConnectionState';
export { handleSocketFrame } from './socketFrameParser';

/**
 * On (re)connect: flush the offline send-queue, then re-issue the last active
 * stream so audio resumes after a drop (#2385) from the current playback
 * position (#3185). Skips the re-issue if the queue already carried a fresh
 * play/stop command, so a stale play is not replayed over it (#3345).
 *
 * Starts by resetting the stream frame tracking (#5619): the socket just
 * (re)opened, so whatever `expectedSeq`/`seqStreamEpoch` a previous connection
 * — possibly against a previous backend process — tracked can only be stale.
 */
export function replayQueueAndResume(
  manager: WebSocketManager,
  queue: OutgoingWebSocketMessage[]
): void {
  resetStreamFrameTracking();

  // Send queued messages (commands sent while disconnected). Track whether any
  // queued message supersedes the saved stream command so we don't re-issue a
  // stale play after reconnect (#3345).
  let queueHadStreamCommand = false;
  while (queue.length > 0) {
    let message = queue.shift();
    if (message && positionRefreshedOnReplay.has(message)) {
      const resumePos = connState.resumeGetters[message.type]?.() ?? 0;
      message = { ...message, data: { ...(message.data ?? {}), start_position: resumePos } };
    }
    if (message?.type === 'play_enhanced' || message?.type === 'play_normal') {
      connState.lastStreamCommand = message;
      connState.streamActive = true;
      queueHadStreamCommand = true;
    } else if (message?.type === 'stop' || message?.type === 'pause') {
      connState.lastStreamCommand = null;
      connState.streamActive = false;
      queueHadStreamCommand = true;
    }
    manager.send(JSON.stringify(message));
  }

  // Only a stream still live when the socket dropped resumes: a track that
  // finished, was stopped or failed must not restart on reconnect (#5876).
  if (connState.lastStreamCommand && connState.streamActive && !queueHadStreamCommand) {
    const resumePos = connState.resumeGetters[connState.lastStreamCommand.type]?.() ?? 0;
    const resumeCommand = {
      ...connState.lastStreamCommand,
      data: {
        ...(connState.lastStreamCommand.data ?? {}),
        start_position: resumePos,
      },
    };
    console.log(`🔄 Reconnected - re-issuing stream command: ${connState.lastStreamCommand.type} at ${resumePos.toFixed(1)}s`);
    manager.send(JSON.stringify(resumeCommand));
  }
}
