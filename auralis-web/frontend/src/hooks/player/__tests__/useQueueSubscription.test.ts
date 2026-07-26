/**
 * useQueueSubscription Hook Tests (#4639)
 *
 * `useQueueSubscription` was split out of `usePlaybackQueue` in #4292 "to give
 * the WS-subscription path its own focused, independently-testable home" — and
 * then never got a test. Its only consumer's suite mocks
 * `useWebSocketMessages` to a no-op, so the handler's branch logic (including
 * the snake_case/camelCase field fallbacks) had never executed under test.
 *
 * These specs deliberately do NOT mock `useWebSocketMessages`: they mock the
 * WebSocket *context* one layer down and capture the handler it is given, so
 * the real subscription hook, the real handler, and the real `queueSlice`
 * reducers all run. Assertions read store state, not dispatch spies — a spy
 * proves an action was created, not that the reducer handles it.
 *
 * @module hooks/player/__tests__/useQueueSubscription.test
 */

import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Provider } from 'react-redux';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { createTestStore } from '@/test/test-utils';
import { useQueueSubscription } from '../useQueueSubscription';
import type { QueueTrack } from '@/types/domain';

// WebSocketContext is auto-mocked globally in src/test/setup.ts; we only
// re-point `subscribe` so the handler can be captured and invoked.
vi.mock('@/contexts/WebSocketContext');

const makeTrack = (id: number): QueueTrack =>
  ({
    id,
    title: `Track ${id}`,
    artist: 'Test Artist',
    album: 'Test Album',
    duration: 180,
  }) as QueueTrack;

const TRACKS = [makeTrack(1), makeTrack(2), makeTrack(3)];

