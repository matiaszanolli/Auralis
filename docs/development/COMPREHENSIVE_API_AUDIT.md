# Comprehensive API Audit - Complete System Analysis

**Date**: 2025-12-20
**Status**: Phase 1 Complete - All endpoints documented
**Priority**: CRITICAL - Production blockers identified

---

## Executive Summary

**System-Wide Contract Analysis Reveals**:
- ✅ Backend has consistent **snake_case** convention across all endpoints
- ✅ Backend has serialization layer (`serializers.py`) for data transformation
- ❌ Frontend has **NO transformation layer** - consumes snake_case directly
- ❌ Frontend components expect **camelCase** props
- ❌ **Duplicate type definitions** with conflicting field names
- ❌ **No single source of truth** for data contracts

**Root Cause**: Frontend was designed for camelCase but backend provides snake_case. No bridge exists between them.

---

## Complete API Surface Map

### 1. Albums API (`/api/albums`)

**Backend Contract** (`routers/albums.py`):
```json
GET /api/albums?limit=50&offset=0&search=query&order_by=title
Response:
{
  "albums": [
    {
      "id": number,
      "title": string,
      "artist": string,              // Artist name (from artist.name)
      "year": number | null,
      "artwork_path": string | null, // ⚠️ snake_case
      "track_count": number,          // ⚠️ snake_case
      "total_duration": number        // ⚠️ snake_case
    }
  ],
  "total": number,
  "offset": number,
  "limit": number,
  "has_more": boolean               // ⚠️ snake_case
}
```

**Frontend Types** (`src/types/api.ts` line 109):
```typescript
export interface Album {
  id: number;
  title: string;
  artist: string;
  artwork_url?: string;    // ❌ MISMATCH: Backend returns "artwork_path"
  track_count: number;
  year?: number;
  genre?: string;          // ❌ Backend doesn't return this
  date_added?: string;     // ❌ Backend doesn't return this
  // ❌ MISSING: total_duration
}
```

**Component Props** (`src/components/album/AlbumCard/AlbumCard.tsx` line 23):
```typescript
export interface AlbumCardProps {
  albumId: number;         // ❌ Backend returns "id"
  title: string;
  artist: string;
  hasArtwork?: boolean;    // ❌ Backend returns "artwork_path" (string | null)
  trackCount?: number;     // ❌ Backend returns "track_count"
  duration?: number;       // ❌ Backend returns "total_duration"
  year?: number;
  onClick?: () => void;
  onArtworkUpdated?: () => void;
}
```

**Fix Applied**: ✅ CozyAlbumGrid now maps fields manually

---

### 2. Artists API (`/api/artists`)

**Backend Contract** (`routers/artists.py` using Pydantic models):
```json
GET /api/artists?limit=50&offset=0&search=query&order_by=name
Response (ArtistsListResponse):
{
  "artists": [
    {
      "id": number,
      "name": string,
      "album_count": number,  // ⚠️ snake_case
      "track_count": number,  // ⚠️ snake_case
      "genres": string[] | null
    }
  ],
  "total": number,
  "offset": number,
  "limit": number,
  "has_more": boolean
}
```

**Frontend Types** (`src/types/api.ts` line 124):
```typescript
export interface Artist {
  id: number;
  name: string;
  artwork_url?: string;    // ❌ Backend doesn't return this
  track_count: number;     // ⚠️ snake_case matches backend
  album_count: number;     // ⚠️ snake_case matches backend
  date_added?: string;     // ❌ Backend doesn't return this
}
```

**Status**: ⚠️ Partial match - snake_case in types matches backend, but missing fields

---

### 3. Tracks/Library API (`/api/library/tracks`)

**Backend Contract** (`routers/library.py` lines 123-129):
```json
GET /api/library/tracks?limit=50&offset=0&search=query&order_by=created_at
Response:
{
  "tracks": [ /* serialized via serialize_tracks() */ ],
  "total": number,
  "offset": number,
  "limit": number,
  "has_more": boolean
}
```

**Serializer** (`serializers.py` lines 18-24):
```python
DEFAULT_TRACK_FIELDS = {
    'id': None,
    'title': 'Unknown',
    'filepath': '',
    'duration': 0,
    'format': 'Unknown'
}
```

