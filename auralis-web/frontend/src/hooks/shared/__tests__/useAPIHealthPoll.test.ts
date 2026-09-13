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
import { DEFAULT_TIMEOUT_MS } from '@/utils/apiRequest';
import { useAPIHealthPoll } from '../useAPIHealthPoll';

let mockFetch: ReturnType<typeof vi.fn>;

/**
 * The poll goes through `get()` (#5019), which parses the response body, so a
 * mock response needs a `json()` — a bare `{ ok: true }` reads as a transport
 * failure rather than a healthy backend.
 */
const okResponse = () => ({ ok: true, status: 200, json: async () => ({ status: 'ok' }) });

/** A request that never settles until the transport's timeout aborts it. */
const hangingFetch = () =>
  vi.fn((_url: string, init: RequestInit) =>
    new Promise((_resolve, reject) => {
      init.signal?.addEventListener('abort', () => {
        reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
      });
    }));

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
    mockFetch.mockResolvedValue(okResponse());
    const store = createTestStore();
    renderHook(() => useAPIHealthPoll(5000), { wrapper: makeWrapper(store) });

    // The first poll only fires via the interval, not synchronously on mount.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    // #5019: through `get()`, so the init now also carries the transport's
    // headers and its timeout-composed AbortSignal.
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/health',
      expect.objectContaining({ method: 'GET', signal: expect.any(AbortSignal) })
    );
    expect(store.getState().connection.apiConnected).toBe(true);
    expect(typeof store.getState().connection.latency).toBe('number');
  });

  it('fires on every interval tick', async () => {
    mockFetch.mockResolvedValue(okResponse());
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

  it('leaves the connection state alone when the response is not ok', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: async () => ({ detail: 'degraded' }),
    });
    const store = createTestStore({
      connection: { apiConnected: true },
    });
    renderHook(() => useAPIHealthPoll(5000), { wrapper: makeWrapper(store) });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    // A non-ok response neither branch dispatches for — success required
    // response.ok, failure required a thrown/rejected fetch — so state is
    // simply not updated from its seeded value. #5019 preserved this: `get()`
    // throws on a non-2xx, and the catch re-narrows to transport-level
    // failures (statusCode 0) before marking the API disconnected.
    expect(store.getState().connection.apiConnected).toBe(true);
  });

  it('stops polling while the tab is hidden (#3257)', async () => {
    mockFetch.mockResolvedValue(okResponse());
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
    mockFetch.mockResolvedValue(okResponse());
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
    let resolveFetch: (value: unknown) => void;
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
      resolveFetch(okResponse());
      await Promise.resolve();
    });

    // The mount guard must have suppressed the dispatch the late resolution
    // would otherwise have triggered.
    expect(store.getState().connection.apiConnected).toBe(false);
  });

  it('gives up on a hung request after the shared transport timeout (#5019)', async () => {
    // The pre-#5019 bare fetch() had no timeout at all: a stalled backend left
    // one request pending per interval tick, forever, and the indicator kept
    // reporting whatever it last saw.
    mockFetch = hangingFetch();
    vi.stubGlobal('fetch', mockFetch);
    const store = createTestStore({
      connection: { apiConnected: true, latency: 42 },
    });
    renderHook(() => useAPIHealthPoll(5000), { wrapper: makeWrapper(store) });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    // Still in flight — nothing has been decided yet.
    expect(store.getState().connection.apiConnected).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS);
    });

    expect(store.getState().connection.apiConnected).toBe(false);
    expect(store.getState().connection.latency).toBe(0);
  });

  it('removes the visibilitychange listener on unmount', async () => {
    mockFetch.mockResolvedValue(okResponse());
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
