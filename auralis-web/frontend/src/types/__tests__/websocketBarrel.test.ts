/**
 * WebSocket types barrel re-export (#4081)
 *
 * The 815-line types/websocket.ts monolith was split into ./ws/* by domain.
 * This pins that the barrel still re-exports the full public surface (runtime
 * values: guards, makeGuard, message-type tables) so the split stays a
 * zero-call-site-change refactor. The compile-time _AssertExhaustive guard in
 * ws/registry.ts already proves WebSocketMessageType === ALL_MESSAGE_TYPES.
 */

import { describe, it, expect } from 'vitest';
import * as ws from '@/types/websocket';

describe('@/types/websocket barrel (#4081)', () => {
  it('re-exports the message-type tables', () => {
    expect(ws.ALL_MESSAGE_TYPES).toHaveLength(35);
    expect(ws.ALL_MESSAGE_TYPES).toContain('player_state');
    expect(ws.ALL_MESSAGE_TYPES).toContain('error');
    expect(ws.PLAYER_STATE_TYPES).toContain('playback_started');
    expect(ws.QUEUE_TYPES).toContain('queue_updated');
    expect(ws.ENHANCEMENT_TYPES).toContain('mastering_recommendation');
    expect(ws.LIBRARY_TYPES).toContain('library_updated');
  });

  it('re-exports working type guards', () => {
    const stopped = { type: 'playback_stopped', data: {} } as const;
    expect(ws.isPlaybackStoppedMessage(stopped as never)).toBe(true);
    expect(ws.isPlayerStateMessage(stopped as never)).toBe(false);

    const err = { type: 'error', error: 'rate_limit_exceeded', message: 'slow down' } as const;
    expect(ws.isWebSocketErrorMessage(err as never)).toBe(true);
  });

  it('re-exports makeGuard and transformPlayerState', () => {
    expect(typeof ws.makeGuard).toBe('function');
    const camel = ws.transformPlayerState({
      state: 'playing', is_playing: true, is_paused: false, current_track: null,
      current_time: 5, duration: 100, volume: 80, is_muted: false, queue: [],
      queue_index: 0, queue_size: 0, shuffle_enabled: false, repeat_mode: 'off',
      mastering_enabled: false, current_preset: 'adaptive',
    });
    expect(camel.isPlaying).toBe(true);
    expect(camel.position).toBe(5);
    expect(camel.crossfadeDuration).toBe(3.0); // default applied
  });
});
