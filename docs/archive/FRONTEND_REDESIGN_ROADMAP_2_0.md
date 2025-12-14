# 🎨 Frontend Complete Redesign Roadmap (v2.0)

**Created:** November 30, 2025
**Priority:** 🔴 **CRITICAL - Main Priority**
**Timeline:** 4-6 weeks (Phase 1-3 in parallel, Phase 4 sequential)
**Target Release:** 1.2.0 (March 2026)
**Status:** Planning Phase - Ready for Implementation

---

## 📋 Executive Summary

The current frontend is heavily fragmented due to iterative patching and branching without a solid backend API. With the new **unified streaming backend** and **WebSocket protocol** now in place, we're undertaking a complete redesign to:

- **Eliminate duplicate code** across 600+ component files
- **Build from the new backend API spec** instead of adapting existing code
- **Implement modern, consistent UI** with single design system
- **Handle dynamic playback changes** (seek, skip, preset changes, auto-mastering toggle)
- **Add fingerprint caching system** for efficient track preprocessing
- **Improve memory efficiency** and rendering performance

**Key Principles:**
1. **One component at a time** - Thin, focused components (< 200 lines)
2. **Orchestrator pattern** - Thin hooks + focused presentational components
3. **Design system enforcement** - Single source of truth for all styling
4. **Test-driven refactoring** - Maintain passing tests while refactoring
5. **Feature parity first** - Match current functionality, then enhance

---

## 🎯 Phase Overview

```
Phase 0: Preparation (1 week)
  └─ Foundation: Type definitions, new hooks architecture, testing setup

Phase 1: Core Player (1.5 weeks) - PARALLEL START
  └─ Player state management, playback controls, streaming integration

Phase 2: Library Browser (1.5 weeks) - PARALLEL START
  └─ Track/album/artist views with infinite scroll, search, metadata

Phase 3: Enhancement Pane (1 week) - PARALLEL START
  └─ Audio settings, preset selector, parameter display

Phase 4: Integration & Polish (1 week) - SEQUENTIAL
  └─ State synchronization, error handling, performance optimization
```

---

## 🏗️ Phase 0: Preparation & Foundation

**Duration:** 1 week
**Deliverables:** Foundation for parallel Phase 1-3 work
**Owner:** One developer

### 0.1 WebSocket Types & Message System

**Goal:** Create single source of truth for all WebSocket types
**Files Created:**
- `src/types/websocket.ts` - Complete message type definitions
- `src/types/api.ts` - REST API request/response types
- `src/types/domain.ts` - Core domain models (Track, Album, Artist, Queue, etc.)

**Scope:**

```typescript
// Complete type definitions for all WebSocket messages
export type WebSocketMessageType =
  | 'player_state'
  | 'playback_started'
  | 'playback_paused'
  | 'playback_stopped'
  | 'track_loaded'
  | 'track_changed'
  | 'position_changed'
  | 'volume_changed'
  | 'queue_updated'
  | 'enhancement_settings_changed'
  | 'mastering_recommendation'
  | 'metadata_updated'
  | 'library_updated'
  | 'scan_progress'
  | 'scan_complete';

// Message interfaces for type-safe handling
interface WebSocketMessage<T = any> {
  type: WebSocketMessageType;
  data: T;
  timestamp?: number;
}

interface PlayerStateMessage {
  type: 'player_state';
  data: {
    currentTrack: Track | null;
    isPlaying: boolean;
    volume: number;
    position: number;
    duration: number;
    queue: Track[];
    queueIndex: number;
    gapless_enabled: boolean;
    crossfade_enabled: boolean;
    crossfade_duration: number;
  };
}

// ... (all other message types)
```

**Testing:**
- Type validation tests
- Message schema validation (Zod)
- TypeScript compilation check

---

### 0.2 New Hooks Architecture

**Goal:** Create lean, composable hooks that map 1:1 to backend API
**Files Created:**
- `src/hooks/websocket/useWebSocketSubscription.ts` - Low-level subscription
- `src/hooks/api/useRestAPI.ts` - Typed REST API calls
- `src/hooks/player/usePlayer.ts` - Player state + control (NEW - replaces usePlayerAPI)
- `src/hooks/player/usePlaybackState.ts` - Listen-only playback updates
- `src/hooks/player/usePlaybackControl.ts` - Control methods (play, pause, seek, etc.)
- `src/hooks/library/useLibrary.ts` - Library queries with caching
- `src/hooks/enhancement/useEnhancement.ts` - Enhancement settings + control
- `src/hooks/fingerprint/useFingerprintCache.ts` - Fingerprint caching

**Architecture Pattern:**

```typescript
// Low-level: WebSocket subscription
export function useWebSocketSubscription(
  messageTypes: WebSocketMessageType[],
  callback: (message: WebSocketMessage) => void
) {
  // Returns unsubscribe function
  // Auto-cleans up on unmount
}

// Mid-level: REST API calls with Zod validation
export function useRestAPI<T>() {
  const api = useMemo(() => {
    return {
      get: async (endpoint: string): Promise<T> => { /* ... */ },
      post: async (endpoint: string, data: any): Promise<T> => { /* ... */ },
      put: async (endpoint: string, data: any): Promise<T> => { /* ... */ },
      delete: async (endpoint: string): Promise<void> => { /* ... */ },
    };
  }, []);
  return api;
}

// High-level: Player composite hook
export function usePlayer() {
  const playbackState = usePlaybackState();    // Listen to WebSocket
  const controls = usePlaybackControl();       // Control methods
  const fingerprint = useFingerprintCache();   // Fingerprint cache

  return {
    // State
    currentTrack: playbackState.currentTrack,
    isPlaying: playbackState.isPlaying,
    position: playbackState.position,
    duration: playbackState.duration,
    queue: playbackState.queue,
    queueIndex: playbackState.queueIndex,

    // Control
    play: controls.play,
    pause: controls.pause,
    seek: controls.seek,
    next: controls.next,
    previous: controls.previous,
    setVolume: controls.setVolume,

    // Fingerprinting (NEW)
    getFingerprintState: fingerprint.getState,  // 'idle' | 'processing' | 'ready'
    fingerprintProgress: fingerprint.progress,  // 0-100
  };
}
```

**Key Design Decisions:**
- Single `usePlayer()` hook replaces `usePlayerAPI` + `usePlayerWithAudio` + `useUnifiedWebMAudioPlayer`
- All subscriptions auto-cleanup on unmount
- REST API calls validated with Zod
- No Redux integration initially (simpler state management)
- Fingerprint caching built into hooks from day one

---

### 0.3 Fingerprint Caching System

**Goal:** Implement preprocessing disguised as buffering
**Files Created:**
- `src/services/fingerprint/FingerprintCache.ts` - SQLite-backed cache
- `src/hooks/fingerprint/useFingerprintCache.ts` - Hook interface
- `src/services/fingerprint/FingerprintWorker.ts` - Web Worker for background processing

