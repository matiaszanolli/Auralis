/**
 * Streaming hooks do not key on the whole wsContext object (#6426)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * WebSocketContext re-memoizes its value on every isConnected / connectionStatus
 * change, so `wsContext` is a new object per status flicker even though send,
 * subscribe, setResumePositionGetter and reissueActiveStreamAs never change. A hook
 * that listed the whole object in a dependency array re-created its callback (and
 * everything keyed on it) on each connect/disconnect, and the flow-drain watch was
 * torn down and re-armed. These tests swap in a fresh context object with a
 * different isConnected over the same stable members.
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import { useAudioStreamingCore, type StreamingCoreOptions } from '../useAudioStreamingCore';
import { useEnhancedPlayCommand } from '../useEnhancedPlayCommand';
import { startFlowDrainWatch } from '../flowDrainWatch';

vi.mock('../flowDrainWatch', () => ({
  startFlowDrainWatch: vi.fn(() => () => {}),
}));

/** The members WebSocketContext keeps identity-stable, shared by every simulated value. */
function makeStableMembers() {
  return {
    subscribe: vi.fn(() => () => {}),
    subscribeAll: vi.fn(() => () => {}),
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    setResumePositionGetter: vi.fn(),
    reissueActiveStreamAs: vi.fn(() => false),
  };
}

/** A fresh context object (as the provider's useMemo yields on a status change). */
function contextValue(members: ReturnType<typeof makeStableMembers>, isConnected: boolean) {
  return {
    ...members,
    isConnected,
    connectionStatus: isConnected ? ('connected' as const) : ('disconnected' as const),
  };
}

const OPTIONS: StreamingCoreOptions = {
  streamType: 'enhanced',
  sendType: 'play_enhanced',
  logPrefix: '[test]',
  getStartThreshold: () => 1,
  throttleProgress: true,
  detectOutOfSequence: true,
  closeContextOnCleanup: false,
};

describe('useAudioStreamingCore with a flickering wsContext (#6426)', () => {
  let members: ReturnType<typeof makeStableMembers>;

  beforeEach(() => {
    vi.clearAllMocks();
    members = makeStableMembers();
  });

  function renderCore() {
    const store = configureStore({ reducer: { player: playerReducer } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    return renderHook(({ ws }) => useAudioStreamingCore(ws as never, OPTIONS), {
      wrapper,
      initialProps: { ws: contextValue(members, true) },
    });
  }

  it('does not tear down and re-arm the flow-drain watch on connect/disconnect', () => {
    const { rerender } = renderCore();
    expect(startFlowDrainWatch).toHaveBeenCalledTimes(1);

    rerender({ ws: contextValue(members, false) });
    rerender({ ws: contextValue(members, true) });

    expect(startFlowDrainWatch).toHaveBeenCalledTimes(1);
    expect(vi.mocked(startFlowDrainWatch).mock.calls[0][0].send).toBe(members.send);
  });

  it('keeps the chunk, end and error handlers stable', () => {
    const { result, rerender } = renderCore();
    const { handleChunk, handleStreamEnd, handleStreamError } = result.current;

    rerender({ ws: contextValue(members, false) });

    expect(result.current.handleChunk).toBe(handleChunk);
    expect(result.current.handleStreamEnd).toBe(handleStreamEnd);
    expect(result.current.handleStreamError).toBe(handleStreamError);
  });
});

describe('useEnhancedPlayCommand with a flickering wsContext (#6426)', () => {
  function setup() {
    const members = makeStableMembers();
    const refs = {
      pauseHoldRef: { current: false },
      playbackEngineRef: { current: null },
      pcmBufferRef: { current: null },
      streamingMetadataRef: { current: null },
      pendingChunksRef: { current: [] },
      lastReceivedChunkIndexRef: { current: -1 },
      abortRef: { current: undefined },
      armStreamStartWatchdog: vi.fn(),
    };
    const dispatch = vi.fn() as never;
    const currentTrackInfoRef = { current: null } as never;
    const resetFingerprint = vi.fn();
    const hook = renderHook(
      ({ ws }) =>
        useEnhancedPlayCommand({
          wsContext: ws as never,
          dispatch,
          core: { ...refs } as never,
          currentTrackInfoRef,
          resetFingerprint,
        }),
      { initialProps: { ws: contextValue(members, true) } }
    );
    return { members, hook, dispatch };
  }

  it('keeps the play callback stable across connect/disconnect', () => {
    const { members, hook } = setup();
    const first = hook.result.current;

    hook.rerender({ ws: contextValue(members, false) });
    hook.rerender({ ws: contextValue(members, true) });

    expect(hook.result.current).toBe(first);
  });

  it('still honours the latest connection state when called', async () => {
    const { members, hook } = setup();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const play = hook.result.current;

    hook.rerender({ ws: contextValue(members, false) });
    await play(7, 'adaptive', 1, 'enhanced');
    expect(members.send).not.toHaveBeenCalled(); // not connected: rejected, nothing sent

    hook.rerender({ ws: contextValue(members, true) });
    await play(7, 'adaptive', 1, 'enhanced'); // the SAME callback sees the reconnect
    expect(members.send).toHaveBeenCalledWith({
      type: 'play_enhanced',
      data: { track_id: 7, preset: 'adaptive', intensity: 1 },
    });
  });
});
