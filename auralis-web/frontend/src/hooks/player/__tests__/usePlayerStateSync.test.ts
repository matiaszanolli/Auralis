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
import { ReactNode, createElement } from 'react';
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
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(Provider, { store, children });
  };
}

// ============================================================================
// Shared mock infrastructure
// ============================================================================

let playerStateHandler: ((message: any) => void) | null = null;
let positionChangedHandler: ((message: any) => void) | null = null;
// All captured handlers keyed by message type, so discrete-event tests (#4144)
// can fire any subscribed type without a dedicated module-level variable.
const handlers: Record<string, (message: any) => void> = {};
const mockUnsubscribe = vi.fn();

/**
 * Build a complete WebSocketContextValue mock covering ALL fields, so adding a
 * new context method doesn't silently break these tests with `undefined is not
 * a function` (#3965). Pass `overrides` to customize specific fields.
 */
function makeMockWsContext(
  overrides: Partial<ReturnType<typeof WebSocketContextModule.useWebSocketContext>> = {}
): ReturnType<typeof WebSocketContextModule.useWebSocketContext> {
  return {
    isConnected: true,
    connectionStatus: 'connected',
    subscribe: vi.fn(() => mockUnsubscribe),
    subscribeAll: vi.fn(() => mockUnsubscribe),
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    setResumePositionGetter: vi.fn(),
    reissueActiveStreamAs: vi.fn(() => false),
    ...overrides,
  };
}

function setupWebSocketMock() {
  playerStateHandler = null;
  positionChangedHandler = null;
  for (const key of Object.keys(handlers)) delete handlers[key];
  mockUnsubscribe.mockReset();

  vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue(
    makeMockWsContext({
      subscribe: vi.fn((type: string, handler: (msg: any) => void) => {
        handlers[type] = handler;
        if (type === 'player_state') {
          playerStateHandler = handler;
        } else if (type === 'position_changed') {
          positionChangedHandler = handler;
        }
        return mockUnsubscribe;
      }) as any,
    })
  );
}

/** Fire an arbitrary subscribed message type (#4144 discrete events). */
function fire(type: string, data: Record<string, any>) {
  act(() => {
    handlers[type]!({ data });
  });
}

function firePlayerState(data: Record<string, any>) {
  act(() => {
    playerStateHandler!({ data });
  });
}