**Architecture:**

```typescript
// IndexedDB-backed cache (browser-local)
class FingerprintCache {
  async get(trackId: number): Promise<Fingerprint | null>;
  async set(trackId: number, fingerprint: Fingerprint): Promise<void>;
  async has(trackId: number): Promise<boolean>;
  async clear(): Promise<void>;
  async getAllKeys(): Promise<number[]>;
  async getSize(): Promise<number>; // MB
}

// Hook for component usage
export function useFingerprintCache() {
  const [state, setState] = useState<'idle' | 'processing' | 'ready'>('idle');
  const [progress, setProgress] = useState(0);

  const preprocess = useCallback(async (trackId: number) => {
    setState('processing');

    // 1. Check if cached
    const cached = await cache.get(trackId);
    if (cached) {
      setState('ready');
      return cached;
    }

    // 2. Start Web Worker to compute in background
    const worker = new Worker(new URL('../fingerprint/FingerprintWorker.ts', import.meta.url), {
      type: 'module'
    });

    worker.onmessage = (event) => {
      const { progress, data } = event.data;
      setProgress(progress);
      if (data) {
        cache.set(trackId, data);
        setState('ready');
      }
    };

    worker.postMessage({ trackId, /* ... */ });
  }, []);

  return { state, progress, preprocess };
}

// Usage in player component
function PlayerComponent() {
  const { currentTrack } = usePlayer();
  const { state: fingerprintState, progress } = useFingerprintCache();

  useEffect(() => {
    if (currentTrack) {
      useFingerprintCache().preprocess(currentTrack.id);
    }
  }, [currentTrack?.id]);

  return (
    <>
      <Player />
      {fingerprintState === 'processing' && (
        <BufferingIndicator progress={progress} />
      )}
    </>
  );
}
```

**Testing:**
- Cache persistence tests
- Worker communication tests
- Cache invalidation tests

---

### 0.4 Testing Setup & Utilities

**Goal:** Establish testing patterns for refactored components
**Files Created:**
- `src/test/hooks/test-hooks.tsx` - Hook testing utilities
- `src/test/mocks/websocket-mock.ts` - WebSocket mock implementation
- `src/test/fixtures/player-state.ts` - Realistic test data

**Key Patterns:**

```typescript
// Test hook in isolation with mock WebSocket
import { renderHook, act } from '@testing-library/react';
import { usePlayer } from '@/hooks/player/usePlayer';
import { mockWebSocket } from '@/test/mocks/websocket-mock';

describe('usePlayer', () => {
  beforeEach(() => {
    mockWebSocket.reset();
  });

  it('should track playback state changes', async () => {
    const { result } = renderHook(() => usePlayer());

    act(() => {
      mockWebSocket.send({
        type: 'playback_started',
        data: { state: 'playing' }
      });
    });

    expect(result.current.isPlaying).toBe(true);
  });

  it('should handle sudden track changes', async () => {
    const { result } = renderHook(() => usePlayer());

    act(() => {
      mockWebSocket.send({
        type: 'track_changed',
        data: { action: 'next' }
      });
    });

    await waitFor(() => {
      expect(result.current.currentTrack?.id).not.toBe(initialTrack.id);
    });
  });
});
```

---

### 0.5 Redux Store Migration Plan

**Goal:** Plan gradual Redux → State Management transition
**Decision:** Keep Redux for Phase 0-1, migrate to Context + Hooks in Phase 2-3

**Rationale:**
- Redux is working for player/queue state
- Don't break what's working
- Refactor library state to Context when redesigning library view
- Timeline pressure: 4-6 weeks for complete redesign

**Deferred Actions:**
- Redux removal (Phase 2)
- Global state consolidation (Phase 3)

---

## 🎮 Phase 1: Core Player Redesign (1.5 weeks)

**Parallel Start:** With Phase 2 & 3
**Owner:** 1-2 developers
**Components To Rebuild:**
- `src/components/player-bar-v3/PlayerBar.tsx` (NEW)
- `src/components/player-bar-v3/PlaybackControls.tsx`
- `src/components/player-bar-v3/ProgressBar.tsx`
- `src/components/player-bar-v3/TrackInfo.tsx`
- `src/components/player-bar-v3/VolumeControl.tsx`

### 1.1 Player State Management

**Goal:** Single source of truth for playback state via WebSocket
**New Hook:** `usePlaybackState()`

```typescript
interface PlaybackStateData {
  currentTrack: Track | null;
  isPlaying: boolean;
  volume: number;
  position: number;
  duration: number;
  queue: Track[];
  queueIndex: number;
  gapless_enabled: boolean;
  crossfade_enabled: boolean;
  crossfade_duration: number;
  isLoading: boolean;
  error: string | null;
}

export function usePlaybackState(): PlaybackStateData {
  const [state, setState] = useState<PlaybackStateData>({
    currentTrack: null,
    isPlaying: false,
    volume: 1.0,
    position: 0,
    duration: 0,
    queue: [],
    queueIndex: -1,
    gapless_enabled: true,
    crossfade_enabled: true,
    crossfade_duration: 3.0,
    isLoading: false,
    error: null,
  });

  useWebSocketSubscription(
    ['player_state', 'playback_started', 'playback_paused', 'playback_stopped'],
    (message) => {
      if (message.type === 'player_state') {
        setState(message.data);
      } else if (message.type === 'playback_started') {
        setState(prev => ({ ...prev, isPlaying: true }));
      } else if (message.type === 'playback_paused') {
        setState(prev => ({ ...prev, isPlaying: false }));
      } else if (message.type === 'playback_stopped') {
        setState(prev => ({
          ...prev,
          isPlaying: false,
          currentTrack: null,
          queue: [],
          position: 0,
        }));
      }
    }
  );

  return state;
}
```

**Testing:**
- WebSocket message handling
- State updates on track changes
- Error state recovery
- Sudden track changes (skip, seek, preset toggle)

---

### 1.2 Playback Controls

**Goal:** Implement play, pause, seek, next, previous, volume
**New Hook:** `usePlaybackControl()`

```typescript
export function usePlaybackControl() {
  const api = useRestAPI();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeAction = useCallback(async (
    endpoint: string,
    method: 'POST' | 'PUT' = 'POST',
    data?: any
  ) => {
    try {
      setIsLoading(true);
      setError(null);

      if (method === 'POST') {
        await api.post(endpoint, data || {});
      } else {
        await api.put(endpoint, data || {});
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  return {
    play: () => executeAction('/api/player/play'),
    pause: () => executeAction('/api/player/pause'),
    stop: () => executeAction('/api/player/stop'),
    seek: (position: number) =>
      executeAction('/api/player/seek', 'PUT', { position }),
    next: () => executeAction('/api/player/next'),
    previous: () => executeAction('/api/player/previous'),
    setVolume: (volume: number) =>
      executeAction('/api/player/volume', 'PUT', { volume }),
    addToQueue: (trackPath: string) =>
      executeAction('/api/player/queue/add', 'POST', { track_path: trackPath }),
    removeFromQueue: (index: number) =>
      executeAction(`/api/player/queue/${index}`, 'DELETE'),
    clearQueue: () => executeAction('/api/player/queue/clear', 'POST'),
    shuffleQueue: () => executeAction('/api/player/queue/shuffle', 'POST'),
    reorderQueue: (fromIndex: number, toIndex: number) =>
      executeAction('/api/player/queue/reorder', 'PUT', { from_index: fromIndex, to_index: toIndex }),

    isLoading,
    error,
  };
}
```

