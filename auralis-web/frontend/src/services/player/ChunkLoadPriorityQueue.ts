/**
 * ChunkLoadPriorityQueue - Priority queue for chunk loading
 *
 * Responsibility: Manage chunk loading order based on playback context
 *
 * Extracted from UnifiedWebMAudioPlayer for:
 * - Clear separation of queue management concern
 * - Testable priority logic
 * - Reusable across different preload strategies
 *
 * Priority Levels (lower number = higher priority):
 * 1. CRITICAL (0): Chunk currently being played
 * 2. IMMEDIATE (1): Next chunk needed for continuous playback
 * 3. SEEK_TARGET (2): Chunk user just seeked to
 * 4. ADJACENT (3): Chunks ±1 around current position
 * 5. BACKGROUND (4): All other chunks
 */

export enum ChunkLoadPriority {
  CRITICAL = 0,      // Currently playing chunk - load first!
  IMMEDIATE = 1,     // Next chunk needed for seamless playback
  SEEK_TARGET = 2,   // User just seeked here
  ADJACENT = 3,      // Chunks next to current position
  BACKGROUND = 4     // Everything else (load when convenient)
}

interface QueueItem {
  chunkIndex: number;
  priority: number;
  timestamp: number;
}

export class ChunkLoadPriorityQueue {
  private queue: QueueItem[] = [];
  private activeLoads = new Map<number, Promise<void>>();

  /**
   * Add or update chunk in queue with given priority
   * If chunk already exists, updates its priority and moves it appropriately
   *
   * @param chunkIndex - Index of chunk to load
   * @param priority - Priority level (0=highest, 4=lowest)
   */
  enqueue(chunkIndex: number, priority: number): void {
    // Remove existing entry if present (will re-add with new priority)
    this.queue = this.queue.filter(item => item.chunkIndex !== chunkIndex);

    // Add with new priority and current timestamp
    this.queue.push({
      chunkIndex,
      priority,
      timestamp: Date.now()
    });

    // Sort by priority (ascending - lower numbers first), then by timestamp (descending - newer first)
    this.queue.sort((a, b) => {
      if (a.priority !== b.priority) {
        return a.priority - b.priority; // Lower priority number comes first (more urgent)
      }
      return b.timestamp - a.timestamp; // Same priority: newer items first
    });
  }

  /**
   * Get next chunk to load based on priority
   * Removes item from queue
   *
   * @returns Next item to load, or null if queue empty
   */
  dequeue(): { chunkIndex: number; priority: number } | null {
    if (this.queue.length === 0) return null;

    const item = this.queue.shift();
    if (!item) return null;

    return {
      chunkIndex: item.chunkIndex,
      priority: item.priority
    };
  }

  /**
   * Remove all chunks with priority level >= threshold
   * Useful when user seeks: discard low-priority background loads
   *
   * @param priority - Threshold priority level
   */
  clearLowerPriority(priority: number): void {
    this.queue = this.queue.filter(item => item.priority <= priority);
  }

  /**
   * Clear entire queue
   * Used when stopping playback or loading new track
   */
  clear(): void {
    this.queue = [];
  }

  /**
   * Check if chunk is queued or currently loading
   * Prevents duplicate load requests
   */
  isQueued(chunkIndex: number): boolean {
    return this.queue.some(item => item.chunkIndex === chunkIndex) ||
           this.activeLoads.has(chunkIndex);
  }

  /**
   * Get current queue size (doesn't include currently loading)
   */
  getSize(): number {
    return this.queue.length;
  }

  /**
   * Get total chunks in queue + currently loading
   */
  getTotalPending(): number {
    return this.queue.length + this.activeLoads.size;
  }

  /**
   * Mark a chunk as actively loading
   * Removes from queue and tracks in activeLoads map
   * Automatically removes when promise settles (resolves or rejects)
   *
   * @param chunkIndex - Index of chunk being loaded
   * @param promise - Load promise that will complete
   */
  markActive(chunkIndex: number, promise: Promise<void>): void {
    this.activeLoads.set(chunkIndex, promise);
    promise.finally(() => {
      this.activeLoads.delete(chunkIndex);
    });
  }

  /**
   * Check if chunk is currently loading
   */
  isLoading(chunkIndex: number): boolean {
    return this.activeLoads.has(chunkIndex);
  }

  /**
   * Get number of chunks currently loading
   */
  getLoadingCount(): number {
    return this.activeLoads.size;
  }
}
