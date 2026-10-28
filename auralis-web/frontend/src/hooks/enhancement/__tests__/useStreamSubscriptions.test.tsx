/**
 * useStreamSubscriptions — dependency regression test (#5621).
 *
 * The subscription effect used to depend on the whole `wsContext` object,
 * whose identity changes with every isConnected/connectionStatus flicker.
 * Each flicker tore down and re-registered all four subscriptions and — the
 * real damage — its cleanup called clearStreamStartWatchdog(), disarming the
 * #4433 stream-start watchdog for any stream whose start crossed a
 * connection flap. The effect now depends on `wsContext.subscribe` only
 * (identity-stable across status transitions, #4668's pattern), and the
 * watchdog clear is out of the cleanup: unmount coverage belongs to
 * useStreamStartWatchdog itself.
 */

import { describe, it, expect, vi, type Mock } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useStreamSubscriptions, type StreamSubscriptionDeps } from '../useStreamSubscriptions';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';

type WsContext = ReturnType<typeof useWebSocketContext>;
type Unsubscribe = Mock<() => void>;

function makeDeps(overrides: Partial<StreamSubscriptionDeps> = {}): StreamSubscriptionDeps & {
  wsContext: WsContext;
  subscribe: Mock<() => () => void>;
  unsubscribes: Unsubscribe[];
  clearStreamStartWatchdog: Mock<() => void>;
} {
  const unsubscribes: Unsubscribe[] = [vi.fn(), vi.fn(), vi.fn(), vi.fn()];
  let next = 0;
  const subscribe: Mock<() => () => void> = vi.fn(() => {
    const u: () => void = unsubscribes[next] ?? vi.fn();
    next += 1;
    return u;
  });
  // Override-aware: an injected shared clear must survive the spread below.
  const clearStreamStartWatchdog: Mock<() => void> =
    (overrides.clearStreamStartWatchdog as Mock<() => void> | undefined) ?? vi.fn();
  const wsContext = {
    subscribe,
    isConnected: true,
    setResumePositionGetter: vi.fn(),
  } as unknown as WsContext;
  // Tracked fns come AFTER the spread so the Partial<...> override type can't
  // widen them back to plain functions.
  return {
    wsContext,
    logPrefix: '[test]',
    streamEpochRef: { current: null },
    handleStreamStartRef: { current: () => {} },
    acceptsStreamType: () => true,
    handleChunk: () => {},
    handleStreamEnd: () => {},
    handleStreamError: () => {},
    ...overrides,
    bufferEpochRef: overrides.bufferEpochRef ?? { current: null },
    subscribe,
    unsubscribes,
    clearStreamStartWatchdog,
  };
}

describe('useStreamSubscriptions (#5621)', () => {
  it('does not resubscribe or clear the watchdog when only the context object identity changes', () => {
    const first = makeDeps();
    const { rerender, unmount } = renderHook((deps: StreamSubscriptionDeps) => useStreamSubscriptions(deps), {
      initialProps: first,
    });

    // One subscription per message type, nothing cleared.
    expect(first.subscribe).toHaveBeenCalledTimes(4);
    expect(first.clearStreamStartWatchdog).not.toHaveBeenCalled();

    // A WS status flicker: new context object (identity change, isConnected
    // toggled), while every dep the effect actually lists stays stable.
    const second = makeDeps({
      logPrefix: first.logPrefix,
      streamEpochRef: first.streamEpochRef,
      handleStreamStartRef: first.handleStreamStartRef,
      acceptsStreamType: first.acceptsStreamType,
      clearStreamStartWatchdog: first.clearStreamStartWatchdog,
      handleChunk: first.handleChunk,
      handleStreamEnd: first.handleStreamEnd,
      handleStreamError: first.handleStreamError,
    });
    // Wrap the FIRST context's subscribe in a new object: same subscribe
    // identity, different object identity — exactly what a status flicker
    // used to produce.
    second.wsContext = { ...first.wsContext, isConnected: false } as unknown as WsContext;

    rerender(second);

    // Old effect body must not have re-run: no new subscriptions, no
    // unsubscribe calls, and — the defect — no watchdog clear from cleanup.
    expect(first.subscribe).toHaveBeenCalledTimes(4);
    expect(first.unsubscribes.every((u) => u.mock.calls.length === 0)).toBe(true);
    expect(first.clearStreamStartWatchdog).not.toHaveBeenCalled();

    unmount();
    expect(first.unsubscribes.every((u) => u.mock.calls.length === 1)).toBe(true);
  });

  it('unmount still unsubscribes without touching the watchdog', () => {
    const deps = makeDeps();
    const { unmount } = renderHook(() => useStreamSubscriptions(deps));

    unmount();

    expect(deps.unsubscribes.every((u) => u.mock.calls.length === 1)).toBe(true);
    // Unmount coverage is useStreamStartWatchdog's job, not this effect's.
    expect(deps.clearStreamStartWatchdog).not.toHaveBeenCalled();
  });
});