**Frontend Types** (`src/types/websocket.ts` - TrackInfo):
```typescript
export interface TrackInfo {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  filepath?: string;
  artwork_url?: string;
  genre?: string;
  year?: number;
  bitrate?: number;
  sample_rate?: number;
  format?: string;
}
```

**Status**: ⚠️ Mostly matches but uses different sources (library tracks vs player state)

---

### 4. Player API (`/api/player/*`)

**Endpoints**:
- `GET /api/player/status` - Get player state
- `POST /api/player/load` - Load track
- `POST /api/player/play` - Start playback
- `POST /api/player/pause` - Pause
- `POST /api/player/stop` - Stop
- `POST /api/player/seek` - Seek position
- `POST /api/player/volume` - Set volume
- `GET /api/player/queue` - Get queue
- `POST /api/player/queue` - Set queue
- `POST /api/player/next` - Next track
- `POST /api/player/previous` - Previous track

**Frontend Types** (`src/types/api.ts` lines 62-73):
```typescript
export interface PlayerState {
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  volume: number;
  position: number;
  duration: number;
  queue: TrackInfo[];
  queueIndex: number;
  gapless_enabled: boolean;     // ⚠️ snake_case
  crossfade_enabled: boolean;   // ⚠️ snake_case
  crossfade_duration: number;   // ⚠️ snake_case
}
```

**Status**: ⚠️ Mixed camelCase and snake_case

---

### 5. Enhancement API (`/api/player/enhancement/*`)

**Endpoints** (`routers/enhancement.py`):
- `POST /api/player/enhancement/toggle` - Enable/disable
- `POST /api/player/enhancement/preset` - Change preset
- `POST /api/player/enhancement/intensity` - Adjust intensity
- `GET /api/player/enhancement/status` - Get settings

**Valid Presets**: `["adaptive", "gentle", "warm", "bright", "punchy"]`

**Frontend Types** (`src/types/api.ts` lines 199-210):
```typescript
export interface EnhancementSettingsRequest {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number; // 0.0 - 1.0
}

export interface EnhancementSettingsResponse {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number;
  last_updated: string; // ⚠️ snake_case
}
```

**Status**: ✅ Mostly correct

---

### 6. WebSocket Messages

**Message Types** (`routers/system.py` - WebSocket endpoint `/ws`):

**Client → Server**:
```json
{
  "type": "play_enhanced",
  "data": {
    "track_id": number,
    "preset": string,
    "intensity": number
  }
}
```

**Server → Client**:
```json
// Player state updates
{
  "type": "player_state",
  "data": { /* PlayerState */ }
}

// Audio streaming
{
  "type": "audio_stream_start",
  "data": {
    "sample_rate": number,
    "channels": number,
    "total_chunks": number
  }
}

{
  "type": "audio_chunk",
  "data": {
    "chunk_data": string  // base64 PCM
  }
}

{
  "type": "audio_stream_end",
  "data": {}
}

// Playlist events
{
  "type": "playlist_created" | "playlist_updated" | "playlist_deleted",
  "data": { /* playlist data */ }
}
```

**Status**: ⚠️ Not fully typed in frontend

---

## Backend Serialization Layer

**Location**: `routers/serializers.py`

**Purpose**: Centralized data transformation from database models to JSON

**Default Field Mappings**:

```python
DEFAULT_ALBUM_FIELDS = {
    'id': None,
    'title': 'Unknown Album',
    'artist': 'Unknown Artist',      # Computed from album.artist.name
    'year': None,
    'artwork_path': None,            # ⚠️ snake_case
    'track_count': 0,                # ⚠️ snake_case
    'total_duration': 0              # ⚠️ Computed from tracks
}

DEFAULT_ARTIST_FIELDS = {
    'id': None,
    'name': 'Unknown Artist',
    'track_count': 0,                # ⚠️ snake_case
    'album_count': 0                 # ⚠️ snake_case
}

DEFAULT_TRACK_FIELDS = {
    'id': None,
    'title': 'Unknown',
    'filepath': '',
    'duration': 0,
    'format': 'Unknown'
}
```

**Observation**: Backend consistently uses snake_case. This is correct Python convention.

---

## Frontend Type System Issues

### Issue #1: Duplicate Type Definitions

