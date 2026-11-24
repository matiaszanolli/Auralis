# API Contract Audit - System-Wide Analysis

**Date**: 2025-12-20
**Status**: CRITICAL - Multiple architectural mismatches found
**Priority**: Blocking production readiness

---

## Executive Summary

Comprehensive audit reveals **architectural contract mismatches** between:
1. Backend API responses (Python/FastAPI)
2. TypeScript type definitions (`src/types/`)
3. React component prop interfaces
4. Data transformation logic

**Root Cause**: No single source of truth for data contracts. Backend, types, and components define incompatible shapes.

---

## Critical Mismatch #1: Album Data Contract

### Backend Returns (`/api/albums`)
Source: `auralis-web/backend/routers/albums.py` lines 103-111

```json
{
  "albums": [
    {
      "id": number,
      "title": string,
      "artist": string,
      "year": number | null,
      "artwork_path": string | null,  // ⚠️ MISMATCH
      "track_count": number,          // ⚠️ snake_case
      "total_duration": number        // ⚠️ Missing from types
    }
  ],
  "total": number,
  "offset": number,
  "limit": number,
  "has_more": boolean
}
```

### TypeScript Type Definitions
Source: `src/types/api.ts` lines 109-118 AND `src/types/domain.ts` lines 45-60

```typescript
export interface Album {
  id: number;
  title: string;
  artist: string;
  artwork_url?: string;    // ❌ Backend returns "artwork_path"
  track_count: number;
  year?: number;
  genre?: string;          // ❌ Backend doesn't return this
  date_added?: string;     // ❌ Backend doesn't return this
  // ❌ Missing: total_duration
}
```

### AlbumCard Component Props
Source: `src/components/album/AlbumCard/AlbumCard.tsx` lines 23-33

```typescript
export interface AlbumCardProps {
  albumId: number;         // ❌ Backend returns "id"
  title: string;
  artist: string;
  hasArtwork?: boolean;    // ❌ Backend returns "artwork_path" (string | null)
  trackCount?: number;     // ❌ Backend returns "track_count" (snake_case)
  duration?: number;       // ❌ Backend returns "total_duration"
  year?: number;
  onClick?: () => void;
  onArtworkUpdated?: () => void;
}
```

### Current Usage in CozyAlbumGrid
Source: `src/components/library/Items/albums/CozyAlbumGrid.tsx` lines 121-127

```tsx
{albums.map((album) => (
  <AlbumCard
    key={album.id}
    album={album}          // ❌ CRITICAL: AlbumCard doesn't have "album" prop!
    onClick={() => onAlbumClick?.(album.id)}
  />
))}
```

**Result**: AlbumCard receives `album={...}` but expects individual props → Empty cards displayed

---

## Critical Mismatch #2: Case Convention Inconsistency

### Backend Convention
- **snake_case** everywhere: `track_count`, `artwork_path`, `total_duration`, `has_more`

### Frontend Expectations
- **camelCase** in components: `albumId`, `trackCount`, `hasArtwork`
- **snake_case** in types: `track_count`, `artwork_url` (inconsistent!)

### Issue
No consistent transformation layer between API responses and component consumption.

---

## Critical Mismatch #3: Artwork Data Type

| Layer | Field Name | Type | Notes |
|-------|-----------|------|-------|
| Backend API | `artwork_path` | `string \| null` | File path on server |
| TypeScript Types | `artwork_url` | `string \| undefined` | ❌ Wrong field name |
| AlbumCard Props | `hasArtwork` | `boolean \| undefined` | ❌ Wrong type |
| ArtworkContainer | `albumId` + `hasArtwork` | number + boolean | Fetches URL internally |

**Flow**: Backend returns path → Frontend expects URL → Component expects boolean → No data flows through!

---

## Critical Mismatch #4: useInfiniteAlbums Hook

### Expected Response Format
Source: `src/hooks/library/useInfiniteAlbums.ts` lines 13-19

```typescript
interface AlbumsResponse {
  albums: Album[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}
```

### Actual Backend Response
✅ **MATCHES** - Backend returns exact structure (see albums.py lines 113-119)

### Problem
The `Album[]` array contains backend snake_case fields, but components expect camelCase props.

---

## Architectural Inconsistencies

### Issue 1: Duplicate Type Definitions
- `src/types/api.ts` defines `Album` interface
- `src/types/domain.ts` ALSO defines `Album` interface
- Both are slightly different
- No clear indication which is canonical

### Issue 2: No Data Transformation Layer
- API responses flow directly to components
- No serializer/deserializer pattern
- snake_case → camelCase conversion missing
- Field name mapping (artwork_path → artwork_url) missing

