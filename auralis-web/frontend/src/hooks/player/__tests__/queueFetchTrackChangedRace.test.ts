/**
 * Regression: track_changed racing the REST-seeded queue (#5009)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * useQueueFetch used to dispatch `GET /api/player/queue`'s raw snake_case
 * tracks straight into the queue slice via an unsafe cast. The `track_changed`
 * WS handler in usePlayerStateSync resolves a skip/auto-advance by indexing
 * directly into `store.getState().queue.tracks` and dispatching that object
 * as-is — no transform of its own. If `track_changed` fires before the first
 * `player_state` snapshot has overwritten the REST-seeded queue (cold start,
 * a `--dev` backend reload, or a WS reconnect racing a REST refetch),
 * `currentTrack` used to end up with `.artwork_url` where every consumer
 * (TrackInfo.tsx) reads `.artworkUrl` — blank Now Playing artwork, no error.
 *
 * This mounts both hooks against one shared store and drives that exact
 * sequence: REST queue resolves, then track_changed fires before any
 * player_state snapshot.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { ReactNode, createElement } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { useQueueFetch } from '../useQueueFetch';
import { usePlayerStateSync } from '../usePlayerStateSync';
import playerReducer from '@/store/slices/playerSlice';
import queueReducer, { selectQueueTracks } from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import * as useRestAPIModule from '@/hooks/api/useRestAPI';
import * as WebSocketContextModule from '@/contexts/WebSocketContext';

vi.mock('@/contexts/WebSocketContext', async (importOriginal) => {
  const actual = await importOriginal<typeof WebSocketContextModule>();
  return { ...actual, useWebSocketContext: vi.fn() };
});

function createStore() {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware({ serializableCheck: false }),
  });
}

type TestStore = ReturnType<typeof createStore>;

function wrapperFor(store: TestStore) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(Provider, { store, children });
  };
}

function mockRestAPI(get: ReturnType<typeof vi.fn>) {
  vi.spyOn(useRestAPIModule, 'useRestAPI').mockReturnValue({
    get,
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    clearError: vi.fn(),
    isLoading: false,
    error: null,
  } as any);
}

let trackChangedHandler: ((message: any) => void) | null = null;

function mockWebSocketContext() {
  trackChangedHandler = null;
  vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue({
    isConnected: true,
    connectionStatus: 'connected',
    subscribe: vi.fn((type: string, handler: (msg: any) => void) => {
      if (type === 'track_changed') trackChangedHandler = handler;
      return vi.fn();
    }) as any,
    subscribeAll: vi.fn(() => vi.fn()),
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    setResumePositionGetter: vi.fn(),
    reissueActiveStreamAs: vi.fn(() => false),
  } as any);
}

describe('track_changed racing the REST-seeded queue (#5009)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('gives currentTrack.artworkUrl even when track_changed fires before any player_state snapshot', async () => {
    mockWebSocketContext();
    mockRestAPI(vi.fn().mockResolvedValue({
      tracks: [
        { id: 1, title: 'A', artist: 'X', album: 'Al', duration: 180, artwork_url: '/art/1.jpg' },
        { id: 2, title: 'B', artist: 'Y', album: 'Bl', duration: 200, artwork_url: '/art/2.jpg' },
      ],
      current_index: 0,
      shuffle_enabled: false,
      repeat_mode: 'off',
    }));

    const store = createStore();
    const wrapper = wrapperFor(store);
    renderHook(() => {
      useQueueFetch();
      usePlayerStateSync();
    }, { wrapper });

    // Wait for the REST-seeded queue to land -- this is the state
    // track_changed will index into, with no player_state snapshot having
    // run yet.
    await waitFor(() => {
      expect(selectQueueTracks(store.getState())).toHaveLength(2);
    });

    expect(trackChangedHandler).not.toBeNull();
    act(() => {
      trackChangedHandler!({ data: { action: 'next', track_index: 1 } });
    });

    expect(store.getState().player.currentTrack).toMatchObject({
      id: 2,
      artworkUrl: '/art/2.jpg',
    });
    expect(store.getState().player.currentTrack).not.toHaveProperty('artwork_url');
  });
});