**Files with conflicting Album types**:
1. `src/types/api.ts` (line 109) - Used for API responses
2. `src/types/domain.ts` (line 45) - Used for domain models

**Differences**:
- Both define `artwork_url` (backend uses `artwork_path`)
- Both include fields backend doesn't return (`genre`, `date_added`)
- Neither includes `total_duration` (backend returns this)

### Issue #2: Mixed Case Conventions

| Layer | Convention | Example |
|-------|-----------|---------|
| Backend API | snake_case | `track_count`, `artwork_path` |
| TypeScript Types | snake_case | `track_count`, `artwork_url` |
| Component Props | camelCase | `trackCount`, `hasArtwork`, `albumId` |
| WebSocket Types | snake_case | `gapless_enabled`, `crossfade_enabled` |

**Result**: No consistency between layers

### Issue #3: No Transformation Layer

**Current Flow**:
```
Backend → API (snake_case) → TanStack Query → Component (expects camelCase)
                                                      ↑
                                                   MISMATCH
```

**Required Flow**:
```
Backend → API (snake_case) → Transformer → Component (camelCase)
                                  ↓
                          Type-safe conversion
```

---

## Architectural Decisions

### Decision #1: Keep Backend snake_case ✅

**Rationale**:
- Python convention is snake_case
- Backend is consistent
- Changing backend would break existing contracts

**Action**: No change to backend

### Decision #2: Frontend Should Use camelCase ✅

**Rationale**:
- JavaScript/TypeScript convention is camelCase
- React components expect camelCase props
- Better developer experience

**Action**: Create transformation layer

### Decision #3: Single Source of Truth for Types

**Problem**: Duplicate definitions in `api.ts` and `domain.ts`

**Solution**:
- `domain.ts` = Frontend domain models (camelCase)
- `api.ts` = Backend API responses (snake_case)
- New: `transformers.ts` = Type-safe transformations

---

## Remediation Plan (Updated)

### Phase 1: ✅ COMPLETE
- Document all API endpoints
- Identify all contract mismatches
- Map backend → frontend data flows

### Phase 2: Create Transformation Layer (NEXT)

**Files to Create**:

1. **`src/api/transformers/types.ts`** - Backend response types (snake_case)
```typescript
// Exact backend response shapes
export interface AlbumApiResponse {
  id: number;
  title: string;
  artist: string;
  year: number | null;
  artwork_path: string | null;    // snake_case from backend
  track_count: number;             // snake_case from backend
  total_duration: number;          // snake_case from backend
}

export interface ArtistApiResponse {
  id: number;
  name: string;
  album_count: number;
  track_count: number;
  genres: string[] | null;
}
```

2. **`src/api/transformers/albumTransformer.ts`**
```typescript
import { AlbumApiResponse } from './types';
import { Album } from '@/types/domain';

export function transformAlbum(apiAlbum: AlbumApiResponse): Album {
  return {
    id: apiAlbum.id,
    title: apiAlbum.title,
    artist: apiAlbum.artist,
    year: apiAlbum.year,
    artworkUrl: apiAlbum.artwork_path,  // snake → camel
    trackCount: apiAlbum.track_count,    // snake → camel
    totalDuration: apiAlbum.total_duration, // snake → camel
  };
}

export function transformAlbums(apiAlbums: AlbumApiResponse[]): Album[] {
  return apiAlbums.map(transformAlbum);
}
```

3. **`src/api/transformers/index.ts`** - Barrel export
```typescript
export * from './albumTransformer';
export * from './artistTransformer';
export * from './trackTransformer';
export * from './types';
```

### Phase 3: Update Hooks to Use Transformers

**`src/hooks/library/useInfiniteAlbums.ts`**:
```typescript
import { transformAlbums } from '@/api/transformers';

export function useInfiniteAlbums(options: UseInfiniteAlbumsOptions = {}) {
  return useInfiniteQuery({
    queryKey: ['albums', { search, limit }],
    queryFn: async ({ pageParam }) => {
      const response = await fetchAlbums({ pageParam, limit, search });

      // Transform API response to domain models
      return {
        ...response,
        albums: transformAlbums(response.albums)
      };
    },
    // ...
  });
}
```

### Phase 4: Update Components to Use Domain Types