**Testing:**
- Each control method maps to correct endpoint
- Loading/error states handled
- Optimistic updates with rollback on error
- Network timeout handling

---

### 1.3 Player Component Rebuild

**Goal:** Create slim, focused player components
**Architecture:**

```typescript
// src/components/player-bar-v3/PlayerBar.tsx (< 100 lines)
export function PlayerBar() {
  const { currentTrack, isPlaying, volume, position, duration } = usePlayer();
  const { fingerprint } = useFingerprintCache();

  return (
    <div className={styles.playerBar}>
      <TrackInfo track={currentTrack} />
      <PlaybackControls isPlaying={isPlaying} />
      <ProgressBar position={position} duration={duration} />
      <VolumeControl volume={volume} />
      {fingerprint.state === 'processing' && (
        <div className={styles.buffer}>Buffering... {fingerprint.progress}%</div>
      )}
    </div>
  );
}

// src/components/player-bar-v3/PlaybackControls.tsx (< 80 lines)
export function PlaybackControls({ isPlaying }: { isPlaying: boolean }) {
  const { play, pause, next, previous, isLoading, error } = usePlaybackControl();

  return (
    <div className={styles.controls}>
      <button
        onClick={() => previous()}
        disabled={isLoading}
        aria-label="Previous track"
      >
        <IconSkipBack />
      </button>

      <button
        onClick={() => isPlaying ? pause() : play()}
        disabled={isLoading}
        className={styles.playButton}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? <IconPause /> : <IconPlay />}
      </button>

      <button
        onClick={() => next()}
        disabled={isLoading}
        aria-label="Next track"
      >
        <IconSkipForward />
      </button>

      {error && <span className={styles.error}>{error}</span>}
    </div>
  );
}

// src/components/player-bar-v3/ProgressBar.tsx (< 120 lines)
export function ProgressBar({ position, duration }: ProgressBarProps) {
  const { seek, crossfade_enabled, crossfade_duration } = usePlaybackControl();
  const [isDragging, setIsDragging] = useState(false);
  const [hoverPosition, setHoverPosition] = useState<number | null>(null);

  const handleSeek = useCallback((newPosition: number) => {
    seek(newPosition).catch(console.error);
  }, [seek]);

  return (
    <div className={styles.progress}>
      <span className={styles.time}>{formatTime(position)}</span>

      <div
        className={styles.track}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const percent = (e.clientX - rect.left) / rect.width;
          setHoverPosition(percent * duration);
        }}
        onMouseLeave={() => setHoverPosition(null)}
      >
        <div
          className={styles.fill}
          style={{ width: `${(position / duration) * 100}%` }}
        />

        {/* Crossfade visualization */}
        {crossfade_enabled && (
          <div
            className={styles.crossfade}
            style={{
              left: `${((duration - crossfade_duration) / duration) * 100}%`,
              width: `${(crossfade_duration / duration) * 100}%`,
            }}
          />
        )}

        <input
          type="range"
          min={0}
          max={duration}
          value={isDragging && hoverPosition ? hoverPosition : position}
          onChange={(e) => handleSeek(parseFloat(e.target.value))}
          onMouseDown={() => setIsDragging(true)}
          onMouseUp={() => setIsDragging(false)}
          className={styles.slider}
        />

        {hoverPosition && (
          <div
            className={styles.tooltip}
            style={{ left: `${(hoverPosition / duration) * 100}%` }}
          >
            {formatTime(hoverPosition)}
          </div>
        )}
      </div>

      <span className={styles.time}>{formatTime(duration)}</span>
    </div>
  );
}

// src/components/player-bar-v3/TrackInfo.tsx (< 100 lines)
export function TrackInfo({ track }: { track: Track | null }) {
  if (!track) {
    return <div className={styles.empty}>No track playing</div>;
  }

  return (
    <div className={styles.trackInfo}>
      <img
        src={track.artwork_url || '/placeholder.jpg'}
        alt={track.title}
        className={styles.artwork}
      />
      <div className={styles.details}>
        <h3 className={styles.title}>{track.title}</h3>
        <p className={styles.artist}>{track.artist}</p>
        <p className={styles.album}>{track.album}</p>
      </div>
    </div>
  );
}

// src/components/player-bar-v3/VolumeControl.tsx (< 100 lines)
export function VolumeControl({ volume }: { volume: number }) {
  const { setVolume } = usePlaybackControl();
  const [isMuted, setIsMuted] = useState(false);
  const previousVolume = useRef(volume);

  const handleMute = useCallback(() => {
    if (isMuted) {
      setVolume(previousVolume.current);
      setIsMuted(false);
    } else {
      previousVolume.current = volume;
      setVolume(0);
      setIsMuted(true);
    }
  }, [isMuted, volume, setVolume]);

  return (
    <div className={styles.volumeControl}>
      <button onClick={handleMute} aria-label="Toggle mute">
        {isMuted || volume === 0 ? <IconVolumeMute /> : <IconVolume2 />}
      </button>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={volume}
        onChange={(e) => setVolume(parseFloat(e.target.value))}
        className={styles.slider}
      />
      <span className={styles.percentage}>{Math.round(volume * 100)}%</span>
    </div>
  );
}
```

**Key Improvements:**
- Each component < 120 lines
- Single responsibility per component
- Crossfade visualization built in
- Error handling with user feedback
- Optimistic UI updates

**Testing:**
- Unit tests for each component
- Integration tests for player flow (play → seek → next → pause)
- Handle sudden state changes (preset toggle during playback)
- Network error handling and recovery

---

### 1.4 Player Streaming Integration

**Goal:** Integrate new WebM/Opus streaming backend
**Architecture:** Use existing `UnifiedWebMAudioPlayer` service but through new hooks

