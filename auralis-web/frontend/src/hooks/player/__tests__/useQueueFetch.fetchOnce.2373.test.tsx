/**
 * The initial queue fetch runs once, however often its consumer re-renders (#2340/#2373, #6598).
 *
 * The HIGH bug: the fetch effect depended on something its own result changed, so seeding the
 * queue re-rendered the consumer, re-ran the effect and fetched again, forever. The effect now
 * depends on `[get, dispatch]`, so the guard is behavioural: with the REAL useRestAPI (whose `get`
 * must stay identity-stable) and a consumer that re-renders on every queue change, exactly one GET
 * is made. This replaces a Python source-grep that had gone red/vacuous after the hook was split.
 */

import { ReactNode, createElement } from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { Provider, useSelector } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { useQueueFetch } from '../useQueueFetch';
import queueReducer, { selectQueueTracks } from '@/store/slices/queueSlice';

const QUEUE = {
  tracks: [
    { id: 1, title: 'One', artist: 'A', album: 'X', duration: 100 },
    { id: 2, title: 'Two', artist: 'B', album: 'Y', duration: 200 },
  ],
  current_index: 0,
  shuffle_enabled: false,
  repeat_mode: 'off',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useQueueFetch – fetches once (#2373)', () => {
  it('makes one GET across the re-renders its own dispatch and the parent cause', async () => {
    // A reintroduced loop must fail here, not spin: past a few calls the server stops answering.
    const fetchMock = vi.fn((_input: RequestInfo | URL, _init?: RequestInit): Promise<Response> =>
      fetchMock.mock.calls.length > 3
        ? new Promise<Response>(() => {})
        : Promise.resolve(new Response(JSON.stringify(QUEUE), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })));
    vi.stubGlobal('fetch', fetchMock);
    const store = configureStore({ reducer: { queue: queueReducer } });
    const wrapper = ({ children }: { children: ReactNode }) => createElement(Provider, { store, children });

    // The consumer re-renders whenever the queue it seeded changes - the loop's trigger.
    const { result, rerender } = renderHook(() => {
      useQueueFetch();
      return useSelector(selectQueueTracks);
    }, { wrapper });

    await waitFor(() => expect(result.current).toHaveLength(2));
    for (let i = 0; i < 5; i++) rerender();
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });

    const queueGets = fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/player/queue'));
    expect(queueGets).toHaveLength(1);
  });
});
