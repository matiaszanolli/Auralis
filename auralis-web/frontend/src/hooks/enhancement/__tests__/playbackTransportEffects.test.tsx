/**
 * The one-job effect hooks usePlaybackTransport composes (#6703).
 */

import { afterEach, describe, it, expect, vi } from 'vitest';
import type { ReactNode } from 'react';
import { Provider } from 'react-redux';
import { act, renderHook } from '@testing-library/react';
import { createTestStore } from '@/test/test-utils';
import { setMuted } from '@/store/slices/playerSlice';
import type { AudioPlaybackEngine } from '@/services/audio/AudioPlaybackEngine';
import {
  useDisconnectKeepalive,
  useEngineGainSync,
  useEnginePlayingSync,
  usePlaybackClock,
  useResumePositionRegistration,
} from '@/hooks/enhancement/playbackTransportEffects';

function fakeEngine(time = 0) {
  return {
    setVolume: vi.fn(),
    pausePlayback: vi.fn(),
    getCurrentPlaybackTime: vi.fn(() => time),
  };
}

function engineRef(engine: ReturnType<typeof fakeEngine> | null) {
  return { current: engine as unknown as AudioPlaybackEngine | null };
}

afterEach(() => {
  vi.useRealTimers();
});

describe('useEngineGainSync', () => {
  it('applies the Redux volume as engine gain and re-applies it on mute (#5607)', () => {
    const store = createTestStore({ player: { volume: 50, isMuted: false } });
    const engine = fakeEngine();
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;

    renderHook(() => useEngineGainSync(engineRef(engine)), { wrapper });
    expect(engine.setVolume).toHaveBeenLastCalledWith(0.5);

    act(() => {
      store.dispatch(setMuted(true));
    });
    expect(engine.setVolume).toHaveBeenLastCalledWith(0);
  });
});

describe('usePlaybackClock', () => {
  it('polls the engine time at 10 Hz only while playing (#3970)', () => {
    vi.useFakeTimers();
    const engine = fakeEngine(12.5);
    const setCurrentTime = vi.fn();
    const ref = engineRef(engine);

    const { rerender } = renderHook(({ playing }) => usePlaybackClock(playing, ref, setCurrentTime), {
      initialProps: { playing: false },
    });
    vi.advanceTimersByTime(500);
    expect(setCurrentTime).not.toHaveBeenCalled();

    rerender({ playing: true });
    vi.advanceTimersByTime(300);
    expect(setCurrentTime).toHaveBeenCalledTimes(3);
    const update = setCurrentTime.mock.calls[0][0] as (prev: number) => number;
    expect(update(0)).toBe(12.5);
    expect(update(12.5)).toBe(12.5);
  });
});

describe('useEnginePlayingSync', () => {
  it('pauses the engine once when Redux stops playing, and resumes only a paused session', () => {
    const engine = fakeEngine();
    const ref = engineRef(engine);
    const resume = vi.fn();
    const setIsPaused = vi.fn();

    const { rerender } = renderHook(
      ({ playing, paused }) => useEnginePlayingSync(playing, paused, ref, resume, setIsPaused),
      { initialProps: { playing: true, paused: false } }
    );
    expect(resume).not.toHaveBeenCalled();

    rerender({ playing: false, paused: false });
    expect(engine.pausePlayback).toHaveBeenCalledTimes(1);
    expect(setIsPaused).toHaveBeenCalledWith(true);

    // #3624: isPaused flipping must not re-run the sync (no second pause).
    rerender({ playing: false, paused: true });
    expect(engine.pausePlayback).toHaveBeenCalledTimes(1);

    rerender({ playing: true, paused: true });
    expect(resume).toHaveBeenCalledTimes(1);
  });

  it('does nothing without an engine', () => {
    const resume = vi.fn();
    const setIsPaused = vi.fn();
    renderHook(() => useEnginePlayingSync(false, false, engineRef(null), resume, setIsPaused));
    expect(setIsPaused).not.toHaveBeenCalled();
  });
});

describe('useResumePositionRegistration', () => {
  it('registers the engine position for the stream and normal commands, and clears both on unmount', () => {
    const engine = fakeEngine(42);
    const setGetter = vi.fn();

    const { unmount } = renderHook(() =>
      useResumePositionRegistration(setGetter, 'play_enhanced', true, engineRef(engine))
    );
    expect(setGetter.mock.calls.map((c) => c[0])).toEqual(['play_enhanced', 'play_normal']);
    expect((setGetter.mock.calls[0][1] as () => number)()).toBe(42);

    unmount();
    expect(setGetter).toHaveBeenCalledWith('play_enhanced', null);
    expect(setGetter).toHaveBeenCalledWith('play_normal', null);
  });
});

describe('useDisconnectKeepalive', () => {
  it('runs onDisconnectExtra on disconnect without touching the engine', () => {
    const engine = fakeEngine();
    const extra = vi.fn();
    const ref = engineRef(engine);

    const { rerender } = renderHook(
      ({ connected }) => useDisconnectKeepalive(connected, ref, '[test]', extra),
      { initialProps: { connected: true } }
    );
    expect(extra).not.toHaveBeenCalled();

    rerender({ connected: false });
    expect(extra).toHaveBeenCalledTimes(1);
    expect(engine.pausePlayback).not.toHaveBeenCalled();
  });
});
