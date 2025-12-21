# Transformation Layer Architecture

**Status**: ✅ Production Ready (Phases 1-8 Complete)
**Version**: 1.0.0
**Last Updated**: December 2025

## Overview

The transformation layer provides a systematic, type-safe conversion between backend API responses (snake_case) and frontend domain models (camelCase). It eliminates manual field mapping, prevents data contract mismatches, and provides a single source of truth for data shapes.

## Problem Statement

Before the transformation layer, the codebase had:

1. **No single source of truth** - Backend, TypeScript types, and components all defined incompatible interfaces
2. **Manual field mapping** - Components manually converted `track_count` → `trackCount` inline
3. **Duplicate type definitions** - Same entities (Album, Artist) defined in multiple files with different field names
4. **Runtime errors** - Missing field conversions caused empty UI elements and broken displays
5. **Patch-after-patch fixes** - Each new component required manual snake_case → camelCase mapping

**Example of the problem**:
```typescript
// Backend returns:
{ id: 1, title: "Album", track_count: 10, artwork_path: "/art.jpg" }

// Component expects:
{ id: 1, title: "Album", trackCount: 10, artworkUrl: "/art.jpg" }

// Result: Empty album cards, missing data
```

## Architecture

The transformation layer uses a **three-tier architecture**:

```
Backend API (snake_case)
         ↓
API Response Types (@/api/transformers/types.ts)
         ↓
Transformers (@/api/transformers/*.ts)
         ↓
Domain Models (@/types/domain.ts)
         ↓
Components (camelCase)
```

### Layer 1: Backend API Types

**Location**: `src/api/transformers/types.ts`

**Purpose**: Define exact backend contract types (snake_case)

**Example**:
```typescript
export interface AlbumApiResponse {
  id: number;
  title: string;
  artist: string;
  year: number | null;
  artwork_path: string | null;  // Backend field name (snake_case)
  track_count: number;           // Backend field name (snake_case)
  total_duration: number;        // Backend field name (snake_case)
}
```

**Rules**:
- Mirror backend JSON structure exactly
- Use snake_case field names
- Use `null` for optional fields (backend convention)
- One interface per backend entity type

### Layer 2: Transformers

**Location**: `src/api/transformers/albumTransformer.ts`, `artistTransformer.ts`, `trackTransformer.ts`

**Purpose**: Convert API types to domain models

**Example**:
```typescript
import type { AlbumApiResponse } from './types';
import type { Album } from '@/types/domain';

export function transformAlbum(apiAlbum: AlbumApiResponse): Album {
  return {
    id: apiAlbum.id,
    title: apiAlbum.title,
    artist: apiAlbum.artist,
    year: apiAlbum.year ?? undefined,              // null → undefined
    artworkUrl: apiAlbum.artwork_path ?? undefined, // snake → camel
    trackCount: apiAlbum.track_count,              // snake → camel
    totalDuration: apiAlbum.total_duration,        // snake → camel
  };
}

export function transformAlbums(apiAlbums: AlbumApiResponse[]): Album[] {
  return apiAlbums.map(transformAlbum);
}

export function transformAlbumsResponse(apiResponse: AlbumsApiResponse) {
  return {
    albums: transformAlbums(apiResponse.albums),
    total: apiResponse.total,
    offset: apiResponse.offset,
    limit: apiResponse.limit,
    hasMore: apiResponse.has_more,  // snake → camel
  };
}
```

**Rules**:
- One transformer file per entity type
- Pure functions (no side effects)
- Convert `null` → `undefined` for optional fields
- Convert snake_case → camelCase
- Export batch transformers (`transformAlbums`, `transformArtists`)
- Export response transformers for paginated data

### Layer 3: Domain Models

**Location**: `src/types/domain.ts`

**Purpose**: Single source of truth for frontend data shapes (camelCase)

**Example**:
```typescript
export interface Album {
  id: number;
  title: string;
  artist: string;
  artworkUrl?: string;      // camelCase, optional
  year?: number;
  genre?: string;
  trackCount: number;       // camelCase
  totalDuration?: number;   // camelCase
  dateAdded?: string;       // camelCase
}
```

**Rules**:
- Use camelCase field names
- Use `undefined` for optional fields (TypeScript convention)
- Document any complex fields
- Keep domain models pure (no API-specific fields)

## Usage

### In Data Fetching Hooks

Transform data at the fetching layer using TanStack Query:

```typescript
import { useInfiniteQuery } from '@tanstack/react-query';
import { transformAlbumsResponse } from '@/api/transformers';
import type { AlbumsApiResponse } from '@/api/transformers';

export function useInfiniteAlbums(options: UseInfiniteAlbumsOptions = {}) {
  const { limit = 50, search, enabled = true } = options;

  return useInfiniteQuery({
    queryKey: ['albums', { search, limit }],
    queryFn: async ({ pageParam }) => {
      // 1. Fetch raw API response (snake_case)
      const apiResponse: AlbumsApiResponse = await fetchAlbums({
        pageParam,
        limit,
        search,
      });

      // 2. Transform to domain model (camelCase)
      return transformAlbumsResponse(apiResponse);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      return lastPage.hasMore ? lastPage.offset + lastPage.limit : undefined;
    },
    enabled,
  });
}
```