function firePositionChanged(data: Record<string, any>) {
  act(() => {
    positionChangedHandler!({ data });
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
  artwork_url: 'https://example.com/art.jpg',
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
    // Eight subscriptions are registered (player_state + position_changed (#3937)
    // + playback_started/resumed/paused/stopped + volume_changed + track_changed
    // (#4144)), so all eight unsubscribe callbacks fire on unmount.
    expect(mockUnsubscribe).toHaveBeenCalledTimes(8);
  });

  it('does not throw when subscribe is not available', () => {
    vi.mocked(WebSocketContextModule.useWebSocketContext).mockReturnValue(
      makeMockWsContext({
        isConnected: false,
        connectionStatus: 'disconnected',
        subscribe: undefined as any,
      })
    );

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

  it('maps artwork_url to artworkUrl', () => {
    firePlayerState({ current_track: { ...backendTrack, artwork_url: 'https://cdn.example.com/cover.png' } });

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

  it('applies duration before current_time so position is not clamped to a stale duration (#3936)', () => {
    // Cold start: store.duration is 0. A single message carrying both fields
    // must set duration FIRST, otherwise setCurrentTime clamps 120 → 0.
    firePlayerState({ current_time: 120, duration: 300 });
    expect(store.getState().player.duration).toBe(300);
    expect(store.getState().player.currentTime).toBe(120);
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
    { id: 1, title: 'Track One', artist: 'Artist A', album: 'Album A', duration: 180, artwork_url: 'https://example.com/1.jpg' },
    { id: 2, title: 'Track Two', artist: 'Artist B', album: 'Album B', duration: 240, artwork_url: 'https://example.com/2.jpg' },
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

  it('maps artwork_url to artworkUrl for each queue track', () => {
    firePlayerState({ queue: backendQueueTracks });

    const { tracks } = store.getState().queue;
    expect(tracks[0].artworkUrl).toBe('https://example.com/1.jpg');
    expect(tracks[1].artworkUrl).toBe('https://example.com/2.jpg');
  });

  it('defaults album to empty string for queue tracks when missing', () => {
    const noAlbumTracks = [{ id: 5, title: 'T', artist: 'A', duration: 100, artwork_url: null }];
    firePlayerState({ queue: noAlbumTracks });

    expect(store.getState().queue.tracks[0].album).toBe('');
  });

  it('defaults duration to 0 for queue tracks when missing', () => {
    const noDurationTracks = [{ id: 6, title: 'T', artist: 'A', album: 'X', artwork_url: null }];
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
            { id: 1, title: 'T1', artist: 'A', album: '', duration: 100, artwork_url: null },
            { id: 2, title: 'T2', artist: 'A', album: '', duration: 100, artwork_url: null },
            { id: 3, title: 'T3', artist: 'A', album: '', duration: 100, artwork_url: null },
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
// shuffle_enabled / repeat_mode (issue #3934 — the reconnect snapshot sync
// added in #3586 had zero test coverage)
// ============================================================================

describe('usePlayerStateSync – shuffle_enabled / repeat_mode', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sets isShuffled from shuffle_enabled', () => {
    firePlayerState({ shuffle_enabled: true });
    expect(store.getState().queue.isShuffled).toBe(true);
  });

  it('sets isShuffled back to false', () => {
    firePlayerState({ shuffle_enabled: true });
    firePlayerState({ shuffle_enabled: false });
    expect(store.getState().queue.isShuffled).toBe(false);
  });

  it('does not dispatch isShuffled when shuffle_enabled is absent', () => {
    firePlayerState({ is_playing: true });
    expect(store.getState().queue.isShuffled).toBe(false); // unchanged default
  });

  it('does not dispatch isShuffled when shuffle_enabled is undefined', () => {
    firePlayerState({ shuffle_enabled: undefined });
    expect(store.getState().queue.isShuffled).toBe(false);
  });

  it('sets repeatMode from repeat_mode', () => {
    firePlayerState({ repeat_mode: 'all' });
    expect(store.getState().queue.repeatMode).toBe('all');
  });

  it('sets repeatMode to "one"', () => {
    firePlayerState({ repeat_mode: 'one' });
    expect(store.getState().queue.repeatMode).toBe('one');
  });

  it('does not dispatch repeatMode when repeat_mode is absent', () => {
    firePlayerState({ is_playing: true });
    expect(store.getState().queue.repeatMode).toBe('off'); // unchanged default
  });

  it('does not dispatch repeatMode when repeat_mode is an invalid value (#4159)', () => {
    firePlayerState({ repeat_mode: 'bogus' });
    expect(store.getState().queue.repeatMode).toBe('off');
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

describe('usePlayerStateSync – position_changed (#3937)', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // setCurrentTime clamps to [0, duration], so a duration must be present for
  // position ticks to apply (the clamp-on-cold-start gap is tracked separately
  // as #3936). Seed a duration via player_state first, mirroring real playback.
  it('updates redux currentTime from a position_changed tick', () => {
    firePlayerState({ duration: 300 });
    firePositionChanged({ position: 42.5 });
    expect(store.getState().player.currentTime).toBe(42.5);
  });

  it('applies sequential position ticks (1Hz playback)', () => {
    firePlayerState({ duration: 300 });
    firePositionChanged({ position: 1 });
    firePositionChanged({ position: 2 });
    firePositionChanged({ position: 3 });
    expect(store.getState().player.currentTime).toBe(3);
  });

  it('ignores non-finite or missing position values', () => {
    firePlayerState({ duration: 300 });
    firePositionChanged({ position: 10 });
    firePositionChanged({ position: NaN });
    firePositionChanged({});
    // currentTime stays at the last valid value, not NaN/undefined
    expect(store.getState().player.currentTime).toBe(10);
  });
});

// ============================================================================
// Discrete playback events (#4144)
// ============================================================================

describe('usePlayerStateSync – discrete playback events (#4144)', () => {
  let store: TestStore;

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('subscribes to all discrete player events on mount', () => {
    const { subscribe } = vi.mocked(WebSocketContextModule.useWebSocketContext)();
    for (const type of [
      'playback_started',
      'playback_resumed',
      'playback_paused',
      'playback_stopped',
      'volume_changed',
      'track_changed',
    ]) {
      expect(vi.mocked(subscribe)).toHaveBeenCalledWith(type, expect.any(Function));
    }
  });

  it('playback_paused sets isPlaying false without a player_state snapshot', () => {
    firePlayerState({ is_playing: true });
    expect(store.getState().player.isPlaying).toBe(true);

    fire('playback_paused', { state: 'paused' });
    expect(store.getState().player.isPlaying).toBe(false);
  });

  it('playback_stopped sets isPlaying false', () => {
    firePlayerState({ is_playing: true });
    fire('playback_stopped', { state: 'stopped' });
    expect(store.getState().player.isPlaying).toBe(false);
  });

  it('playback_started sets isPlaying true', () => {
    fire('playback_started', { state: 'playing' });
    expect(store.getState().player.isPlaying).toBe(true);
  });

  it('playback_resumed sets isPlaying true', () => {
    firePlayerState({ is_playing: false });
    fire('playback_resumed', { state: 'playing' });
    expect(store.getState().player.isPlaying).toBe(true);
  });

  it('volume_changed updates volume (0-100 scale)', () => {
    fire('volume_changed', { volume: 35 });
    expect(store.getState().player.volume).toBe(35);
  });

  it('volume_changed ignores non-finite values', () => {
    fire('volume_changed', { volume: 60 });
    fire('volume_changed', { volume: NaN });
    fire('volume_changed', {});
    expect(store.getState().player.volume).toBe(60);
  });
});

// ============================================================================
// track_changed → currentIndex / currentTrack (#4144)
// ============================================================================

describe('usePlayerStateSync – track_changed (#4144)', () => {
  let store: TestStore;

  const queueTracks = [
    { id: 1, title: 'T1', artist: 'A', album: '', duration: 100, artwork_url: null },
    { id: 2, title: 'T2', artist: 'B', album: '', duration: 110, artwork_url: null },
    { id: 3, title: 'T3', artist: 'C', album: '', duration: 120, artwork_url: null },
  ];

  beforeEach(() => {
    setupWebSocketMock();
    store = createTestStore();
    renderHook(() => usePlayerStateSync(), { wrapper: makeWrapper(store) });
    // Seed the synced queue so track_changed can resolve track_index → track.
    firePlayerState({ queue: queueTracks, queue_index: 0 });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("updates currentIndex and currentTrack on a 'next' skip with track_index", () => {
    fire('track_changed', { action: 'next', track_index: 1 });
    expect(store.getState().queue.currentIndex).toBe(1);
    expect(store.getState().player.currentTrack?.id).toBe(2);
  });

  it("updates state on a 'previous' skip", () => {
    fire('track_changed', { action: 'next', track_index: 2 });
    fire('track_changed', { action: 'previous', track_index: 1 });
    expect(store.getState().queue.currentIndex).toBe(1);
    expect(store.getState().player.currentTrack?.id).toBe(2);
  });

  it("updates state on a 'jumped' action", () => {
    fire('track_changed', { action: 'jumped', track_index: 2 });
    expect(store.getState().queue.currentIndex).toBe(2);
    expect(store.getState().player.currentTrack?.id).toBe(3);
  });

  it('ignores track_changed with no track_index (reconciles via player_state)', () => {
    fire('track_changed', { action: 'next', track_index: 1 });
    fire('track_changed', { action: 'next' }); // legacy/missing index
    // currentIndex stays at the last resolved value, not reset/NaN
    expect(store.getState().queue.currentIndex).toBe(1);
    expect(store.getState().player.currentTrack?.id).toBe(2);
  });

  it('ignores out-of-range track_index', () => {
    fire('track_changed', { action: 'jumped', track_index: 99 });
    expect(store.getState().queue.currentIndex).toBe(0); // unchanged seed
    expect(store.getState().player.currentTrack).toBeNull();
  });
});