describe('useQueueSubscription', () => {
  let store: ReturnType<typeof createTestStore>;
  /** message type -> handler registered by useWebSocketMessages. */
  let handlers: Map<string, (message: any) => void>;
  let subscribe: ReturnType<typeof vi.fn>;
  let unsubscribe: ReturnType<typeof vi.fn>;

  const renderSubscription = () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(Provider, { store, children });
    return renderHook(() => useQueueSubscription(), { wrapper });
  };

  /** Deliver a synthetic broadcast through the real captured handler. */
  const deliver = (message: any) => {
    const handler = handlers.get(message?.type);
    if (!handler) throw new Error(`no handler subscribed for "${message?.type}"`);
    act(() => {
      handler(message);
    });
  };

  const queue = () => store.getState().queue;

  beforeEach(() => {
    vi.clearAllMocks();
    store = createTestStore();
    handlers = new Map();
    unsubscribe = vi.fn();

    subscribe = vi.fn((type: string, handler: (message: any) => void) => {
      handlers.set(type, handler);
      return unsubscribe;
    });

    vi.mocked(useWebSocketContext).mockReturnValue({ subscribe } as any);
  });

  // --------------------------------------------------------------------
  // Wiring
  // --------------------------------------------------------------------

  it('subscribes to exactly the three queue message types', () => {
    renderSubscription();

    expect(subscribe).toHaveBeenCalledTimes(3);
    expect([...handlers.keys()].sort()).toEqual([
      'queue_changed',
      'queue_shuffled',
      'repeat_mode_changed',
    ]);
  });

  it('unsubscribes every handler on unmount', () => {
    const { unmount } = renderSubscription();
    unmount();
    expect(unsubscribe).toHaveBeenCalledTimes(3);
  });

  // --------------------------------------------------------------------
  // queue_changed
  // --------------------------------------------------------------------

  it('applies tracks from queue_changed', () => {
    renderSubscription();

    deliver({ type: 'queue_changed', data: { tracks: TRACKS } });

    expect(queue().tracks).toHaveLength(3);
    expect(queue().tracks.map((t) => t.id)).toEqual([1, 2, 3]);
  });

  it('applies snake_case current_index', () => {
    renderSubscription();

    deliver({ type: 'queue_changed', data: { tracks: TRACKS, current_index: 2 } });

    expect(queue().currentIndex).toBe(2);
  });

  it('applies camelCase currentIndex as a fallback', () => {
    renderSubscription();

    deliver({ type: 'queue_changed', data: { tracks: TRACKS, currentIndex: 2 } });

    expect(queue().currentIndex).toBe(2);
  });

  it('prefers snake_case when both spellings are present', () => {
    renderSubscription();

    deliver({
      type: 'queue_changed',
      data: { tracks: TRACKS, current_index: 1, currentIndex: 2 },
    });

    expect(queue().currentIndex).toBe(1);
  });

  it('accepts current_index: 0 (not treated as absent)', () => {
    renderSubscription();

    deliver({ type: 'queue_changed', data: { tracks: TRACKS, current_index: 2 } });
    expect(queue().currentIndex).toBe(2);

    deliver({ type: 'queue_changed', data: { tracks: TRACKS, current_index: 0 } });
    expect(queue().currentIndex).toBe(0);
  });

  it('leaves currentIndex untouched when neither spelling is sent', () => {
    renderSubscription();

    deliver({ type: 'queue_changed', data: { tracks: TRACKS, current_index: 2 } });
    expect(queue().currentIndex).toBe(2);

    deliver({ type: 'queue_changed', data: { tracks: TRACKS } });
    expect(queue().currentIndex).toBe(2);
  });

  it('leaves tracks untouched when the message carries only an index', () => {
    renderSubscription();

    deliver({ type: 'queue_changed', data: { tracks: TRACKS } });
    deliver({ type: 'queue_changed', data: { current_index: 1 } });

    expect(queue().tracks).toHaveLength(3);
    expect(queue().currentIndex).toBe(1);
  });

  // --------------------------------------------------------------------
  // queue_shuffled
  // --------------------------------------------------------------------

  it('applies snake_case is_shuffled', () => {
    renderSubscription();

    deliver({ type: 'queue_shuffled', data: { is_shuffled: true } });

    expect(queue().isShuffled).toBe(true);
  });

  it('applies camelCase isShuffled as a fallback', () => {
    renderSubscription();

    deliver({ type: 'queue_shuffled', data: { isShuffled: true } });

    expect(queue().isShuffled).toBe(true);
  });

  it('applies is_shuffled: false (not treated as absent)', () => {
    renderSubscription();

    deliver({ type: 'queue_shuffled', data: { is_shuffled: true } });
    expect(queue().isShuffled).toBe(true);

    deliver({ type: 'queue_shuffled', data: { is_shuffled: false } });
    expect(queue().isShuffled).toBe(false);
  });

  it('applies the reordered tracks carried by queue_shuffled', () => {
    renderSubscription();

    const reordered = [makeTrack(3), makeTrack(1), makeTrack(2)];
    deliver({ type: 'queue_shuffled', data: { is_shuffled: true, tracks: reordered } });

    expect(queue().tracks.map((t) => t.id)).toEqual([3, 1, 2]);
    expect(queue().isShuffled).toBe(true);
  });

  // --------------------------------------------------------------------
  // repeat_mode_changed
  // --------------------------------------------------------------------

  it.each(['off', 'all', 'one'] as const)(
    'applies snake_case repeat_mode "%s"',
    (mode) => {
      renderSubscription();
      // Move off the 'off' default so 'off' is an observable transition.
      deliver({ type: 'repeat_mode_changed', data: { repeat_mode: 'all' } });

      deliver({ type: 'repeat_mode_changed', data: { repeat_mode: mode } });

      expect(queue().repeatMode).toBe(mode);
    }
  );

  it('applies camelCase repeatMode as a fallback', () => {
    renderSubscription();

    deliver({ type: 'repeat_mode_changed', data: { repeatMode: 'one' } });

    expect(queue().repeatMode).toBe('one');
  });

  it('ignores an invalid repeat mode rather than corrupting the slice (#4159)', () => {
    renderSubscription();

    deliver({ type: 'repeat_mode_changed', data: { repeat_mode: 'all' } });
    deliver({ type: 'repeat_mode_changed', data: { repeat_mode: 'sideways' } });

    expect(queue().repeatMode).toBe('all');
  });

  // --------------------------------------------------------------------
  // Malformed input
  // --------------------------------------------------------------------

  it('does not throw or corrupt state on malformed payloads', () => {
    renderSubscription();

    deliver({ type: 'queue_changed', data: { tracks: TRACKS, current_index: 1 } });
    const before = queue();

    expect(() => {
      deliver({ type: 'queue_changed', data: {} });
      deliver({ type: 'queue_shuffled', data: {} });
      deliver({ type: 'repeat_mode_changed', data: {} });
      deliver({ type: 'queue_changed', data: { tracks: null } });
      deliver({ type: 'queue_shuffled', data: { is_shuffled: null } });
      deliver({ type: 'repeat_mode_changed', data: { repeat_mode: null } });
    }).not.toThrow();

    expect(queue().tracks.map((t) => t.id)).toEqual(before.tracks.map((t) => t.id));
    expect(queue().currentIndex).toBe(before.currentIndex);
    expect(queue().isShuffled).toBe(before.isShuffled);
    expect(queue().repeatMode).toBe(before.repeatMode);
  });

  it('does not throw when a frame arrives with no data object at all', () => {
    renderSubscription();

    // A `data`-less frame must not blow up the shared WS dispatch loop and
    // take every later message down with it.
    expect(() => {
      deliver({ type: 'queue_changed' });
      deliver({ type: 'queue_shuffled' });
      deliver({ type: 'repeat_mode_changed' });
    }).not.toThrow();

    // The subscription is still live and later well-formed messages apply.
    deliver({ type: 'queue_changed', data: { tracks: TRACKS } });
    expect(queue().tracks).toHaveLength(3);
  });

  it('ignores message types it did not subscribe to', () => {
    renderSubscription();
    deliver({ type: 'queue_changed', data: { tracks: TRACKS, current_index: 1 } });

    // WebSocketContext keys handlers by type, but the same stable callback is
    // registered for all three — an unrelated type routed to it must no-op.
    expect(() => {
      act(() => {
        handlers.get('queue_changed')!({ type: 'playback_state', data: { foo: 1 } });
      });
    }).not.toThrow();

    expect(queue().tracks).toHaveLength(3);
    expect(queue().currentIndex).toBe(1);
  });
});
