# 🚀 Phase 0: Quick Start Guide

**Duration:** 1 week
**Owner:** 1 developer
**Target Completion:** December 6, 2025

This guide walks through the foundation work needed before starting Phase 1-3 parallel work.

---

## 📋 Phase 0 Tasks

### 0.1 WebSocket & API Types (2 days)

**Files to Create:**

```
src/types/
├── websocket.ts          # Complete WebSocket message types
├── api.ts               # REST API request/response shapes
└── domain.ts            # Core models (Track, Album, Artist, etc.)
```

**Quick Implementation:**

```typescript
// src/types/websocket.ts

// Message type union
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

// Base message interface
export interface WebSocketMessage<T = any> {
  type: WebSocketMessageType;
  data: T;
  timestamp?: number;
}

// Specific message types (copy from WEBSOCKET_API.md)
export interface PlayerStateMessage {
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

// ... (add all other message types)
```

**Testing Checklist:**
- [ ] All types compile without errors
- [ ] No unused types
- [ ] Message interfaces match WEBSOCKET_API.md exactly

---

### 0.2 REST API Types (1 day)

**Files to Create:**

```typescript
// src/types/api.ts

// Generic request/response shape
export interface ApiResponse<T> {
  data: T;
  error?: string;
  status: number;
}

export interface ApiListResponse<T> {
  data: T[];
  total: number;
  limit: number;
  offset: number;
}

// Player endpoints
export interface PlayerPlayRequest {
  track_path?: string;
}

export interface PlayerSeekRequest {
  position: number;
}

export interface PlayerVolumeRequest {
  volume: number;
}

export interface EnhancementSettingsRequest {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number;
}

// Library queries
export interface LibraryQueryParams {
  view: 'tracks' | 'albums' | 'artists';
  limit?: number;
  offset?: number;
  search?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

// Metadata update
export interface MetadataUpdateRequest {
  title?: string;
  artist?: string;
  album?: string;
  genre?: string;
  year?: number;
}

export interface MetadataBatchUpdateRequest {
  track_ids: number[];
  updates: MetadataUpdateRequest;
}
```

**Testing Checklist:**
- [ ] All request types match backend API
- [ ] Response types are consistent
- [ ] No breaking changes from current API usage

---

### 0.3 Domain Models (1 day)

**Files to Create:**

```typescript
// src/types/domain.ts

export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  filepath: string;
  artwork_url?: string;
  genre?: string;
  year?: number;
  bitrate?: number;
  sample_rate?: number;
  bit_depth?: number;
  format?: string;
  loudness?: number;
  crest_factor?: number;
  centroid?: number;
  date_added?: string;
  date_modified?: string;
}

export interface Album {
  id: number;
  title: string;
  artist: string;
  artwork_url?: string;
  track_count: number;
  year?: number;
  genre?: string;
  date_added?: string;
}

export interface Artist {
  id: number;
  name: string;
  artwork_url?: string;
  track_count: number;
  album_count: number;
  date_added?: string;
}

export interface Playlist {
  id: number;
  name: string;
  description?: string;
  track_count: number;
  created_at: string;
  modified_at: string;
  is_smart: boolean;
}

export interface EnhancementSettings {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number;
}

export interface Queue {
  tracks: Track[];
  currentIndex: number;
  isShuffled: boolean;
  repeatMode: 'off' | 'all' | 'one';
}

export interface Fingerprint {
  trackId: number;
  loudness: number;
  crest: number;
  centroid: number;
  spectralFlux: number[];
  mfcc: number[][];
  chroma: number[][];
  timestamp: number;
}

export interface MasteringRecommendation {
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
```

**Testing Checklist:**
- [ ] All models match backend Track/Album/Artist schema
- [ ] No missing required fields
- [ ] Optional fields clearly marked with `?`

---

### 0.4 Base Hooks Architecture (2 days)

**Files to Create:**

```
src/hooks/
├── index.ts                           # Public hook exports
├── websocket/
│   └── useWebSocketSubscription.ts    # Low-level subscription hook
├── api/
│   └── useRestAPI.ts                  # Typed REST API calls
├── player/
│   ├── usePlayer.ts                   # Composite hook
│   ├── usePlaybackState.ts            # Listen-only
│   └── usePlaybackControl.ts          # Control methods
├── library/
│   └── useLibrary.ts                  # Library queries with caching
├── enhancement/
│   └── useEnhancement.ts              # Audio settings
└── fingerprint/
    └── useFingerprintCache.ts         # Fingerprint caching
```