**`src/components/library/Items/albums/CozyAlbumGrid.tsx`**:
```typescript
import { Album } from '@/types/domain';

// albums is now Album[] with camelCase fields
{albums.map((album) => (
  <AlbumCard
    key={album.id}
    albumId={album.id}
    title={album.title}
    artist={album.artist}
    hasArtwork={!!album.artworkUrl}  // camelCase!
    trackCount={album.trackCount}     // camelCase!
    duration={album.totalDuration}    // camelCase!
    year={album.year}
    onClick={() => onAlbumClick?.(album.id)}
  />
))}
```

### Phase 5: Refactor AlbumCard to Accept Domain Model

**Option A: Accept `album` prop** (Modern)
```typescript
export interface AlbumCardProps {
  album: Album;  // Domain model
  onClick?: () => void;
  onArtworkUpdated?: () => void;
}
```

**Option B: Keep destructured props** (Current)
- Requires manual mapping in every parent component
- More verbose but explicit

**Recommendation**: Option A (cleaner, less boilerplate)

### Phase 6: Add Contract Tests

```typescript
// src/api/__tests__/albumTransformer.test.ts
describe('albumTransformer', () => {
  it('transforms snake_case API response to camelCase domain model', () => {
    const apiResponse: AlbumApiResponse = {
      id: 1,
      title: 'Test Album',
      artist: 'Test Artist',
      year: 2024,
      artwork_path: '/path/to/art.jpg',
      track_count: 12,
      total_duration: 3600
    };

    const result = transformAlbum(apiResponse);

    expect(result).toEqual({
      id: 1,
      title: 'Test Album',
      artist: 'Test Artist',
      year: 2024,
      artworkUrl: '/path/to/art.jpg',
      trackCount: 12,
      totalDuration: 3600
    });
  });
});
```

---

## Implementation Order

1. ✅ **Phase 1**: Complete API audit (DONE)
2. ✅ **Emergency Hotfix**: Fix AlbumCard mapping (DONE)
3. ⏭️ **Phase 2**: Create transformation layer
   - Create `src/api/transformers/` directory
   - Add backend response types (snake_case)
   - Implement transformers for Album, Artist, Track
4. ⏭️ **Phase 3**: Update `useInfiniteAlbums` to use transformer
5. ⏭️ **Phase 4**: Clean up `domain.ts` to use camelCase
6. ⏭️ **Phase 5**: Update AlbumCard to accept `album` prop
7. ⏭️ **Phase 6**: Repeat for Artists and Tracks
8. ⏭️ **Phase 7**: Add contract tests
9. ⏭️ **Phase 8**: Remove emergency hotfix mapping

---

## Success Metrics

✅ **Single source of truth**: One Album type in `domain.ts` (camelCase)
✅ **Type safety**: No `any` types, all transformations type-checked
✅ **Consistency**: All components use camelCase props
✅ **Maintainability**: Backend changes isolated to transformers
✅ **Testability**: Contract tests verify transformations

---

## Files Modified (Summary)

### Completed
- ✅ `API_CONTRACT_AUDIT.md` - Initial audit
- ✅ `CozyAlbumGrid.tsx` - Emergency hotfix

### To Create
- `src/api/transformers/types.ts`
- `src/api/transformers/albumTransformer.ts`
- `src/api/transformers/artistTransformer.ts`
- `src/api/transformers/trackTransformer.ts`
- `src/api/transformers/index.ts`
- `src/api/__tests__/albumTransformer.test.ts`

### To Modify
- `src/types/domain.ts` - Update to camelCase
- `src/hooks/library/useInfiniteAlbums.ts` - Use transformers
- `src/components/album/AlbumCard/AlbumCard.tsx` - Accept `album` prop
- All other list components (artists, tracks, playlists)

---

## Conclusion

The system needs a **transformation layer** to bridge backend snake_case and frontend camelCase conventions. This is standard practice in full-stack applications and should have been implemented from the start.

**Estimated Effort**:
- Phase 2 (transformers): 2-3 hours
- Phase 3-6 (integration): 4-6 hours
- Phase 7 (tests): 2-3 hours
- **Total**: 8-12 hours for complete system cleanup

**Benefits**:
- ✅ Type-safe data flow
- ✅ Single source of truth
- ✅ Easier to maintain
- ✅ Prevents future bugs
- ✅ Better developer experience
