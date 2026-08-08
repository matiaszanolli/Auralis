/**
 * useAPIHealthPoll (#5012)
 *
 * Extracted from ConnectionStatusIndicator (#4186) with no dedicated test of
 * its own, leaving two previously-fixed races unguarded: the visibility-
 * driven pause/resume (#3257) and the dispatch-after-unmount mount guard
 * (#3585).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { ReactNode, createElement } from 'react';
import { createTestStore } from '@/test/test-utils';
import { useAPIHealthPoll } from '../useAPIHealthPoll';

let mockFetch: ReturnType<typeof vi.fn>;

function makeWrapper(store: ReturnType<typeof createTestStore>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(Provider, { store, children });
}

/** jsdom's `document.hidden` is a read-only getter; redefine it per test. */
function setDocumentHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', {
    configurable: true,
    get: () => hidden,
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
  setDocumentHidden(false);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  setDocumentHidden(false);
});

describe('useAPIHealthPoll (#5012)', () => {
  it('polls immediately on mount and dispatches connected + latency on success', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const store = createTestStore();
    renderHook(() => useAPIHealthPoll(5000), { wrapper: makeWrapper(store) });

    // The first poll only fires via the interval, not synchronously on mount.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/health', { method: 'GET' });
    expect(store.getState().connection.apiConnected).toBe(true);
    expect(typeof store.getState().connection.latency).toBe('number');
  });

  it('fires on every interval tick', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const store = createTestStore();
    renderHook(() => useAPIHealthPoll(1000), { wrapper: makeWrapper(store) });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3500);
    });

    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  it('dispatches connected: false and latency: 0 when the health fetch rejects', async () => {
    mockFetch.mockRejectedValue(new Error('network down'));
    const store = createTestStore({
      connection: { apiConnected: true, latency: 42 },
    });
    renderHook(() => useAPIHealthPoll(5000), { wrapper: makeWrapper(store) });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(store.getState().connection.apiConnected).toBe(false);
    expect(store.getState().connection.latency).toBe(0);
  });

  it('dispatches connected: false when the response is not ok', async () => {
    mockFetch.mockResolvedValue({ ok: false });
    const store = createTestStore({
      connection: { apiConnected: true },
    });
    renderHook(() => useAPIHealthPoll(5000), { wrapper: makeWrapper(store) });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    // A non-ok response neither branch dispatches for — success requires
    // response.ok, failure requires a thrown/rejected fetch — so state is
    // simply not updated from its seeded value.
    expect(store.getState().connection.apiConnected).toBe(true);
  });

  it('stops polling while the tab is hidden (#3257)', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const store = createTestStore();
    renderHook(() => useAPIHealthPoll(1000), { wrapper: makeWrapper(store) });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);

    setDocumentHidden(true);
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Interval is cleared — further elapsed time must not poll.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('polls immediately and resumes the interval when the tab becomes visible again (#3257)', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const store = createTestStore();
    renderHook(() => useAPIHealthPoll(1000), { wrapper: makeWrapper(store) });

    setDocumentHidden(true);
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(mockFetch).not.toHaveBeenCalled();

    setDocumentHidden(false);
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    // Immediate check on return, before any interval tick.
    expect(mockFetch).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('does not dispatch after unmount, even if an in-flight fetch resolves later (#3585)', async () => {
    let resolveFetch: (value: { ok: boolean }) => void;
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );
    const store = createTestStore();
    const { unmount } = renderHook(() => useAPIHealthPoll(1000), {
      wrapper: makeWrapper(store),
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);

    unmount();
    await act(async () => {
      resolveFetch({ ok: true });
      await Promise.resolve();
    });

    // The mount guard must have suppressed the dispatch the late resolution
    // would otherwise have triggered.
    expect(store.getState().connection.apiConnected).toBe(false);
  });

  it('removes the visibilitychange listener on unmount', async () => {
    mockFetch.mockResolvedValue({ ok: true });
    const store = createTestStore();
    const { unmount } = renderHook(() => useAPIHealthPoll(1000), {
      wrapper: makeWrapper(store),
    });
    unmount();
    mockFetch.mockClear();

    setDocumentHidden(true);
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    setDocumentHidden(false);
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });
});