**Implementation Pattern:**

```typescript
// src/hooks/websocket/useWebSocketSubscription.ts

export function useWebSocketSubscription(
  messageTypes: WebSocketMessageType[],
  callback: (message: WebSocketMessage) => void
): () => void {
  useEffect(() => {
    // 1. Get WebSocket connection from context or global
    const ws = getWebSocketConnection();

    // 2. Subscribe to message types
    const unsubscribe = ws.subscribe(messageTypes, callback);

    // 3. Auto-cleanup on unmount
    return unsubscribe;
  }, [messageTypes, callback]);

  // Return unsubscribe function for manual cleanup
  return () => { /* cleanup */ };
}

// src/hooks/api/useRestAPI.ts

export function useRestAPI<T = any>() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const api = useMemo(() => {
    return {
      get: async (endpoint: string): Promise<T> => {
        setIsLoading(true);
        try {
          const response = await fetch(endpoint);
          if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
          return response.json();
        } catch (err) {
          setError(err instanceof Error ? err : new Error('Unknown error'));
          throw err;
        } finally {
          setIsLoading(false);
        }
      },

      post: async (endpoint: string, data: any): Promise<T> => {
        setIsLoading(true);
        try {
          const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
          });
          if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
          return response.json();
        } catch (err) {
          setError(err instanceof Error ? err : new Error('Unknown error'));
          throw err;
        } finally {
          setIsLoading(false);
        }
      },

      put: async (endpoint: string, data: any): Promise<T> => {
        // Similar to POST
      },

      delete: async (endpoint: string): Promise<void> => {
        // Similar implementation
      },
    };
  }, []);

  return api;
}
```

**Testing Checklist:**
- [ ] Hook subscribes to WebSocket correctly
- [ ] Hook unsubscribes on unmount
- [ ] REST API calls handle errors
- [ ] No infinite render loops

---

### 0.5 Fingerprint Cache System (2 days)

**Files to Create:**

```
src/services/fingerprint/
├── FingerprintCache.ts       # IndexedDB-backed cache
├── FingerprintWorker.ts      # Web Worker for processing
└── FingerprintAnalyzer.ts    # Computation logic
```

**Quick Implementation:**

```typescript
// src/services/fingerprint/FingerprintCache.ts

export class FingerprintCache {
  private dbName = 'auralis-fingerprints';
  private storeName = 'fingerprints';
  private db: IDBDatabase | null = null;

  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, 1);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          db.createObjectStore(this.storeName, { keyPath: 'trackId' });
        }
      };
    });
  }

  async get(trackId: number): Promise<Fingerprint | null> {
    if (!this.db) return null;

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      const request = store.get(trackId);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result || null);
    });
  }

  async set(trackId: number, fingerprint: Fingerprint): Promise<void> {
    if (!this.db) return;

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      const request = store.put({ trackId, ...fingerprint });

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  }

  async clear(): Promise<void> {
    if (!this.db) return;

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      const request = store.clear();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  }
}

// src/hooks/fingerprint/useFingerprintCache.ts

export function useFingerprintCache() {
  const [state, setState] = useState<'idle' | 'processing' | 'ready'>('idle');
  const [progress, setProgress] = useState(0);
  const cacheRef = useRef<FingerprintCache>();

  useEffect(() => {
    const cache = new FingerprintCache();
    cache.init();
    cacheRef.current = cache;

    return () => {
      // Cleanup
    };
  }, []);

  const preprocess = useCallback(async (trackId: number) => {
    const cache = cacheRef.current!;

    // Check if cached
    const cached = await cache.get(trackId);
    if (cached) {
      setState('ready');
      return cached;
    }

    // Start worker
    setState('processing');
    // ... worker communication
  }, []);

  return {
    state,
    progress,
    preprocess,
  };
}
```

**Testing Checklist:**
- [ ] Cache stores and retrieves fingerprints
- [ ] Cache initializes IndexedDB correctly
- [ ] Worker communicates with main thread
- [ ] Progress updates work
- [ ] Cache survives browser refresh

---

### 0.6 Testing Utilities & Setup (1 day)

**Files to Create:**

