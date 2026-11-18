/**
 * Client-to-server WebSocket commands (#6050).
 *
 * The inbound side has a discriminated registry (registry.ts); this is its outbound twin. The
 * shapes mirror what the backend's handlers read (schemas/websocket.py): a typo in `type` or a
 * field name (`trackId`, `start_pos`) no longer compiles instead of being dropped or rejected at
 * runtime, and `track_id` is a number, not `unknown`.
 */

import type { EnhancementPreset } from '@/types/domain';

/** Start an enhanced stream. `start_position` (seconds) is set by the reconnect/reissue paths. */
export interface PlayEnhancedCommand {
  type: 'play_enhanced';
  data: {
    track_id: number;
    preset?: EnhancementPreset;
    intensity?: number;
    force?: boolean;
    start_position?: number;
  };
}

/** Start an unprocessed stream. */
export interface PlayNormalCommand {
  type: 'play_normal';
  data: { track_id: number; start_position?: number };
}

/**
 * Restart the stream at `position` seconds. preset/intensity are deliberately omitted by the app
 * (#5604): the backend resolves them from the connection's active stream settings.
 */
export interface SeekCommand {
  type: 'seek';
  data: { track_id: number; position: number; preset?: EnhancementPreset; intensity?: number };
}

/** Transport and flow-control commands that carry no payload (the server ignores `data`). */
export interface SignalCommand {
  type: 'pause' | 'stop' | 'resume' | 'buffer_full' | 'buffer_ready';
  data?: Record<string, never>;
}

/** Every command the client may send. */
export type OutgoingCommand = PlayEnhancedCommand | PlayNormalCommand | SeekCommand | SignalCommand;

/** The commands that start a stream and can be replayed on reconnect. */
export type StreamCommand = PlayEnhancedCommand | PlayNormalCommand;

/** What a live enhancement change may override when the active stream is re-issued. */
export interface StreamOverrides {
  preset?: EnhancementPreset;
  intensity?: number;
  force?: boolean;
}

/** Register (or clear, with null) the playback-position getter used when a stream is resumed. */
export type SetResumePositionGetter = (
  streamType: StreamCommand['type'],
  getter: (() => number) | null
) => void;

/**
 * Re-issue the tracked stream as `type`, applying `dataOverrides`; `startPositionOverride` (seconds)
 * wins over the live resume position. False when there is no active stream to re-issue (#3759).
 */
export type ReissueActiveStream = (
  type: StreamCommand['type'],
  dataOverrides?: StreamOverrides,
  startPositionOverride?: number
) => boolean;
