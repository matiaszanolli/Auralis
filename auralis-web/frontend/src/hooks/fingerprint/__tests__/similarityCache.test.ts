/**
 * Similarity result cache — issue #4629
 *
 * `use_graph` selects between two different backend data sources (pre-computed
 * K-NN edges vs. a fresh computation against the fitted model, which also derive
 * `rank` differently), but the cache key was
 * `${trackId}:${limit}:${includeDetails}` — `useGraph` absent. Asking for
 * `useGraph: false`, the explicit "give me fresh results" escape hatch, returned
 * the earlier graph-backed answer instead, and vice versa, until 50 other keys
 * evicted it.
 *
 * These pin the key's completeness, the LRU behaviour that had to survive the
 * extra dimension, and the TTL that bounds how long a pre-rebuild entry can be
 * served.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  CACHE_MAX_ENTRIES,
  CACHE_TTL_MS,
  clearSimilarityCache,
  getCacheKey,
  readSimilarityCache,
  similarityCacheSize,
  writeSimilarityCache,
} from '../similarityCache';
import type { SimilarTrack } from '../useSimilarTracks';

const track = (trackId: number): SimilarTrack[] => [
  { trackId, distance: 0.1, similarityScore: 0.9 },
];

beforeEach(() => {
  clearSimilarityCache();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('getCacheKey', () => {
  it('distinguishes the two useGraph values', () => {
    // The regression itself: these two produced an identical key.
    expect(getCacheKey(1, 10, true, true)).not.toBe(getCacheKey(1, 10, true, false));
  });

  it('covers every parameter that reaches the wire', () => {
    const base = getCacheKey(1, 10, true, true);

    expect(getCacheKey(2, 10, true, true)).not.toBe(base); // trackId
    expect(getCacheKey(1, 20, true, true)).not.toBe(base); // limit
    expect(getCacheKey(1, 10, false, true)).not.toBe(base); // includeDetails
    expect(getCacheKey(1, 10, true, false)).not.toBe(base); // useGraph
  });

  it('is stable for identical parameters', () => {
    expect(getCacheKey(1, 10, true, true)).toBe(getCacheKey(1, 10, true, true));
  });
});

describe('graph vs. real-time results never alias', () => {
  it('stores the two variants separately', () => {
    const graphKey = getCacheKey(1, 10, true, true);
    const freshKey = getCacheKey(1, 10, true, false);

    writeSimilarityCache(graphKey, track(100));
    writeSimilarityCache(freshKey, track(200));

    expect(readSimilarityCache(graphKey)?.[0].trackId).toBe(100);
    expect(readSimilarityCache(freshKey)?.[0].trackId).toBe(200);
  });

  it('a graph-backed entry is not served to a useGraph:false request', () => {
    writeSimilarityCache(getCacheKey(1, 10, true, true), track(100));

    // Pre-fix this returned the graph result; now it is a miss, so the hook
    // issues a real request.
    expect(readSimilarityCache(getCacheKey(1, 10, true, false))).toBeNull();
  });
});

describe('LRU behaviour survives the extra key dimension', () => {
  it('repeated identical calls still hit', () => {
    const key = getCacheKey(1, 10, true, true);
    writeSimilarityCache(key, track(100));

    expect(readSimilarityCache(key)).not.toBeNull();
    expect(readSimilarityCache(key)).not.toBeNull();
    expect(similarityCacheSize()).toBe(1);
  });

  it('never exceeds the cap', () => {
    for (let i = 0; i < CACHE_MAX_ENTRIES + 20; i += 1) {
      writeSimilarityCache(getCacheKey(i, 10, true, true), track(i));
    }
    expect(similarityCacheSize()).toBe(CACHE_MAX_ENTRIES);
  });

  it('evicts the least-recently-used entry, not the oldest-written', () => {
    for (let i = 0; i < CACHE_MAX_ENTRIES; i += 1) {
      writeSimilarityCache(getCacheKey(i, 10, true, true), track(i));
    }

    // Touch the oldest so it is no longer least-recently-used.
    const oldest = getCacheKey(0, 10, true, true);
    expect(readSimilarityCache(oldest)).not.toBeNull();

    writeSimilarityCache(getCacheKey(999, 10, true, true), track(999));

    expect(readSimilarityCache(oldest)).not.toBeNull();
    expect(readSimilarityCache(getCacheKey(1, 10, true, true))).toBeNull();
  });

  it('re-storing a key promotes it rather than keeping its old rank', () => {
    for (let i = 0; i < CACHE_MAX_ENTRIES; i += 1) {
      writeSimilarityCache(getCacheKey(i, 10, true, true), track(i));
    }

    const oldest = getCacheKey(0, 10, true, true);
    writeSimilarityCache(oldest, track(0));
    writeSimilarityCache(getCacheKey(999, 10, true, true), track(999));

    expect(readSimilarityCache(oldest)).not.toBeNull();
    expect(similarityCacheSize()).toBe(CACHE_MAX_ENTRIES);
  });
});

describe('TTL bounds how long a pre-rebuild entry is served', () => {
  it('serves an entry inside the window', () => {
    vi.useFakeTimers();
    const key = getCacheKey(1, 10, true, true);
    writeSimilarityCache(key, track(100));

    vi.advanceTimersByTime(CACHE_TTL_MS - 1);
    expect(readSimilarityCache(key)).not.toBeNull();
  });

  it('drops an entry past the window', () => {
    vi.useFakeTimers();
    const key = getCacheKey(1, 10, true, true);
    writeSimilarityCache(key, track(100));

    vi.advanceTimersByTime(CACHE_TTL_MS + 1);
    expect(readSimilarityCache(key)).toBeNull();
  });

  it('frees the slot rather than leaving a dead entry occupying it', () => {
    vi.useFakeTimers();
    const key = getCacheKey(1, 10, true, true);
    writeSimilarityCache(key, track(100));
    expect(similarityCacheSize()).toBe(1);

    vi.advanceTimersByTime(CACHE_TTL_MS + 1);
    readSimilarityCache(key);
    expect(similarityCacheSize()).toBe(0);
  });
});
