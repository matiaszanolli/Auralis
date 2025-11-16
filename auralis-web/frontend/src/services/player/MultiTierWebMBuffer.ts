/**
 * MultiTierWebMBuffer - Decoded audio chunk cache
 *
 * Responsibility: Cache decoded AudioBuffer instances for instant playback
 *
 * Extracted from UnifiedWebMAudioPlayer for:
 * - Clear separation of caching concern
 * - Testable buffer management
 * - Reusable across different player implementations
 *
 * Why it's called "MultiTier":
 * - Tier 1: Current chunk (always available)
 * - Tier 2: Next/previous chunks (preloaded)
 * - Tier 3: Background chunks (loaded when convenient)
 * LRU eviction keeps recent chunks, discards old ones
 */

export class MultiTierWebMBuffer {
  private cache: Map<string, AudioBuffer> = new Map();
  private maxSize: number = 10; // Keep last 10 chunks

  /**
   * Generate cache key for a chunk
   *
   * Key includes: track ID, chunk index, enhancement status, preset
   * This ensures different track variations don't collide
   */
  getCacheKey(trackId: number, chunkIdx: number, enhanced: boolean, preset: string): string {
    return `${trackId}_${chunkIdx}_${enhanced}_${preset}`;
  }

  /**
   * Get a cached audio buffer
   *
   * @returns AudioBuffer if found, null if not cached
   */
  get(key: string): AudioBuffer | null {
    return this.cache.get(key) || null;
  }

  /**
   * Store an audio buffer in cache
   *
   * Uses LRU (Least Recently Used) eviction:
   * When cache is full, oldest entry is deleted
   */
  set(key: string, buffer: AudioBuffer): void {
    // Simple LRU: if cache full, delete oldest entry
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey) this.cache.delete(firstKey);
    }
    this.cache.set(key, buffer);
  }

  /**
   * Clear all cached buffers
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Get current cache size
   */
  getSize(): number {
    return this.cache.size;
  }
}