```typescript
// src/services/player/UnifiedWebMAudioPlayerV2.ts
// Wraps existing UnifiedWebMAudioPlayer with new API shape
export class UnifiedWebMAudioPlayerV2 {
  private player: UnifiedWebMAudioPlayer;

  async loadTrack(track: Track): Promise<void> {
    // 1. Start fingerprinting in background (disguised as buffering)
    this.startFingerprinting(track.id);

    // 2. Fetch WebM/Opus stream from /api/player/stream/{track_id}
    const response = await fetch(`/api/player/stream/${track.id}`);
    const stream = response.body!;

    // 3. Load into MSE buffer
    await this.player.load(stream);
  }

  private async startFingerprinting(trackId: number) {
    const cached = await fingerprintCache.get(trackId);
    if (!cached) {
      // Compute in background Web Worker
      // Disguised as buffering to user
      fingerprintWorker.compute(trackId);
    }
  }

  async play(): Promise<void> {
    return this.player.play();
  }

  async pause(): Promise<void> {
    return this.player.pause();
  }

  async seek(position: number): Promise<void> {
    return this.player.seek(position);
  }

  getPosition(): number {
    return this.player.getPosition();
  }

  getDuration(): number {
    return this.player.getDuration();
  }
}
```

**Testing:**
- Stream loading
- Chunk prebuffering
- Seek accuracy
- Playback continuity

---

## 📚 Phase 2: Library Browser Redesign (1.5 weeks)

**Parallel Start:** With Phase 1 & 3
**Owner:** 1-2 developers
**Components To Rebuild:**
- `src/components/library-v3/LibraryView.tsx` (NEW)
- `src/components/library-v3/TrackList.tsx`
- `src/components/library-v3/AlbumGrid.tsx`
- `src/components/library-v3/ArtistList.tsx`
- `src/components/library-v3/SearchBar.tsx`
- `src/components/library-v3/MetadataEditor.tsx`

### 2.1 Library State Management

**Goal:** Query library data with caching + infinite scroll pagination
**New Hook:** `useLibrary()`

```typescript
interface LibraryQueryOptions {
  view: 'tracks' | 'albums' | 'artists';
  sortBy?: 'title' | 'artist' | 'album' | 'date_added';
  sortOrder?: 'asc' | 'desc';
  search?: string;
  limit?: number;
  offset?: number;
}

interface LibraryState {
  items: (Track | Album | Artist)[];
  total: number;
  hasMore: boolean;
  isLoading: boolean;
  error: string | null;
}

export function useLibrary(options: LibraryQueryOptions): LibraryState {
  const [state, setState] = useState<LibraryState>({
    items: [],
    total: 0,
    hasMore: true,
    isLoading: false,
    error: null,
  });

  const api = useRestAPI();

  useEffect(() => {
    const fetchData = async () => {
      setState(prev => ({ ...prev, isLoading: true }));
      try {
        const endpoint = `/api/library/${options.view}`;
        const params = new URLSearchParams({
          limit: (options.limit || 50).toString(),
          offset: (options.offset || 0).toString(),
          ...(options.search && { q: options.search }),
          ...(options.sortBy && { sort: options.sortBy }),
          ...(options.sortOrder && { order: options.sortOrder }),
        });

        const response = await api.get(`${endpoint}?${params}`);

        setState({
          items: response.data,
          total: response.total,
          hasMore: response.offset + response.data.length < response.total,
          isLoading: false,
          error: null,
        });
      } catch (err) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: err instanceof Error ? err.message : 'Unknown error',
        }));
      }
    };

    fetchData();
  }, [options, api]);

  // Listen for library updates via WebSocket
  useWebSocketSubscription(['library_updated'], (message) => {
    // Invalidate cache and refetch
    setState(prev => ({ ...prev, items: [] }));
  });

  return state;
}
```

**Testing:**
- Query caching
- Pagination handling
- Search filtering
- Sort order
- WebSocket invalidation on library changes

---

### 2.2 Infinite Scroll Implementation

**Goal:** Virtual scrolling for 10,000+ tracks
**Hook:** `useInfiniteScroll()`

```typescript
export function useInfiniteScroll(
  loadMore: () => Promise<void>,
  hasMore: boolean,
  isLoading: boolean
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore && !isLoading) {
          loadMore();
        }
      },
      { rootMargin: '200px' }
    );

    if (sentinelRef.current) {
      observer.observe(sentinelRef.current);
    }

    return () => observer.disconnect();
  }, [hasMore, isLoading, loadMore]);

  return { containerRef, sentinelRef };
}
```

**Testing:**
- Intersection observer triggers
- Loading state management
- Rapid scroll performance

---

### 2.3 Library View Components

**Goal:** Create focused, reusable list/grid components
**Architecture:**

```typescript
// src/components/library-v3/LibraryView.tsx (< 150 lines)
export function LibraryView() {
  const [view, setView] = useState<'tracks' | 'albums' | 'artists'>('tracks');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'title' | 'artist' | 'date'>('title');
  const [offset, setOffset] = useState(0);

  const { items, hasMore, isLoading } = useLibrary({
    view,
    search,
    sortBy,
    limit: 50,
    offset,
  });

  const { containerRef, sentinelRef } = useInfiniteScroll(
    () => setOffset(prev => prev + 50),
    hasMore,
    isLoading
  );

  return (
    <div className={styles.libraryView}>
      <header>
        <SearchBar onSearch={setSearch} />
        <ViewToggle current={view} onChange={setView} />
        <SortControls current={sortBy} onChange={setSortBy} />
      </header>

      <div ref={containerRef} className={styles.content}>
        {view === 'tracks' && <TrackList items={items as Track[]} />}
        {view === 'albums' && <AlbumGrid items={items as Album[]} />}
        {view === 'artists' && <ArtistList items={items as Artist[]} />}

        {isLoading && <LoadingSpinner />}
      </div>

      <div ref={sentinelRef} className={styles.sentinel} />
    </div>
  );
}

// src/components/library-v3/TrackList.tsx (< 120 lines)
export function TrackList({ items }: { items: Track[] }) {
  const { play } = usePlaybackControl();
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const handlePlayClick = useCallback((track: Track) => {
    play(); // Will load track via API
  }, [play]);

  const handleSelect = useCallback((id: number, isCtrlKey: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (isCtrlKey) {
        if (next.has(id)) next.delete(id);
        else next.add(id);
      } else {
        next.clear();
        next.add(id);
      }
      return next;
    });
  }, []);

  return (
    <table className={styles.trackList}>
      <thead>
        <tr>
          <th style={{ width: '40px' }}></th>
          <th>Title</th>
          <th>Artist</th>
          <th>Album</th>
          <th style={{ width: '60px' }}>Duration</th>
        </tr>
      </thead>
      <tbody>
        {items.map(track => (
          <tr
            key={track.id}
            className={selectedIds.has(track.id) ? styles.selected : ''}
            onClick={(e) => handleSelect(track.id, e.ctrlKey || e.metaKey)}
          >
            <td>
              <button
                className={styles.playButton}
                onClick={() => handlePlayClick(track)}
                aria-label={`Play ${track.title}`}
              >
                <IconPlay />
              </button>
            </td>
            <td>{track.title}</td>
            <td>{track.artist}</td>
            <td>{track.album}</td>
            <td>{formatTime(track.duration)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// src/components/library-v3/AlbumGrid.tsx (< 100 lines)
export function AlbumGrid({ items }: { items: Album[] }) {
  return (
    <div className={styles.grid}>
      {items.map(album => (
        <AlbumCard key={album.id} album={album} />
      ))}
    </div>
  );
}

// src/components/library-v3/AlbumCard.tsx (< 100 lines)
export function AlbumCard({ album }: { album: Album }) {
  const { play } = usePlaybackControl();
  const router = useRouter();

  return (
    <div
      className={styles.card}
      onClick={() => router.push(`/albums/${album.id}`)}
    >
      <div className={styles.artwork}>
        <img src={album.artwork_url} alt={album.title} />
        <button
          className={styles.playOverlay}
          onClick={(e) => {
            e.stopPropagation();
            play(); // Will load first track of album
          }}
        >
          <IconPlay />
        </button>
      </div>
      <h3 className={styles.title}>{album.title}</h3>
      <p className={styles.artist}>{album.artist}</p>
      <p className={styles.trackCount}>{album.track_count} tracks</p>
    </div>
  );
}

// src/components/library-v3/SearchBar.tsx (< 80 lines)
export function SearchBar({ onSearch }: { onSearch: (q: string) => void }) {
  const [query, setQuery] = useState('');
  const timeoutRef = useRef<number>();

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);

    clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => {
      onSearch(value);
    }, 300); // Debounce
  }, [onSearch]);

  return (
    <div className={styles.searchBar}>
      <IconSearch />
      <input
        type="text"
        placeholder="Search tracks, albums, artists..."
        value={query}
        onChange={handleChange}
        className={styles.input}
      />
      {query && (
        <button onClick={() => {
          setQuery('');
          onSearch('');
        }}>
          <IconX />
        </button>
      )}
    </div>
  );
}
```