### In Components

Components receive pre-transformed domain models:

```typescript
import type { Album } from '@/types/domain';

export const CozyAlbumGrid: React.FC = ({ onAlbumClick }) => {
  // Data already transformed by useInfiniteAlbums
  const { data } = useInfiniteAlbums({ limit: 50 });

  const albums = data?.pages.flatMap(page => page.albums) ?? [];

  return (
    <div>
      {albums.map((album) => (
        <AlbumCard
          key={album.id}
          albumId={album.id}
          title={album.title}
          artist={album.artist}
          hasArtwork={!!album.artworkUrl}    // ✅ camelCase
          trackCount={album.trackCount}      // ✅ camelCase
          duration={album.totalDuration}     // ✅ camelCase
          year={album.year}
          onClick={() => onAlbumClick?.(album.id)}
        />
      ))}
    </div>
  );
};
```

### In Tests

Use domain models for mock data:

```typescript
import type { Album } from '@/types/domain';

const mockAlbum: Album = {
  id: 1,
  title: 'Test Album',
  artist: 'Test Artist',
  year: 2023,
  trackCount: 10,              // camelCase
  artworkUrl: '/album.jpg',    // camelCase
  totalDuration: 2400,         // camelCase
};
```

## Adding New Transformers

### Step 1: Define Backend API Type

Add to `src/api/transformers/types.ts`:

```typescript
export interface PlaylistApiResponse {
  id: number;
  name: string;
  description: string | null;
  track_count: number;        // snake_case
  is_smart: boolean;          // snake_case
  created_at: string;         // snake_case
  modified_at: string;        // snake_case
}

export interface PlaylistsApiResponse {
  playlists: PlaylistApiResponse[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}
```

### Step 2: Create Transformer

Create `src/api/transformers/playlistTransformer.ts`:

```typescript
import type { PlaylistApiResponse, PlaylistsApiResponse } from './types';
import type { Playlist } from '@/types/domain';

export function transformPlaylist(apiPlaylist: PlaylistApiResponse): Playlist {
  return {
    id: apiPlaylist.id,
    name: apiPlaylist.name,
    description: apiPlaylist.description ?? undefined,
    trackCount: apiPlaylist.track_count,    // snake → camel
    isSmart: apiPlaylist.is_smart,          // snake → camel
    createdAt: apiPlaylist.created_at,      // snake → camel
    modifiedAt: apiPlaylist.modified_at,    // snake → camel
  };
}

export function transformPlaylists(apiPlaylists: PlaylistApiResponse[]): Playlist[] {
  return apiPlaylists.map(transformPlaylist);
}

export function transformPlaylistsResponse(apiResponse: PlaylistsApiResponse) {
  return {
    playlists: transformPlaylists(apiResponse.playlists),
    total: apiResponse.total,
    offset: apiResponse.offset,
    limit: apiResponse.limit,
    hasMore: apiResponse.has_more,
  };
}
```

### Step 3: Export from Index

Add to `src/api/transformers/index.ts`:

```typescript
export * from './playlistTransformer';
```

### Step 4: Update Domain Model

Add to `src/types/domain.ts`:

```typescript
export interface Playlist {
  id: number;
  name: string;
  description?: string;
  trackCount: number;     // camelCase
  isSmart: boolean;       // camelCase
  createdAt: string;      // camelCase
  modifiedAt: string;     // camelCase
}
```

### Step 5: Use in Hooks

```typescript
import { transformPlaylistsResponse } from '@/api/transformers';

export function useInfinitePlaylists() {
  return useInfiniteQuery({
    queryKey: ['playlists'],
    queryFn: async ({ pageParam }) => {
      const apiResponse = await fetchPlaylists({ pageParam });
      return transformPlaylistsResponse(apiResponse);  // Transform!
    },
  });
}
```

## Benefits

### Type Safety
- ✅ Compile-time checking of field conversions
- ✅ IDE autocomplete for transformed fields
- ✅ Catch missing field conversions during build

### Maintainability
- ✅ Single place to update when backend changes
- ✅ No manual field mapping in components
- ✅ Clear separation of concerns

### Consistency
- ✅ All frontend code uses camelCase
- ✅ All backend types use snake_case
- ✅ Systematic conversion layer

### Developer Experience
- ✅ Components work with clean domain models
- ✅ No need to remember backend field names
- ✅ Clear documentation of data contracts

## Testing Strategy

### Contract Tests

Verify transformers handle backend contracts correctly:

```typescript
describe('albumTransformer', () => {
  it('should transform snake_case API response to camelCase domain model', () => {
    const apiResponse: AlbumApiResponse = {
      id: 1,
      title: 'Test Album',
      artist: 'Test Artist',
      year: 2023,
      artwork_path: '/art.jpg',
      track_count: 10,
      total_duration: 2400,
    };

    const result = transformAlbum(apiResponse);

    expect(result).toEqual({
      id: 1,
      title: 'Test Album',
      artist: 'Test Artist',
      year: 2023,
      artworkUrl: '/art.jpg',    // snake → camel
      trackCount: 10,            // snake → camel
      totalDuration: 2400,       // snake → camel
    });
  });

  it('should convert null to undefined for optional fields', () => {
    const apiResponse: AlbumApiResponse = {
      id: 1,
      title: 'Test Album',
      artist: 'Test Artist',
      year: null,               // Backend null
      artwork_path: null,       // Backend null
      track_count: 10,
      total_duration: 2400,
    };

    const result = transformAlbum(apiResponse);

    expect(result.year).toBeUndefined();        // null → undefined
    expect(result.artworkUrl).toBeUndefined();  // null → undefined
  });
});
```

## Common Patterns

### Handling Nested Objects

```typescript
export function transformTrack(apiTrack: TrackApiResponse): Track {
  return {
    id: apiTrack.id,
    title: apiTrack.title,
    // Nested album transformation
    album: apiTrack.album ? transformAlbum(apiTrack.album) : undefined,
  };
}
```

### Handling Arrays

```typescript
export function transformTracks(apiTracks: TrackApiResponse[]): Track[] {
  return apiTracks.map(transformTrack);
}
```

### Handling Pagination

```typescript
export function transformTracksResponse(apiResponse: TracksApiResponse) {
  return {
    tracks: transformTracks(apiResponse.tracks),
    total: apiResponse.total,
    offset: apiResponse.offset,
    limit: apiResponse.limit,
    hasMore: apiResponse.has_more,  // snake → camel
  };
}
```

### Handling Enums

```typescript
// Backend uses lowercase strings
export type ApiEnhancementPreset = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';

// Frontend uses same strings (no transformation needed)
export type EnhancementPreset = 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';

export function transformEnhancementSettings(api: EnhancementSettingsApiResponse): EnhancementSettings {
  return {
    enabled: api.enabled,
    preset: api.preset as EnhancementPreset,  // Type cast (same values)
    intensity: api.intensity,
  };
}
```

## Migration Guide

### From Manual Mapping

**Before** (manual field mapping in components):
```typescript
const albums = apiResponse.albums.map(album => ({
  id: album.id,
  title: album.title,
  artist: album.artist,
  trackCount: album.track_count,      // Manual conversion
  artworkUrl: album.artwork_path,     // Manual conversion
}));
```

**After** (systematic transformation):
```typescript
import { transformAlbums } from '@/api/transformers';

const albums = transformAlbums(apiResponse.albums);
```

### From Inline Types

**Before** (types defined inline):
```typescript
interface Album {
  id: number;
  title: string;
  track_count: number;  // Snake case leaked into frontend
}
```

**After** (use domain models):
```typescript
import type { Album } from '@/types/domain';

// Album has trackCount (camelCase)
```

## Troubleshooting

### Issue: TypeScript errors about missing fields

**Symptom**: `Property 'trackCount' does not exist on type 'AlbumApiResponse'`

**Solution**: You're using an API type where you should use a domain model. Import from `@/types/domain`, not `@/api/transformers/types`.

### Issue: Runtime errors with undefined fields

**Symptom**: Album cards show empty data

**Solution**: Ensure transformation is applied in the data fetching hook:
```typescript
queryFn: async () => {
  const apiResponse = await fetchAlbums();
  return transformAlbumsResponse(apiResponse);  // Don't forget this!
}
```

### Issue: Tests fail with camelCase expectations

**Symptom**: Mock data has `track_count` but test expects `trackCount`

**Solution**: Use domain models for test data:
```typescript
import type { Album } from '@/types/domain';

const mockAlbum: Album = {
  trackCount: 10,  // camelCase, not track_count
};
```

## File Organization

```
src/
├── api/
│   └── transformers/
│       ├── index.ts                  # Barrel exports
│       ├── types.ts                  # Backend API types (snake_case)
│       ├── albumTransformer.ts       # Album transformation
│       ├── artistTransformer.ts      # Artist transformation
│       └── trackTransformer.ts       # Track transformation
├── types/
│   └── domain.ts                     # Domain models (camelCase)
├── hooks/
│   └── library/
│       ├── useInfiniteAlbums.ts      # Uses transformAlbumsResponse
│       ├── useInfiniteArtists.ts     # Uses transformArtistsResponse
│       └── useInfiniteTracks.ts      # Uses transformTracksResponse
└── components/
    └── library/
        └── Items/
            ├── albums/
            │   └── CozyAlbumGrid.tsx # Receives transformed data
            └── artists/
                └── CozyArtistList.tsx # Receives transformed data
```

## Related Documentation

- [TypeScript Strict Mode](https://www.typescriptlang.org/tsconfig#strict) - Type safety configuration
- [TanStack Query](https://tanstack.com/query/latest/docs/react/overview) - Data fetching with transformations
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html) - Separation of domain models from API contracts

## Version History

- **1.0.0** (December 2025) - Initial implementation (Phases 1-8 complete)
  - Created transformation layer architecture
  - Consolidated duplicate types
  - Updated all components to use domain models
  - Fixed audio sync bug (stereo sample count)
