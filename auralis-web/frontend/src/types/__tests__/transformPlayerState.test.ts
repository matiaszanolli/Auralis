/**
 * transformPlayerState Regression Test
 *
 * Regression test for issue #2650:
 * Verifies all snake_case backend fields are correctly mapped to
 * camelCase frontend fields with proper defaults.
 */

import { describe, it, expect } from 'vitest';
import { transformPlayerState, RawPlayerStateData } from '../websocket';

describe('transformPlayerState (regression: #2650)', () => {
  const fullRawState: RawPlayerStateData = {
    state: 'playing',
    is_playing: true,
    is_paused: false,
    current_track: { id: 1, title: 'Test', artist: 'Artist', album: 'Album', duration: 180, filepath: '/test.mp3' },
    current_time: 42.5,
    duration: 180.0,
    volume: 75,
    is_muted: false,
    queue: [],
    queue_index: 3,
    queue_size: 10,
    shuffle_enabled: false,
    repeat_mode: 'off',
    mastering_enabled: true,
    current_preset: 'adaptive',
    gapless_enabled: false,
    crossfade_enabled: false,
    crossfade_duration: 5.0,
  };

  it('maps all snake_case fields to camelCase', () => {
    const result = transformPlayerState(fullRawState);

    expect(result.currentTrack).toEqual(fullRawState.current_track);
    expect(result.isPlaying).toBe(true);
    expect(result.volume).toBe(75);
    expect(result.position).toBe(42.5); // current_time → position
    expect(result.duration).toBe(180.0);
    expect(result.queue).toEqual([]);
    expect(result.queueIndex).toBe(3);
    expect(result.gaplessEnabled).toBe(false);
    expect(result.crossfadeEnabled).toBe(false);
    expect(result.crossfadeDuration).toBe(5.0);
  });

  it('provides sensible defaults for missing optional fields', () => {
    const minimal: RawPlayerStateData = {
      state: 'idle',
      is_playing: false,
      is_paused: false,
      current_track: null,
      current_time: 0,
      duration: 0,
      volume: 80,
      is_muted: false,
      queue: [],
      queue_index: -1,
      queue_size: 0,
      shuffle_enabled: false,
      repeat_mode: 'off',
      mastering_enabled: false,
      current_preset: 'adaptive',
      // gapless_enabled, crossfade_enabled, crossfade_duration omitted
    };

    const result = transformPlayerState(minimal);

    expect(result.gaplessEnabled).toBe(true);      // default
    expect(result.crossfadeEnabled).toBe(true);     // default
    expect(result.crossfadeDuration).toBe(3.0);     // default
  });

  it('handles null current_track', () => {
    const result = transformPlayerState({ ...fullRawState, current_track: null });
    expect(result.currentTrack).toBeNull();
  });

  it('current_time maps to position (not currentTime)', () => {
    const result = transformPlayerState({ ...fullRawState, current_time: 99.9 });
    expect(result.position).toBe(99.9);
    expect((result as any).currentTime).toBeUndefined();
  });

  it('volume defaults to 80 when undefined', () => {
    const raw = { ...fullRawState } as any;
    delete raw.volume;
    const result = transformPlayerState(raw);
    expect(result.volume).toBe(80);
  });
});