**Key Improvements:**
- Tracks can handle 10,000+ items via virtual scrolling
- Search with 300ms debounce
- Multi-select with Ctrl+click
- Infinite scroll with 200px ahead-of-time loading
- Album artwork lazy loading

**Testing:**
- Virtual scrolling performance
- Search debouncing
- Multi-select state
- Infinite scroll pagination

---

### 2.4 Metadata Editor

**Goal:** Edit track metadata (title, artist, album, genre, year)
**New Hook:** `useMetadataEditor()`

```typescript
interface MetadataEditOptions {
  trackIds: number[];
  fields: ('title' | 'artist' | 'album' | 'genre' | 'year')[];
}

export function useMetadataEditor(options: MetadataEditOptions) {
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const api = useRestAPI();

  const submit = useCallback(async () => {
    setIsSubmitting(true);
    try {
      // Single track update
      if (options.trackIds.length === 1) {
        await api.put(
          `/api/metadata/tracks/${options.trackIds[0]}`,
          formData
        );
      } else {
        // Batch update
        await api.post('/api/metadata/batch', {
          track_ids: options.trackIds,
          updates: formData,
        });
      }

      setError(null);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }, [options.trackIds, formData, api]);

  return {
    formData,
    setFormData,
    submit,
    isSubmitting,
    error,
  };
}

// Component
export function MetadataEditorDialog({
  trackIds,
  isOpen,
  onClose,
}: {
  trackIds: number[];
  isOpen: boolean;
  onClose: () => void;
}) {
  const { formData, setFormData, submit, isSubmitting, error } = useMetadataEditor({
    trackIds,
    fields: ['title', 'artist', 'album', 'genre', 'year'],
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await submit();
    if (success) {
      onClose();
    }
  };

  return (
    <dialog open={isOpen} className={styles.dialog}>
      <form onSubmit={handleSubmit}>
        <h2>Edit Metadata</h2>
        <p className={styles.subtitle}>
          {trackIds.length === 1
            ? '1 track selected'
            : `${trackIds.length} tracks selected`}
        </p>

        <div className={styles.form}>
          {['title', 'artist', 'album', 'genre', 'year'].map(field => (
            <div key={field} className={styles.field}>
              <label htmlFor={field} className={styles.label}>
                {field.charAt(0).toUpperCase() + field.slice(1)}
              </label>
              <input
                id={field}
                type="text"
                value={formData[field] || ''}
                onChange={(e) =>
                  setFormData(prev => ({ ...prev, [field]: e.target.value }))
                }
                className={styles.input}
              />
            </div>
          ))}
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.actions}>
          <button type="button" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </dialog>
  );
}
```

**Testing:**
- Single track metadata update
- Batch metadata update
- Form validation
- Error handling and recovery

---

## 🎚️ Phase 3: Enhancement Pane Redesign (1 week)

**Parallel Start:** With Phase 1 & 2
**Owner:** 1 developer
**Components To Rebuild:**
- `src/components/enhancement-pane-v3/EnhancementPane.tsx` (NEW)
- `src/components/enhancement-pane-v3/PresetSelector.tsx`
- `src/components/enhancement-pane-v3/ParameterDisplay.tsx`
- `src/components/enhancement-pane-v3/MasteringRecommendation.tsx`

### 3.1 Enhancement Settings Management

**Goal:** Manage audio enhancement settings with real-time sync
**New Hook:** `useEnhancement()`

```typescript
interface EnhancementSettings {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number; // 0.0 - 1.0
}

interface MasteringRecommendation {
  track_id: number;
  primary_profile_id: string;
  primary_profile_name: string;
  confidence_score: number;
  predicted_loudness_change: number;
  predicted_crest_change: number;
  predicted_centroid_change: number;
  weighted_profiles: Array<{
    profile_id: string;
    profile_name: string;
    weight: number;
  }>;
  reasoning: string;
  is_hybrid: boolean;
}

export function useEnhancement() {
  const [settings, setSettings] = useState<EnhancementSettings>({
    enabled: true,
    preset: 'adaptive',
    intensity: 1.0,
  });

  const [recommendation, setRecommendation] = useState<MasteringRecommendation | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const api = useRestAPI();

  // Fetch settings on mount
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await api.get('/api/enhancement/settings');
        setSettings(response);
      } catch (err) {
        console.error('Failed to fetch enhancement settings:', err);
      }
    };

    fetchSettings();
  }, [api]);

  // Listen for setting changes via WebSocket
  useWebSocketSubscription(['enhancement_settings_changed'], (message) => {
    setSettings(message.data);
  });

  // Listen for mastering recommendations
  useWebSocketSubscription(['mastering_recommendation'], (message) => {
    setRecommendation(message.data);
  });

  const updateSettings = useCallback(async (updates: Partial<EnhancementSettings>) => {
    const newSettings = { ...settings, ...updates };
    setSettings(newSettings);

    try {
      await api.put('/api/enhancement/settings', newSettings);
    } catch (err) {
      // Rollback on error
      setSettings(settings);
      throw err;
    }
  }, [settings, api]);

  const toggleEnabled = useCallback(() => {
    updateSettings({ enabled: !settings.enabled });
  }, [settings.enabled, updateSettings]);

  const setPreset = useCallback((preset: EnhancementSettings['preset']) => {
    updateSettings({ preset });
  }, [updateSettings]);

  const setIntensity = useCallback((intensity: number) => {
    updateSettings({ intensity });
  }, [updateSettings]);

  return {
    settings,
    recommendation,
    toggleEnabled,
    setPreset,
    setIntensity,
    isLoading,
  };
}
```