### Issue 3: Component Prop Design Mismatch
AlbumCard expects destructured props:
```tsx
<AlbumCard
  albumId={123}
  title="Album Name"
  artist="Artist Name"
  ...
/>
```

But modern pattern would be:
```tsx
<AlbumCard album={album} onClick={...} />
```

### Issue 4: Type Safety Not Enforced
- `useInfiniteAlbums` returns `Album` type
- CozyAlbumGrid uses it as `album.id`, `album.title`
- AlbumCard expects different prop names
- TypeScript doesn't catch the mismatch because types are defined with `any` escape hatches

---

## Complete API Surface (Phase 1)

### REST Endpoints

| Endpoint | Method | Request | Response | Status |
|----------|--------|---------|----------|--------|
| `/api/albums` | GET | `limit, offset, search, order_by` | `AlbumsResponse` | ✅ Implemented |
| `/api/albums/{id}` | GET | `album_id` | `Album` | ✅ Implemented |
| `/api/albums/{id}/tracks` | GET | `album_id` | `AlbumTracksResponse` | ✅ Implemented |
| `/api/artists` | GET | `limit, offset, search` | `ArtistsResponse` | ⚠️ Not audited |
| `/api/artists/{id}` | GET | `artist_id` | `Artist` | ⚠️ Not audited |
| `/api/library/tracks` | GET | `limit, offset, search` | `TracksResponse` | ⚠️ Not audited |
| `/api/player/play` | POST | `PlayerPlayRequest` | `PlayerState` | ⚠️ Not audited |
| `/api/player/pause` | POST | - | `PlayerState` | ⚠️ Not audited |
| `/api/player/stop` | POST | - | `PlayerState` | ⚠️ Not audited |
| `/api/player/seek` | POST | `PlayerSeekRequest` | `PlayerState` | ⚠️ Not audited |
| `/api/enhancement/presets` | GET | - | `EnhancementPresetsResponse` | ⚠️ Not audited |

### WebSocket Messages

| Message Type | Direction | Payload | Status |
|--------------|-----------|---------|--------|
| `player_state` | Server → Client | `PlayerState` | ⚠️ Not audited |
| `play_enhanced` | Client → Server | `{ track_id, preset, intensity }` | ⚠️ Not audited |
| `audio_stream_start` | Server → Client | `{ sample_rate, channels, total_chunks }` | ⚠️ Not audited |
| `audio_chunk` | Server → Client | `{ chunk_data }` | ⚠️ Not audited |

---

## Remediation Strategy

### Immediate Fixes (Blocking)

1. **Fix AlbumCard Usage** (CRITICAL)
   - Update CozyAlbumGrid to pass individual props instead of `album={album}`
   - OR: Refactor AlbumCard to accept `album` prop

2. **Add Data Transformation Layer**
   - Create `transformAlbumData(apiAlbum): AlbumCardProps`
   - Map snake_case → camelCase
   - Map `artwork_path` → `hasArtwork`
   - Add `total_duration` → `duration`

3. **Consolidate Type Definitions**
   - Choose ONE Album type (recommend `domain.ts`)
   - Delete duplicate from `api.ts`
   - Update to match backend contract exactly

### Systematic Approach (Comprehensive)

**Phase 1**: ✅ Document complete API surface (IN PROGRESS)

**Phase 2**: Audit all data types
- Map backend response → TypeScript types → Component props
- Identify all mismatches
- Create transformation functions

**Phase 3**: Create transformation layer
- `src/api/transformers/` directory
- One transformer per entity (album, artist, track)
- Consistent camelCase conversion
- Type-safe transformations

**Phase 4**: Update all components
- Use transformed data
- Remove manual field mapping
- Add TypeScript strict mode

**Phase 5**: Add API contract tests
- Backend: Response format tests
- Frontend: Type validation tests
- Integration: End-to-end contract tests

---

## Next Steps

1. ✅ Complete Phase 1 (API surface documentation)
2. ⏭️ Create emergency hotfix for AlbumCard
3. ⏭️ Audit remaining endpoints (artists, tracks, player, enhancement)
4. ⏭️ Map all WebSocket message types
5. ⏭️ Create comprehensive transformation layer
6. ⏭️ Implement systematic fixes

---

## Files Modified

None yet - this is documentation phase.

## Files To Modify (Phase 2+)

### Immediate Hotfix
- `src/components/library/Items/albums/CozyAlbumGrid.tsx` - Fix AlbumCard props
- `src/types/api.ts` OR `src/types/domain.ts` - Consolidate Album type

### Systematic Fix
- Create `src/api/transformers/albumTransformer.ts`
- Update `src/hooks/library/useInfiniteAlbums.ts` to use transformer
- Update all Album-consuming components
- Add contract tests in `src/api/__tests__/`
