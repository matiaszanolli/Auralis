/**
 * websocketConnectionState - transport singletons + shared connection types
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The module-level state of the single WebSocket connection (one connection
 * across StrictMode remounts), split out of websocketConnectionCore.ts
 * (#5840). `websocketConnectionCore` re-exports everything here, so existing
 * import paths are unchanged.
 */

import { WebSocketManager } from '@/utils/errorHandling';
import type {
  AnyWebSocketMessage,
  AudioChunkMetaMessage,
  WebSocketMessage,
} from '@/types/websocket';

// ============================================================================
// Public types
// ============================================================================

export interface OutgoingWebSocketMessage {
  type: string;
  data?: Record<string, unknown>;
}

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

/** Dispatch a parsed inbound message to subscribers (owned by the provider). */
export type DispatchMessage = (message: AnyWebSocketMessage | WebSocketMessage) => void;

// ============================================================================
// Singleton connection state (survives StrictMode double-mounting)
// ============================================================================

/**
 * Module-level singleton state so only ONE WebSocket connection exists even
 * when StrictMode double-mounts the provider in development. A single mutable
 * container (rather than several `let` bindings) lets the pure helpers below
 * — which live in this module — share the state with the hook.
 *
 * - `manager` / `refCount`: the connection and how many providers hold it.
 * - `url`: the URL `manager` was built for, so a URL change can be detected and
 *   the old socket torn down instead of silently orphaned (#4522).
 * - `connectPromise`: the in-flight `manager.connect()` handshake. Concurrent
 *   callers await this one promise rather than each building their own manager
 *   (#4522) — the window is the whole handshake plus every reconnect backoff,
 *   up to 30 s per attempt.
 * - `pendingMeta`: an audio_chunk_meta text frame awaiting its binary PCM frame.
 * - `lastStreamCommand`: last play_enhanced/play_normal, re-issued on reconnect
 *   (#2385); cleared on explicit stop/pause.
 * - `streamActive`: whether that command's stream is still live (#5876). The
 *   client never sends WS stop/pause — stop and track end are client-side —
 *   so `lastStreamCommand` alone outlived every session and a reconnect or an
 *   enhancement toggle re-issued a finished/stopped track. Set by play_* and
 *   seek; cleared by `endActiveStream()`.
 * - `resumeGetters`: per-stream-type playback-position getters (#3185/#3373).
 * - `expectedSeq` / `seqStreamEpoch`: audio_chunk_meta.seq desync detection
 *   (#3774). `seqStreamEpoch` tracks which stream_epoch `expectedSeq` applies
 *   to, so a new stream (seek/track change) resets tracking instead of
 *   comparing against the previous stream's counter.
 */
export interface ConnectionState {
  manager: WebSocketManager | null;
  url: string | null;
  connectPromise: Promise<void> | null;
  refCount: number;
  pendingMeta: AudioChunkMetaMessage | null;
  lastStreamCommand: OutgoingWebSocketMessage | null;
  streamActive: boolean;
  resumeGetters: Record<string, () => number>;
  expectedSeq: number | null;
  seqStreamEpoch: number | null;
}

/**
 * Re-issued stream commands queued while disconnected whose start_position is only a placeholder
 * (#6044). The player keeps playing buffered audio during an outage, so the position read when the
 * command was queued lags the real one by the outage length; replay re-reads it. An explicit
 * recovery position (#4655) is deliberately not registered here.
 */
export const positionRefreshedOnReplay = new WeakSet<object>();

export const connState: ConnectionState = {
  manager: null,
  url: null,
  connectPromise: null,
  refCount: 0,
  pendingMeta: null,
  lastStreamCommand: null,
  streamActive: false,
  resumeGetters: {},
  expectedSeq: null,
  seqStreamEpoch: null,
};

/**
 * Tear down the current singleton manager, if any, before it is replaced or
 * dropped (#4522).
 *
 * Every path that clears or overwrites `connState.manager` must go through
 * here. Dropping the reference alone leaves the old socket, its handlers and
 * its running reconnect timer alive and unreachable — nothing else holds a
 * reference to close them, so it keeps dispatching inbound frames into Redux
 * for the lifetime of the renderer.
 */
export function closeCurrentManager(): void {
  if (connState.manager) {
    try {
      connState.manager.close();
    } catch {
      // Ignore errors during teardown
    }
  }
  connState.manager = null;
  connState.url = null;
  connState.connectPromise = null;
}

/**
 * Reset the per-stream frame tracking that must not survive a connection
 * (#5619). Called when a (re)connect opens: the backend's stream_epoch counter
 * is per-process (`itertools.count(1)`), so after a backend restart a resumed
 * first stream arrives with the SAME epoch number the stale `expectedSeq` was
 * tracking — epoch equality cannot distinguish a continuation from a fresh
 * process, and the stale counter would falsely DESYNC the resumed stream and
 * tear it down. `pendingMeta` goes with it: an unpaired meta stashed just
 * before the drop can never meet its binary frame on the new socket (#4782).
 */
export function resetStreamFrameTracking(): void {
  connState.pendingMeta = null;
  connState.expectedSeq = null;
  connState.seqStreamEpoch = null;
}

/**
 * Reset the connection singletons — ONLY FOR TESTING. Called by the provider's
 * resetWebSocketSingletons() (which also clears the subscription maps) between
 * tests to prevent memory leaks from accumulated connections.
 */
export function resetConnectionSingletons(): void {
  // Also clears `url` and `connectPromise` (#4522) — a leaked connectPromise
  // would make the next test's first connect() await a dead handshake.
  closeCurrentManager();
  connState.refCount = 0;
  connState.lastStreamCommand = null;
  connState.streamActive = false;
  for (const key of Object.keys(connState.resumeGetters)) {
    delete connState.resumeGetters[key];
  }
  resetStreamFrameTracking();
}

/**
 * The playback session ended: client-side stop, the track's stream finishing,
 * a terminal stream error or a stream that never started (#5876). Neither a
 * reconnect nor an enhancement toggle may re-issue it afterwards. A `trackId`
 * makes it a no-op when a newer track's command is tracked, so a superseded
 * track's late end frame cannot end the current stream.
 */
export function endActiveStream(trackId?: number): void {
  const tracked = (connState.lastStreamCommand?.data as { track_id?: unknown } | undefined)?.track_id;
  if (trackId !== undefined && tracked !== trackId) return;
  connState.streamActive = false;
}