**Testing:**
- Settings fetch on mount
- WebSocket updates
- Optimistic updates with rollback
- Recommendation updates

---

### 3.2 Enhancement Pane Components

**Goal:** Modern, clear enhancement UI
**Architecture:**

```typescript
// src/components/enhancement-pane-v3/EnhancementPane.tsx (< 100 lines)
export function EnhancementPane() {
  const { settings, recommendation, toggleEnabled, setPreset, setIntensity } = useEnhancement();

  return (
    <aside className={styles.pane}>
      <header className={styles.header}>
        <h2>Audio Enhancement</h2>
      </header>

      <div className={styles.content}>
        {/* Toggle */}
        <div className={styles.section}>
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={() => toggleEnabled()}
            />
            <span>Enhancement {settings.enabled ? 'ON' : 'OFF'}</span>
          </label>
        </div>

        {settings.enabled && (
          <>
            {/* Preset Selector */}
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Preset</h3>
              <PresetSelector
                current={settings.preset}
                onChange={setPreset}
              />
            </div>

            {/* Intensity Slider */}
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Intensity</h3>
              <IntensitySlider
                value={settings.intensity}
                onChange={setIntensity}
              />
            </div>

            {/* Mastering Recommendation */}
            {recommendation && (
              <MasteringRecommendation
                recommendation={recommendation}
              />
            )}

            {/* Parameter Display */}
            <ParameterDisplay
              loudnessChange={recommendation?.predicted_loudness_change}
              crestChange={recommendation?.predicted_crest_change}
              centroidChange={recommendation?.predicted_centroid_change}
            />
          </>
        )}
      </div>
    </aside>
  );
}

// src/components/enhancement-pane-v3/PresetSelector.tsx (< 100 lines)
const PRESET_DESCRIPTIONS: Record<string, string> = {
  adaptive: 'Automatically optimize for current track',
  gentle: 'Subtle enhancement with minimal change',
  warm: 'Enhance warmth and bass',
  bright: 'Enhance clarity and high frequencies',
  punchy: 'Maximize energy and dynamics',
};

export function PresetSelector({
  current,
  onChange,
}: {
  current: string;
  onChange: (preset: string) => void;
}) {
  const presets = ['adaptive', 'gentle', 'warm', 'bright', 'punchy'] as const;

  return (
    <div className={styles.presets}>
      {presets.map(preset => (
        <button
          key={preset}
          className={`${styles.preset} ${current === preset ? styles.active : ''}`}
          onClick={() => onChange(preset)}
          title={PRESET_DESCRIPTIONS[preset]}
        >
          <span className={styles.name}>
            {preset.charAt(0).toUpperCase() + preset.slice(1)}
          </span>
          <span className={styles.description}>
            {PRESET_DESCRIPTIONS[preset]}
          </span>
        </button>
      ))}
    </div>
  );
}

// src/components/enhancement-pane-v3/IntensitySlider.tsx (< 80 lines)
export function IntensitySlider({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className={styles.intensity}>
      <div className={styles.labels}>
        <span>Off</span>
        <span>Full</span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className={styles.slider}
      />
      <div className={styles.value}>{Math.round(value * 100)}%</div>
    </div>
  );
}

// src/components/enhancement-pane-v3/MasteringRecommendation.tsx (< 120 lines)
export function MasteringRecommendation({
  recommendation,
}: {
  recommendation: MasteringRecommendation;
}) {
  return (
    <div className={styles.recommendation}>
      <h3 className={styles.title}>Mastering Profile</h3>

      <div className={styles.primary}>
        <div className={styles.profile}>
          <div className={styles.name}>{recommendation.primary_profile_name}</div>
          <div className={styles.confidence}>
            Confidence: {Math.round(recommendation.confidence_score * 100)}%
          </div>
        </div>
      </div>

      {recommendation.is_hybrid && recommendation.weighted_profiles.length > 0 && (
        <div className={styles.hybrid}>
          <p className={styles.label}>Hybrid Blend</p>
          <div className={styles.profiles}>
            {recommendation.weighted_profiles.map(profile => (
              <div key={profile.profile_id} className={styles.profileBar}>
                <span className={styles.name}>{profile.profile_name}</span>
                <div className={styles.bar}>
                  <div
                    className={styles.fill}
                    style={{ width: `${profile.weight * 100}%` }}
                  />
                </div>
                <span className={styles.weight}>{Math.round(profile.weight * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className={styles.reasoning}>
        <p className={styles.label}>Why</p>
        <p className={styles.text}>{recommendation.reasoning}</p>
      </div>

      <div className={styles.predictions}>
        <div className={styles.metric}>
          <span className={styles.label}>Loudness</span>
          <span className={`${styles.value} ${recommendation.predicted_loudness_change > 0 ? styles.positive : ''}`}>
            {recommendation.predicted_loudness_change > 0 ? '+' : ''}{recommendation.predicted_loudness_change.toFixed(2)} dB
          </span>
        </div>
        <div className={styles.metric}>
          <span className={styles.label}>Crest</span>
          <span className={`${styles.value} ${recommendation.predicted_crest_change > 0 ? styles.positive : ''}`}>
            {recommendation.predicted_crest_change > 0 ? '+' : ''}{recommendation.predicted_crest_change.toFixed(2)} dB
          </span>
        </div>
        <div className={styles.metric}>
          <span className={styles.label}>Centroid</span>
          <span className={`${styles.value} ${recommendation.predicted_centroid_change > 0 ? styles.positive : ''}`}>
            {recommendation.predicted_centroid_change > 0 ? '+' : ''}{recommendation.predicted_centroid_change.toFixed(1)} Hz
          </span>
        </div>
      </div>
    </div>
  );
}

// src/components/enhancement-pane-v3/ParameterDisplay.tsx (< 100 lines)
export function ParameterDisplay({
  loudnessChange,
  crestChange,
  centroidChange,
}: {
  loudnessChange?: number;
  crestChange?: number;
  centroidChange?: number;
}) {
  if (!loudnessChange || !crestChange || !centroidChange) {
    return (
      <div className={styles.empty}>
        <p>Play a track to see predicted enhancement</p>
      </div>
    );
  }

  return (
    <div className={styles.parameters}>
      <h3 className={styles.title}>Predicted Changes</h3>
      <div className={styles.grid}>
        <ParameterBar
          label="Loudness"
          value={loudnessChange}
          unit="dB"
          min={-5}
          max={5}
        />
        <ParameterBar
          label="Crest Factor"
          value={crestChange}
          unit="dB"
          min={-5}
          max={5}
        />
        <ParameterBar
          label="Frequency"
          value={centroidChange}
          unit="Hz"
          min={-500}
          max={500}
        />
      </div>
    </div>
  );
}

// src/components/enhancement-pane-v3/ParameterBar.tsx (< 80 lines)
export function ParameterBar({
  label,
  value,
  unit,
  min,
  max,
}: {
  label: string;
  value: number;
  unit: string;
  min: number;
  max: number;
}) {
  const percent = ((value - min) / (max - min)) * 100;

  return (
    <div className={styles.parameter}>
      <div className={styles.header}>
        <span className={styles.label}>{label}</span>
        <span className={styles.value}>
          {value > 0 ? '+' : ''}{value.toFixed(2)} {unit}
        </span>
      </div>
      <div className={styles.bar}>
        <div
          className={`${styles.fill} ${value > 0 ? styles.positive : styles.negative}`}
          style={{ width: `${Math.abs(percent - 50) * 2}%` }}
        />
      </div>
    </div>
  );
}
```

