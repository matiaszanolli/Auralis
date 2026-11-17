/**
 * Direct spec for usePlayerRedux (#5683): imports the module itself, not the useReduxState barrel.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import { setCurrentTime, setVolume } from '@/store/slices/playerSlice';
import { usePlayerActions, usePlayerState } from '../usePlayerRedux';

function setup(player?: Parameters<typeof createTestStore>[0]) {
  const store = createTestStore(player);
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  return { store, wrapper };
}

describe('usePlayerState', () => {
  it('reads the player slice and follows its updates', () => {
    const { store, wrapper } = setup({ player: { volume: 40 } });
    const { result } = renderHook(() => usePlayerState(), { wrapper });
    expect(result.current.volume).toBe(40);

    act(() => { store.dispatch(setVolume(65)); });
    expect(result.current.volume).toBe(65);
  });
});

describe('usePlayerActions', () => {
  it('play and pause set isPlaying', () => {
    const { store, wrapper } = setup();
    const { result } = renderHook(() => usePlayerActions(), { wrapper });

    act(() => { result.current.play(); });
    expect(store.getState().player.isPlaying).toBe(true);
    act(() => { result.current.pause(); });
    expect(store.getState().player.isPlaying).toBe(false);
  });

  it('togglePlay reads the live isPlaying at call time, not a render-time snapshot', () => {
    const { store, wrapper } = setup();
    const { result } = renderHook(() => usePlayerActions(), { wrapper });
    const toggle = result.current.togglePlay;

    act(() => { toggle(); });
    act(() => { toggle(); });
    act(() => { toggle(); });
    // Three toggles through the SAME captured callback: a stale closure would have stopped at true.
    expect(store.getState().player.isPlaying).toBe(true);
    act(() => { toggle(); });
    expect(store.getState().player.isPlaying).toBe(false);
  });

  it('seek, volume and mute dispatch to the slice', () => {
    const { store, wrapper } = setup({ player: { isMuted: false, duration: 100 } });
    const { result } = renderHook(() => usePlayerActions(), { wrapper });

    act(() => {
      result.current.seek(42);
      result.current.setVolume(30);
      result.current.toggleMute();
    });
    const { player } = store.getState();
    expect(player.currentTime).toBe(42);
    expect(player.volume).toBe(30);
    expect(player.isMuted).toBe(true);

    act(() => { result.current.setMuted(false); });
    expect(store.getState().player.isMuted).toBe(false);
  });

  it('keeps one object identity across state changes so action-only consumers do not re-render', () => {
    const { store, wrapper } = setup();
    const { result } = renderHook(() => usePlayerActions(), { wrapper });
    const first = result.current;

    act(() => { store.dispatch(setCurrentTime(5)); });
    expect(result.current).toBe(first);
  });
});
