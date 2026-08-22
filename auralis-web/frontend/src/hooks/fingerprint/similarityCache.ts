/**
 * Module-level LRU cache for `/tracks/{id}/similar` results.
 *
 * Split out of `useSimilarTracks` (#4629) so the key derivation and the
 * staleness rules can be tested without driving the hook, and so the hook stays
 * inside the 300-line convention.
 *
 * Two things this cache has to get right, both of which it previously did not:
 *
 * **Every parameter that reaches the wire must be in the key.** `use_graph`
 * selects between two different data sources on the backend — `true` reads
 * pre-computed edges via `KNNGraphBuilder.get_neighbors`, `false` recomputes
 * against the fitted model — and the two derive `rank` differently besides. It
 * was absent from the key, so asking for `useGraph: false` (the explicit "give
 * me fresh results, not the stored graph" escape hatch) silently returned the
 * earlier graph-backed answer, and vice versa.
 *
 * **A correct key alone does not make the cache coherent.** Even for one key,
 * `use_graph: true` can legitimately hold results from either source: the
 * backend falls back to the real-time path when the graph is empty. So an entry
 * cached before a graph rebuild is not equivalent to the same request after it.
 * The frontend never triggers a rebuild and gets no event when one happens
 * out-of-band, so there is nothing to invalidate *on*; entries expire instead.
 * That bounds staleness to CACHE_TTL_MS rather than "until 50 other keys evict
 * it", which is the situation the escape hatch was unusable in — right after new
 * tracks are fingerprinted and the stored graph has gone stale.
 */

import type { SimilarTrack } from './useSimilarTracks';

/** Maximum entries before the least-recently-used one is evicted. */
export const CACHE_MAX_ENTRIES = 50;

/**
 * How long an entry may be served.
 *
 * Long enough that reopening the modal or flipping between a few tracks still
 * hits, short enough that a graph rebuilt in the background is reflected without
 * a reload. Only an upper bound on staleness — not a correctness guarantee, see
 * the module docstring.
 */
export const CACHE_TTL_MS = 5 * 60 * 1000;

interface CacheEntry {
  results: SimilarTrack[];
  storedAt: number;
}

/** Map iteration order is insertion order, so the oldest entry is first. */
const similarityCache = new Map<string, CacheEntry>();

/**
 * Derive the cache key.
 *
 * Must cover every parameter `findSimilar` puts on the wire. Adding one to the
 * request without adding it here is exactly the defect #4629 reported.
 */
export function getCacheKey(
  trackId: number,
  limit: number,
  includeDetails: boolean,
  useGraph: boolean
): string {
  return `${trackId}:${limit}:${includeDetails}:${useGraph}`;
}

/**
 * Read an entry, or null when absent or expired.
 *
 * A hit is promoted to most-recent so the LRU ordering reflects use, not
 * insertion. An expired entry is deleted rather than merely skipped, so it stops
 * occupying one of the CACHE_MAX_ENTRIES slots.
 */
export function readSimilarityCache(key: string): SimilarTrack[] | null {
  const entry = similarityCache.get(key);
  if (!entry) return null;

  if (Date.now() - entry.storedAt > CACHE_TTL_MS) {
    similarityCache.delete(key);
    return null;
  }

  similarityCache.delete(key);
  similarityCache.set(key, entry);
  return entry.results;
}

/** Store an entry, evicting least-recently-used entries past the cap. */
export function writeSimilarityCache(key: string, results: SimilarTrack[]): void {
  // Delete first so a re-store moves the key to the most-recent position rather
  // than updating it in place at its old rank.
  similarityCache.delete(key);
  similarityCache.set(key, { results, storedAt: Date.now() });

  while (similarityCache.size > CACHE_MAX_ENTRIES) {
    const oldestKey = similarityCache.keys().next().value!;
    similarityCache.delete(oldestKey);
  }
}

/**
 * Drop every entry.
 *
 * The seam an event-driven invalidation would call if the frontend ever learns
 * that the similarity graph was rebuilt (it neither triggers nor observes that
 * today — see the module docstring). Until then its callers are the tests, which
 * need it because this cache is module-level state shared across cases.
 */
export function clearSimilarityCache(): void {
  similarityCache.clear();
}

/** Current entry count. Exposed for tests asserting eviction behaviour. */
export function similarityCacheSize(): number {
  return similarityCache.size;
}