**Key Improvements:**
- Clear preset descriptions
- Confidence score display
- Hybrid blend visualization
- Predicted change metrics
- Real-time update from WebSocket

**Testing:**
- Settings fetch and updates
- Preset switching
- Intensity slider
- Mastering recommendation display
- WebSocket updates

---

## 🔧 Phase 4: Integration & Polish (1 week)

**Sequential Phase:** Starts after Phase 1-3 basics complete
**Owner:** 1-2 developers

### 4.1 State Synchronization

**Goal:** Ensure all state changes propagate correctly across app
**Key Scenarios:**

1. **Track Skip During Playback**
   - User clicks "Next"
   - REST API call to `/api/player/next`
   - WebSocket broadcasts `track_changed`
   - Player updates currentTrack, position resets to 0
   - Fingerprint preprocessing starts for next track
   - Enhancement pane shows new mastering recommendation

2. **Seek + Enhancement Toggle**
   - User seeks to 2:30
   - REST API call to `/api/player/seek`
   - WebSocket broadcasts `position_changed`
   - User toggles enhancement OFF
   - REST API call to `/api/enhancement/settings`
   - WebSocket broadcasts `enhancement_settings_changed`
   - Both updates reflected in UI without race conditions

3. **Sudden Preset Change**
   - Track playing with "Adaptive" preset
   - User switches to "Bright" preset mid-playback
   - Enhancement pane updates preset selector
   - REST API call to `/api/enhancement/settings`
   - Backend re-processes audio with new preset
   - No playback interruption (streaming continues)
   - UI shows new mastering recommendation

**Implementation:**

```typescript
// Central state synchronization via WebSocket
export function usePlayerSync() {
  const playerState = usePlaybackState();
  const enhancementState = useEnhancement();
  const libraryState = useLibraryState();

  // Detect conflicts and resolve them
  const resolveConflict = useCallback((
    source: 'websocket' | 'local',
    state: string,
    values: Record<string, any>
  ) => {
    // Example: Position changed locally (seek) + WebSocket update (server side seek)
    if (source === 'websocket' && state === 'position') {
      // Server position is authoritative - accept it
      return true;
    }

    // Example: Enhancement toggled locally + WebSocket update
    if (source === 'websocket' && state === 'enhancement') {
      // Server settings are authoritative - accept it
      return true;
    }

    return true;
  }, []);

  return {
    playerState,
    enhancementState,
    libraryState,
    resolveConflict,
  };
}
```

**Testing:**
- Race condition handling
- Optimistic updates with server validation
- Conflict resolution
- Error recovery

---

### 4.2 Error Handling & Recovery

**Goal:** Gracefully handle network errors and unexpected state changes
**Scenarios:**

1. **Network Timeout During Seek**
   - User seeks to 3:00
   - Network timeout on `/api/player/seek`
   - UI shows error toast
   - Position reverts to pre-seek value
   - User can retry or try different position

2. **WebSocket Disconnect During Playback**
   - Playback started via REST API
   - WebSocket disconnects
   - Local timer continues tracking position
   - WebSocket reconnects
   - Full `player_state` synced with server
   - Local timer position validated against server
   - If different > 1 second, snap to server time

3. **Track Deletion While Playing**
   - Track playing from library
   - WebSocket receives `metadata_updated` with track marked as deleted
   - UI shows warning: "Track no longer available"
   - User can skip to next track
   - Or close app without crash

**Implementation:**

```typescript
export function useErrorRecovery() {
  const [error, setError] = useState<AppError | null>(null);
  const playerSync = usePlayerSync();

  const handleError = useCallback((err: unknown) => {
    const appError = normalizeError(err);

    switch (appError.type) {
      case 'NETWORK_ERROR':
        setError(appError);
        // Auto-retry after 2 seconds
        setTimeout(() => retry(), 2000);
        break;

      case 'NOT_FOUND':
        // Track was deleted - skip to next
        if (playerSync.playerState.currentTrack) {
          setError({
            type: 'INFO',
            message: 'Track no longer available',
          });
          // Skip to next after 3 seconds
          setTimeout(() => playerSync.next(), 3000);
        }
        break;

      case 'CONFLICT':
        // Server state differs from local - sync
        playerSync.syncWithServer();
        break;

      default:
        setError(appError);
    }
  }, [playerSync]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { error, handleError, clearError };
}
```

**Testing:**
- Network error handling
- Retry logic
- State recovery
- User-friendly error messages

---

### 4.3 Performance Optimization

**Goal:** Achieve 60 FPS rendering and < 16ms interactions
**Optimizations:**

1. **Component Memoization**
   ```typescript
   // Only re-render when props change
   export const TrackInfo = React.memo(function TrackInfo({ track }: Props) {
     return /* ... */;
   });
   ```

2. **useCallback for Event Handlers**
   ```typescript
   const handleSeek = useCallback((position: number) => {
     seek(position);
   }, [seek]); // Only recreate if seek changes
   ```

3. **Virtual Scrolling for Large Lists**
   - Implemented in Phase 2
   - Supports 10,000+ tracks
   - Only renders visible items

4. **Lazy Code Splitting**
   ```typescript
   const EnhancementPane = lazy(() => import('./EnhancementPane'));

   <Suspense fallback={<LoadingSpinner />}>
     <EnhancementPane />
   </Suspense>
   ```

5. **Image Optimization**
   ```typescript
   // Lazy load album artwork
   <img loading="lazy" src={artwork_url} alt={title} />
   ```

**Testing:**
- Performance benchmarks (Lighthouse)
- Frame rate monitoring
- Memory profiling
- Bundle size analysis

---

### 4.4 Accessibility (WCAG 2.1 AA)

**Goal:** Ensure app is usable by everyone
**Requirements:**

1. **Keyboard Navigation**
   - Tab through all controls
   - Enter to activate buttons
   - Space to play/pause
   - Arrow keys to seek
   - Shift+Arrow to adjust volume

2. **Screen Reader Support**
   - All buttons have `aria-label`
   - Form inputs have `<label>`
   - Live regions for status updates