```typescript
// src/test/hooks/test-hooks.tsx

import { render, RenderResult } from '@testing-library/react';
import { ReactNode } from 'react';

// Wrap hooks with WebSocket mock + Redux provider
export function renderHook<T>(
  hook: () => T,
  options?: { initialState?: any }
): RenderResult {
  // Setup mock WebSocket
  // Setup Redux provider
  // Setup theme/design system context
  // Call hook
  // Return result + helpers
}

// src/test/mocks/websocket-mock.ts

export class WebSocketMock {
  private subscribers: Map<WebSocketMessageType, Set<Function>> = new Map();

  subscribe(types: WebSocketMessageType[], callback: Function): () => void {
    types.forEach(type => {
      if (!this.subscribers.has(type)) {
        this.subscribers.set(type, new Set());
      }
      this.subscribers.get(type)!.add(callback);
    });

    // Return unsubscribe function
    return () => {
      types.forEach(type => {
        this.subscribers.get(type)?.delete(callback);
      });
    };
  }

  send(message: WebSocketMessage): void {
    const callbacks = this.subscribers.get(message.type);
    if (callbacks) {
      callbacks.forEach(cb => cb(message));
    }
  }

  reset(): void {
    this.subscribers.clear();
  }
}

// src/test/fixtures/player-state.ts

export const mockTrack: Track = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  filepath: '/music/test.wav',
  genre: 'Rock',
  year: 2024,
};

export const mockPlayerState: PlayerStateMessage['data'] = {
  currentTrack: mockTrack,
  isPlaying: false,
  volume: 0.8,
  position: 0,
  duration: 180,
  queue: [mockTrack],
  queueIndex: 0,
  gapless_enabled: true,
  crossfade_enabled: true,
  crossfade_duration: 3.0,
};
```

**Testing Checklist:**
- [ ] Hook test utilities work
- [ ] WebSocket mock sends messages
- [ ] Test fixtures are realistic
- [ ] All tests pass

---

## ✅ Phase 0 Completion Checklist

### Types & Definitions
- [ ] `src/types/websocket.ts` - 100% complete with all message types
- [ ] `src/types/api.ts` - All request/response shapes
- [ ] `src/types/domain.ts` - All models (Track, Album, Artist, etc.)

### Hooks Architecture
- [ ] `src/hooks/websocket/useWebSocketSubscription.ts` - Low-level subscription
- [ ] `src/hooks/api/useRestAPI.ts` - Typed REST API
- [ ] `src/hooks/player/usePlayer.ts` - Composite hook
- [ ] `src/hooks/player/usePlaybackState.ts` - Listen-only state
- [ ] `src/hooks/player/usePlaybackControl.ts` - Control methods
- [ ] `src/hooks/library/useLibrary.ts` - Library queries
- [ ] `src/hooks/enhancement/useEnhancement.ts` - Audio settings
- [ ] `src/hooks/fingerprint/useFingerprintCache.ts` - Fingerprint cache

### Services
- [ ] `src/services/fingerprint/FingerprintCache.ts` - IndexedDB cache
- [ ] `src/services/fingerprint/FingerprintWorker.ts` - Web Worker
- [ ] `src/services/fingerprint/FingerprintAnalyzer.ts` - Analysis logic

### Testing
- [ ] `src/test/hooks/test-hooks.tsx` - Hook testing utilities
- [ ] `src/test/mocks/websocket-mock.ts` - WebSocket mock
- [ ] `src/test/fixtures/player-state.ts` - Test data

### Documentation
- [ ] Hook usage patterns documented
- [ ] Type definitions explained
- [ ] Testing examples provided
- [ ] Phase 0 summary written

### Quality Assurance
- [ ] TypeScript compilation passes
- [ ] No unused types or functions
- [ ] All tests passing
- [ ] Performance acceptable (no memory leaks)
- [ ] Code review approved

---

## 📚 Reference Documents

- **Backend API:** `auralis-web/backend/WEBSOCKET_API.md`
- **Design System:** `src/design-system/tokens.ts`
- **Testing Guide:** `docs/development/TESTING_GUIDELINES.md`
- **Frontend Redesign:** `docs/roadmaps/FRONTEND_REDESIGN_ROADMAP_2_0.md`

---

## 🚀 Moving to Phase 1-3

Once Phase 0 is complete:

1. **Phase 1 Team** starts Player redesign (uses new `usePlayer()` hook)
2. **Phase 2 Team** starts Library redesign (uses new `useLibrary()` hook)
3. **Phase 3 Team** starts Enhancement redesign (uses new `useEnhancement()` hook)

All three phases work in parallel, sharing the Phase 0 foundation.

---

*Timeline: 1 week (Dec 2-6, 2025)*
*Target: Ready for Phase 1-3 parallel work by December 7*
