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
import type { AudioStreamStartMessage } from '@/types/websocket';

describe('@/types/websocket barrel (#4081)', () => {
  it('re-exports the message-type tables', () => {
    // 35 public subscription types: 'audio_chunk_meta' was removed (#4167) — it
    // is consumed internally by WebSocketContext and never dispatched.
    // 'cache_cleared' was added (#4585) — it was broadcast by the backend but
    // never registered, so the dispatcher dropped it silently.
    // #4680 traded one for one: 'job_progress' added (emitted by the backend
    // with no declaration anywhere), 'queue_updated' removed (declared here
    // with no emitter since #3492).
    expect(ws.ALL_MESSAGE_TYPES).toHaveLength(35);
    expect(ws.ALL_MESSAGE_TYPES).not.toContain('audio_chunk_meta');
    expect(ws.ALL_MESSAGE_TYPES).not.toContain('queue_updated');
    expect(ws.ALL_MESSAGE_TYPES).toContain('cache_cleared');
    expect(ws.ALL_MESSAGE_TYPES).toContain('job_progress');
    expect(ws.ALL_MESSAGE_TYPES).toContain('player_state');
    expect(ws.ALL_MESSAGE_TYPES).toContain('error');
    expect(ws.PLAYER_STATE_TYPES).toContain('playback_started');
    expect(ws.QUEUE_TYPES).toContain('queue_changed');
    expect(ws.QUEUE_TYPES).not.toContain('queue_updated');
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

  it("accepts audio_stream_start.data.preset: 'none' (#4654)", () => {
    // stream_normal.py hardcodes preset="none" for the unprocessed-playback
    // path — a stream-MODE marker, not a mastering preset. This fixture
    // failing to type-check against AudioStreamStartMessage is the bug
    // #4654 fixed (EnhancementPreset | 'none' override on this one field,
    // narrower than widening the picker-facing EnhancementPreset union).
    const normalStreamStart: AudioStreamStartMessage = {
      type: 'audio_stream_start',
      data: {
        track_id: 1,
        preset: 'none',
        intensity: 1.0,
        sample_rate: 44100,
        channels: 2,
        total_chunks: 4,
        chunk_duration: 15.0,
        total_duration: 60.0,
        stream_type: 'normal',
      },
    };
    expect(ws.isAudioStreamStartMessage(normalStreamStart as never)).toBe(true);

    // A real mastering preset must still type-check on the same field.
    const enhancedStreamStart: AudioStreamStartMessage = {
      ...normalStreamStart,
      data: { ...normalStreamStart.data, preset: 'warm', stream_type: 'enhanced' },
    };
    expect(ws.isAudioStreamStartMessage(enhancedStreamStart as never)).toBe(true);
  });
});