3. **Color Contrast**
   - All text meets WCAG AA (4.5:1 ratio)
   - No information conveyed by color alone

4. **Focus Indicators**
   - Visible focus ring on all interactive elements
   - High contrast (3:1 minimum)

**Implementation:**

```typescript
// Keyboard shortcuts
export function useKeyboardShortcuts() {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault();
        playerSync.togglePlayback();
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        playerSync.seek(playerSync.position + 5);
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        playerSync.seek(playerSync.position - 5);
      } else if (e.code === 'ArrowUp') {
        e.preventDefault();
        playerSync.setVolume(Math.min(playerSync.volume + 0.1, 1));
      } else if (e.code === 'ArrowDown') {
        e.preventDefault();
        playerSync.setVolume(Math.max(playerSync.volume - 0.1, 0));
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [playerSync]);
}
```

**Testing:**
- Axe accessibility audit
- Screen reader testing
- Keyboard navigation
- Color contrast verification

---

### 4.5 Analytics & Monitoring

**Goal:** Track user behavior and errors for optimization
**Metrics:**

1. **Performance**
   - Page load time
   - Time to interactive
   - Frame rate during playback
   - Memory usage

2. **User Behavior**
   - Most used presets
   - Average session length
   - Library size distribution
   - Error frequency

3. **Errors**
   - Network errors
   - Playback failures
   - UI crashes
   - WebSocket disconnections

**Implementation:**

```typescript
export class Analytics {
  static trackPageView(page: string) {
    // Send to analytics service
  }

  static trackEvent(category: string, action: string, label?: string) {
    // Play track, skip track, toggle enhancement, etc.
  }

  static trackError(error: AppError) {
    // Network error, playback failure, etc.
  }

  static trackPerformance(metric: string, value: number) {
    // Load time, render time, etc.
  }
}
```

**Testing:**
- Analytics events fire correctly
- No data loss on errors
- Privacy compliant (no sensitive data)

---

## 📊 Testing Strategy

### Unit Tests (< 200 lines each)
- Hook tests (usePlayer, useLibrary, useEnhancement)
- Component render tests
- Event handler tests

### Integration Tests
- Player flow (play → seek → skip → pause)
- Library browsing (search → filter → sort → infinite scroll)
- Enhancement control (toggle → preset → intensity)

### E2E Tests (Playwright)
- Complete user flows
- Network error scenarios
- State sync scenarios

### Performance Tests
- Large library (10,000+ tracks)
- Long playback sessions (8+ hours)
- Rapid preset changes
- WebSocket reconnection

---

## 🎨 Design System Integration

All components use `tokens` from design system:

```typescript
import { tokens } from '@/design-system/tokens';

const styles = {
  container: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.primary,
    borderRadius: tokens.borderRadius.md,
  },
  text: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
    fontFamily: tokens.typography.fontFamily.primary,
  },
  interactive: {
    transition: tokens.transitions.normal,
    boxShadow: tokens.shadows.md,
  },
};
```

---

## 📅 Implementation Timeline

```
Week 1: Phase 0 (Foundation)
  Mon-Tue: Type definitions + WebSocket types
  Wed-Thu: Hooks architecture + Fingerprint cache
  Fri: Testing setup + documentation

Week 2-3: Phase 1-3 (Parallel)
  Phase 1 (Player) - 1.5 weeks
  Phase 2 (Library) - 1.5 weeks
  Phase 3 (Enhancement) - 1 week

Week 4: Phase 4 (Integration)
  Mon-Tue: State synchronization + error handling
  Wed-Thu: Performance optimization
  Fri: Accessibility + analytics

Week 5: Testing & Polish
  Mon-Tue: Test all scenarios
  Wed-Thu: Bug fixes + refinement
  Fri: Documentation + release prep

Week 6: Release
  Mon: Final testing
  Tue-Wed: Binary builds
  Thu: Release announcement
  Fri: Post-release monitoring
```

---

## 🚀 Success Criteria

- ✅ All 600+ files refactored into < 300 lines each
- ✅ Duplicate code eliminated (current 40% duplication → 0%)
- ✅ 100% API spec compliance
- ✅ Fingerprint caching working (disguised as buffering)
- ✅ Handle sudden state changes (seek, skip, preset toggle, auto-mastering)
- ✅ Modern, consistent UI across all sections
- ✅ 60 FPS rendering performance
- ✅ < 200ms UI interactions
- ✅ WCAG 2.1 AA accessibility
- ✅ 850+ frontend tests passing (same as backend)
- ✅ Zero known regressions from current version

---

## 🔗 Integration with Main Roadmap

**Priority:** 🔴 **CRITICAL - Main Priority (replaces all other frontend work)**

**Fits into:** [docs/roadmaps/DEVELOPMENT_ROADMAP_1_1_0.md](DEVELOPMENT_ROADMAP_1_1_0.md)

**Phase Integration:**
- **Phase 1 (Core Stability):** 50% complete
  - This redesign is the stabilization work for frontend
  - Eliminate fragmentation and duplicate code
  - Target: 1.1.0 stable release with new frontend

- **Phase 2 (Performance):** Ready for
  - Virtual scrolling (implemented Phase 2)
  - Code splitting (implemented Phase 4)
  - Query caching (uses new hooks)
  - Frontend optimization ready for Q1 2026

- **Phase 3+ (Features):** Foundation for
  - New features built on clean codebase
  - No duplicate code to maintain
  - Faster feature iteration

---

## 📚 Documentation

- This roadmap: [docs/roadmaps/FRONTEND_REDESIGN_ROADMAP_2_0.md](FRONTEND_REDESIGN_ROADMAP_2_0.md)
- Phase 0 setup: [docs/frontend/PHASE0_SETUP.md](docs/frontend/PHASE0_SETUP.md) (TBD)
- Component templates: [src/components/\_TEMPLATE.tsx](src/components/_TEMPLATE.tsx) (TBD)
- Hooks patterns: [docs/frontend/HOOKS_PATTERNS.md](docs/frontend/HOOKS_PATTERNS.md) (TBD)
- Testing guide: [docs/frontend/TESTING_GUIDE_V3.md](docs/frontend/TESTING_GUIDE_V3.md) (TBD)

---

## ✅ Next Steps

1. **Review & Approval** (You) - Read this roadmap and provide feedback
2. **Phase 0 Implementation** (1 developer) - 1 week
3. **Phase 1-3 Parallel Work** (2-3 developers) - 3 weeks
4. **Phase 4 Integration** (1-2 developers) - 1 week
5. **Testing & Release** - 1 week

**Start Date:** December 2, 2025 (after Phase 0 setup)
**Target Release:** 1.2.0 (March 2026)
**Estimated Effort:** 4-6 weeks (1-2 full-time developers)

---

*Created November 30, 2025*
*Integrated with DEVELOPMENT_ROADMAP_1_1_0.md as CRITICAL priority*
