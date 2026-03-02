/**
 * usePlayerStateSync Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Verifies that every backend field in a `player_state` WebSocket message is
 * correctly mapped to the corresponding Redux action / state value.
 *
 * Architecture under test:
 *   Backend → WebSocket 'player_state' broadcast → usePlayerStateSync → Redux
 *
 * Test strategy:
 *   - Mock useWebSocketContext to capture the subscribe handler
 *   - Wrap the hook in a real (in-memory) Redux store
 *   - Fire synthetic player_state messages via the captured handler
 *   - Assert the resulting store state rather than spy call details
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { usePlayerStateSync } from '../usePlayerStateSync';
import playerReducer from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import * as WebSocketContextModule from '@/contexts/WebSocketContext';

// ============================================================================
// Mock WebSocket context
// ============================================================================

vi.mock('@/contexts/WebSocketContext', async (importOriginal) => {
  const actual = await importOriginal<typeof WebSocketContextModule>();
  return { ...actual, useWebSocketContext: vi.fn() };
});

// ============================================================================
// Test helpers
// ============================================================================

function createTestStore() {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({ serializableCheck: false }),
  });
}

type TestStore = ReturnType<typeof createTestStore>;

function makeWrapper(store: TestStore) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(Provider, { store, children });
  };
}

// ============================================================================
// Shared mock infrastructure
// ============================================================================

let playerStateHandler: ((message: any) => void) | null = null;
const mockUnsubscribe = vi.fn();

function setupWebSocketMock() {
  playerStateHandler = null;
  mockUnsubscribe.mockReset();

  vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue({
    isConnected: true,
    connectionStatus: 'connected',
    subscribe: vi.fn((type: string, handler: (msg: any) => void) => {
      if (type === 'player_state') {
        playerStateHandler = handler;
      }
      return mockUnsubscribe;
    }),
    subscribeAll: vi.fn(() => mockUnsubscribe),
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  });
}

function firePlayerState(data: Record<string, any>) {
  act(() => {
    playerStateHandler!({ data });
  });
}

// ============================================================================
// Sample fixtures
// ============================================================================

const backendTrack = {
  id: 42,
  title: 'Stairway to Heaven',
  artist: 'Led Zeppelin',
  album: 'Led Zeppelin IV',
  duration: 482,
  album_art: 'https://example.com/art.jpg',
};

const expectedReduxTrack = {
  id: 42,
  title: 'Stairway to Heaven',
  artist: 'Led Zeppelin',
  album: 'Led Zeppelin IV',
  duration: 482,
  artworkUrl: 'https://example.com/art.jpg',
};

// ============================================================================
// Subscription lifecycle
// ============================================================================

describe('usePlayerStateSync – subscription lifecycle', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('subscribes to player_state on mount', () => {
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });

    const { subscribe } = vi.mocked(WebSocketContextModule.useWebSocketContext)();
    expect(vi.mocked(subscribe)).toHaveBeenCalledWith('player_state', expect.any(Function));
  });

  it('calls unsubscribe on unmount', () => {
    const { unmount } = renderHook(() => usePlayerStateSync(), {
      wrapper: makeWrapper(store),
    });
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledOnce();
  });

  it('does not throw when subscribe is not available', () => {
    vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue({
      isConnected: false,
      connectionStatus: 'disconnected',
      subscribe: undefined as any,
      subscribeAll: vi.fn(() => () => {}),
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
    });

    expect(() =>
      renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) })
    ).not.toThrow();
  });
});

// ============================================================================
// current_track mapping
// ============================================================================

describe('usePlayerStateSync – current_track', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('maps all backend track fields to Redux Track shape', () => {
    firePlayerState({ current_track: backendTrack });

    expect(store.getState().player.currentTrack).toEqual(expectedReduxTrack);
  });

  it('maps album_art to artworkUrl', () => {
    firePlayerState({ current_track: { ...backendTrack, album_art: 'https://cdn.example.com/cover.png' } });

    expect(store.getState().player.currentTrack?.artworkUrl).toBe('https://cdn.example.com/cover.png');
  });

  it('defaults album to empty string when missing', () => {
    const { album: _unused, ...trackWithoutAlbum } = backendTrack;
    firePlayerState({ current_track: trackWithoutAlbum });

    expect(store.getState().player.currentTrack?.album).toBe('');
  });

  it('defaults duration to 0 when missing', () => {
    const { duration: _unused, ...trackWithoutDuration } = backendTrack;
    firePlayerState({ current_track: trackWithoutDuration });

    expect(store.getState().player.currentTrack?.duration).toBe(0);
  });

  it('sets currentTrack to null when backend sends null', () => {
    // First set a track
    firePlayerState({ current_track: backendTrack });
    expect(store.getState().player.currentTrack).not.toBeNull();

    // Then clear it
    firePlayerState({ current_track: null });
    expect(store.getState().player.currentTrack).toBeNull();
  });

  it('does not dispatch setCurrentTrack when field is absent', () => {
    firePlayerState({ is_playing: true }); // no current_track key

    expect(store.getState().player.currentTrack).toBeNull(); // unchanged default
  });

  it('does not dispatch setCurrentTrack when field is undefined', () => {
    firePlayerState({ current_track: undefined });

    expect(store.getState().player.currentTrack).toBeNull();
  });
});

// ============================================================================
// is_playing mapping
// ============================================================================

describe('usePlayerStateSync – is_playing', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets isPlaying to true', () => {
    firePlayerState({ is_playing: true });
    expect(store.getState().player.isPlaying).toBe(true);
  });

  it('sets isPlaying to false', () => {
    firePlayerState({ is_playing: true });
    firePlayerState({ is_playing: false });
    expect(store.getState().player.isPlaying).toBe(false);
  });

  it('does not dispatch when field is absent', () => {
    firePlayerState({ volume: 50 }); // no is_playing
    expect(store.getState().player.isPlaying).toBe(false); // unchanged default
  });

  it('does not dispatch when field is undefined', () => {
    firePlayerState({ is_playing: undefined });
    expect(store.getState().player.isPlaying).toBe(false);
  });
});

// ============================================================================
// current_time mapping
// ============================================================================

describe('usePlayerStateSync – current_time', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets currentTime', () => {
    // Set duration first so setCurrentTime clamp doesn't cap at 0
    firePlayerState({ duration: 300 });
    firePlayerState({ current_time: 123.45 });
    expect(store.getState().player.currentTime).toBe(123.45);
  });

  it('does not dispatch when field is absent', () => {
    firePlayerState({ is_playing: false });
    expect(store.getState().player.currentTime).toBe(0);
  });

  it('does not dispatch when field is undefined', () => {
    firePlayerState({ current_time: undefined });
    expect(store.getState().player.currentTime).toBe(0);
  });
});

// ============================================================================
// duration mapping
// ============================================================================

describe('usePlayerStateSync – duration', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets duration', () => {
    firePlayerState({ duration: 300 });
    expect(store.getState().player.duration).toBe(300);
  });

  it('sets duration to zero', () => {
    firePlayerState({ duration: 300 });
    firePlayerState({ duration: 0 });
    expect(store.getState().player.duration).toBe(0);
  });

  it('does not dispatch when field is absent', () => {
    firePlayerState({ is_playing: false });
    expect(store.getState().player.duration).toBe(0);
  });
});

// ============================================================================
// volume mapping
// ============================================================================

describe('usePlayerStateSync – volume', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets volume', () => {
    firePlayerState({ volume: 80 });
    expect(store.getState().player.volume).toBe(80);
  });

  it('clamps volume above 100 to 100 (via reducer)', () => {
    firePlayerState({ volume: 120 });
    expect(store.getState().player.volume).toBe(100);
  });

  it('clamps volume below 0 to 0 (via reducer)', () => {
    firePlayerState({ volume: -10 });
    expect(store.getState().player.volume).toBe(0);
  });

  it('does not dispatch when field is absent', () => {
    firePlayerState({ is_playing: false });
    expect(store.getState().player.volume).toBe(80); // initial default (issue #2251)
  });
});

// ============================================================================
// is_muted mapping
// ============================================================================

describe('usePlayerStateSync – is_muted', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets isMuted to true', () => {
    firePlayerState({ is_muted: true });
    expect(store.getState().player.isMuted).toBe(true);
  });

  it('sets isMuted to false', () => {
    firePlayerState({ is_muted: true });
    firePlayerState({ is_muted: false });
    expect(store.getState().player.isMuted).toBe(false);
  });

  it('does not dispatch when field is absent', () => {
    firePlayerState({ volume: 60 });
    expect(store.getState().player.isMuted).toBe(false);
  });

  it('does not dispatch when field is undefined', () => {
    firePlayerState({ is_muted: undefined });
    expect(store.getState().player.isMuted).toBe(false);
  });
});

// ============================================================================
// current_preset mapping
// ============================================================================

describe('usePlayerStateSync – current_preset', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets preset', () => {
    firePlayerState({ current_preset: 'warm' });
    expect(store.getState().player.preset).toBe('warm');
  });

  it('does not dispatch when field is absent (falsy)', () => {
    firePlayerState({ is_playing: false });
    expect(store.getState().player.preset).toBe('adaptive'); // default
  });

  it('does not dispatch when field is empty string (falsy)', () => {
    firePlayerState({ current_preset: '' });
    expect(store.getState().player.preset).toBe('adaptive'); // default
  });
});

// ============================================================================
// queue mapping
// ============================================================================

describe('usePlayerStateSync – queue', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const backendQueueTracks = [
    { id: 1, title: 'Track One', artist: 'Artist A', album: 'Album A', duration: 180, album_art: 'https://example.com/1.jpg' },
    { id: 2, title: 'Track Two', artist: 'Artist B', album: 'Album B', duration: 240, album_art: 'https://example.com/2.jpg' },
  ];

  it('maps queue tracks to Redux Track shape', () => {
    firePlayerState({ queue: backendQueueTracks });

    const { tracks } = store.getState().queue;
    expect(tracks).toHaveLength(2);
    expect(tracks[0]).toEqual({
      id: 1,
      title: 'Track One',
      artist: 'Artist A',
      album: 'Album A',
      duration: 180,
      artworkUrl: 'https://example.com/1.jpg',
    });
  });

  it('maps album_art to artworkUrl for each queue track', () => {
    firePlayerState({ queue: backendQueueTracks });

    const { tracks } = store.getState().queue;
    expect(tracks[0].artworkUrl).toBe('https://example.com/1.jpg');
    expect(tracks[1].artworkUrl).toBe('https://example.com/2.jpg');
  });

  it('defaults album to empty string for queue tracks when missing', () => {
    const noAlbumTracks = [{ id: 5, title: 'T', artist: 'A', duration: 100, album_art: null }];
    firePlayerState({ queue: noAlbumTracks });

    expect(store.getState().queue.tracks[0].album).toBe('');
  });

  it('defaults duration to 0 for queue tracks when missing', () => {
    const noDurationTracks = [{ id: 6, title: 'T', artist: 'A', album: 'X', album_art: null }];
    firePlayerState({ queue: noDurationTracks });

    expect(store.getState().queue.tracks[0].duration).toBe(0);
  });

  it('dispatches setQueue with empty array to clear queue', () => {
    firePlayerState({ queue: backendQueueTracks });
    expect(store.getState().queue.tracks).toHaveLength(2);

    firePlayerState({ queue: [] });
    expect(store.getState().queue.tracks).toHaveLength(0);
  });

  it('does not dispatch setQueue when queue is not an array', () => {
    firePlayerState({ queue: 'not-an-array' });
    expect(store.getState().queue.tracks).toHaveLength(0); // unchanged
  });

  it('does not dispatch setQueue when field is absent', () => {
    firePlayerState({ is_playing: false });
    expect(store.getState().queue.tracks).toHaveLength(0);
  });
});

// ============================================================================
// queue_index mapping
// ============================================================================

describe('usePlayerStateSync – queue_index', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });

    // Seed queue so setCurrentIndex bounds check passes (index must be < length)
    act(() => {
      playerStateHandler!({
        data: {
          queue: [
            { id: 1, title: 'T1', artist: 'A', album: '', duration: 100, album_art: null },
            { id: 2, title: 'T2', artist: 'A', album: '', duration: 100, album_art: null },
            { id: 3, title: 'T3', artist: 'A', album: '', duration: 100, album_art: null },
          ],
        },
      });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets queue currentIndex', () => {
    firePlayerState({ queue_index: 2 });
    expect(store.getState().queue.currentIndex).toBe(2);
  });

  it('sets queue currentIndex to 0', () => {
    firePlayerState({ queue_index: 2 });
    firePlayerState({ queue_index: 0 });
    expect(store.getState().queue.currentIndex).toBe(0);
  });

  it('does not dispatch when field is absent', () => {
    firePlayerState({ is_playing: true });
    expect(store.getState().queue.currentIndex).toBe(0); // unchanged default
  });

  it('does not dispatch when field is undefined', () => {
    firePlayerState({ queue_index: undefined });
    expect(store.getState().queue.currentIndex).toBe(0);
  });
});

// ============================================================================
// Full message: all fields together
// ============================================================================

describe('usePlayerStateSync – complete player_state message', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('syncs all 9 fields from a single message', () => {
    firePlayerState({
      current_track: backendTrack,
      is_playing: true,
      current_time: 30,
      duration: 482,
      volume: 75,
      is_muted: false,
      current_preset: 'punchy',
      queue: [backendTrack],
      queue_index: 0,
    });

    const playerState = store.getState().player;
    const queueState = store.getState().queue;

    expect(playerState.currentTrack).toEqual(expectedReduxTrack);
    expect(playerState.isPlaying).toBe(true);
    expect(playerState.currentTime).toBe(30);
    expect(playerState.duration).toBe(482);
    expect(playerState.volume).toBe(75);
    expect(playerState.isMuted).toBe(false);
    expect(playerState.preset).toBe('punchy');
    expect(queueState.tracks).toHaveLength(1);
    expect(queueState.currentIndex).toBe(0);
  });
});

// ============================================================================
// Empty / unknown messages
// ============================================================================

describe('usePlayerStateSync – edge cases', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('leaves state untouched on empty data object', () => {
    const before = store.getState();
    firePlayerState({});
    expect(store.getState().player).toEqual(before.player);
    expect(store.getState().queue).toEqual(before.queue);
  });

  it('does not throw when message.data is undefined', () => {
    expect(() => {
      act(() => {
        playerStateHandler!({ data: undefined });
      });
    }).not.toThrow();
  });

  it('does not throw when message.data has unknown extra fields', () => {
    expect(() => {
      firePlayerState({ unknown_field: 'value', another: 42 });
    }).not.toThrow();
  });

  it('handles multiple sequential messages correctly (last write wins)', () => {
    firePlayerState({ is_playing: true });
    firePlayerState({ is_playing: false });
    firePlayerState({ is_playing: true });

    expect(store.getState().player.isPlaying).toBe(true);
  });
});
