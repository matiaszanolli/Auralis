/**
 * Queue Statistics Utility
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides statistical analysis and analytics for queue contents.
 * Calculates queue metrics, genre distribution, duration stats, and more.
 *
 * Usage:
 * ```typescript
 * import { QueueStatistics } from '@/utils/queue/queue_statistics';
 *
 * const stats = QueueStatistics.calculateStats(queue);
 * console.log(stats.totalDuration); // Total queue duration in seconds
 * console.log(stats.averageDuration); // Average track length
 * console.log(stats.genreDistribution); // Genre breakdown
 * ```
 */

import type { Track } from '@/types/domain';

/**
 * Statistics for a single track property distribution
 */
export interface PropertyDistribution {
  /** Most common value */
  mode: string | number | null;

  /** Least common value */
  least: string | number | null;

  /** Number of unique values */
  unique: number;

  /** All values with counts */
  distribution: Map<string | number, number>;
}

/**
 * Complete queue statistics
 */
export interface QueueStats {
  // Basic counts
  trackCount: number;
  uniqueArtists: number;
  uniqueAlbums: number;

  // Duration metrics
  totalDuration: number; // in seconds
  averageDuration: number;
  minDuration: number;
  maxDuration: number;
  medianDuration: number;

  // Genre distribution
  genres: PropertyDistribution;

  // Artist distribution
  artists: PropertyDistribution;

  // Album distribution
  albums: PropertyDistribution;

  // Format distribution
  formats: PropertyDistribution;

  // Additional info
  isEmpty: boolean;
  estimatedPlayTime: string; // Formatted string like "2h 45m"
}

/**
 * Queue Statistics utility class
 */
export class QueueStatistics {
  /**
   * Calculate complete statistics for a queue
   *
   * @param queue Array of tracks
   * @returns Complete statistics object
   */
  static calculateStats(queue: Track[]): QueueStats {
    if (queue.length === 0) {
      return this.getEmptyStats();
    }

    const trackCount = queue.length;
    const durations = queue.map((t) => t.duration);
    const totalDuration = durations.reduce((sum, d) => sum + d, 0);
    const averageDuration = totalDuration / trackCount;
    const sortedDurations = [...durations].sort((a, b) => a - b);
    const minDuration = sortedDurations[0];
    const maxDuration = sortedDurations[trackCount - 1];
    const medianDuration =
      trackCount % 2 === 0
        ? (sortedDurations[trackCount / 2 - 1] + sortedDurations[trackCount / 2]) / 2
        : sortedDurations[Math.floor(trackCount / 2)];

    const uniqueArtists = new Set(queue.map((t) => t.artist)).size;
    const uniqueAlbums = new Set(queue.map((t) => t.album)).size;

    // Build distributions
    const genres = this.buildDistribution(
      queue.map((t) => this.extractGenre(t))
    );
    const artists = this.buildDistribution(queue.map((t) => t.artist));
    const albums = this.buildDistribution(queue.map((t) => t.album));
    const formats = this.buildDistribution(
      queue.map((t) => this.extractFormat(t.filepath))
    );

    return {
      trackCount,
      uniqueArtists,
      uniqueAlbums,
      totalDuration,
      averageDuration,
      minDuration,
      maxDuration,
      medianDuration,
      genres,
      artists,
      albums,
      formats,
      isEmpty: false,
      estimatedPlayTime: this.formatDuration(totalDuration),
    };
  }

  /**
   * Get empty queue statistics
   */
  private static getEmptyStats(): QueueStats {
    const emptyDistribution: PropertyDistribution = {
      mode: null,
      least: null,
      unique: 0,
      distribution: new Map(),
    };

    return {
      trackCount: 0,
      uniqueArtists: 0,
      uniqueAlbums: 0,
      totalDuration: 0,
      averageDuration: 0,
      minDuration: 0,
      maxDuration: 0,
      medianDuration: 0,
      genres: emptyDistribution,
      artists: emptyDistribution,
      albums: emptyDistribution,
      formats: emptyDistribution,
      isEmpty: true,
      estimatedPlayTime: '0m',
    };
  }

  /**
   * Build distribution statistics from array of values
   */
  private static buildDistribution(values: (string | number)[]): PropertyDistribution {
    const distribution = new Map<string | number, number>();

    // Count occurrences
    for (const value of values) {
      if (value === null || value === undefined || value === '') {
        continue;
      }
      distribution.set(value, (distribution.get(value) || 0) + 1);
    }

    if (distribution.size === 0) {
      return {
        mode: null,
        least: null,
        unique: 0,
        distribution,
      };
    }

    // Find mode (most common)
    let mode: string | number | null = null;
    let maxCount = 0;
    for (const [value, count] of distribution.entries()) {
      if (count > maxCount) {
        maxCount = count;
        mode = value;
      }
    }

    // Find least common
    let least: string | number | null = null;
    let minCount = Infinity;
    for (const [value, count] of distribution.entries()) {
      if (count < minCount) {
        minCount = count;
        least = value;
      }
    }

    return {
      mode,
      least,
      unique: distribution.size,
      distribution,
    };
  }

  /**
   * Extract file format from filepath
   */
  private static extractFormat(filepath: string): string {
    if (!filepath) return 'unknown';
    const match = filepath.match(/\.([a-z0-9]+)$/i);
    return match ? match[1].toLowerCase() : 'unknown';
  }

  /**
   * Extract genre from track metadata
   * (assumes genre is stored in track object or derived from metadata)
   */
  private static extractGenre(track: Track): string {
    // For now, we'll use a placeholder
    // In a real app, this would read from track metadata
    return 'unknown';
  }

  /**
   * Format duration in seconds to human-readable string
   */
  private static formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    }
    return `${secs}s`;
  }

  /**
   * Get top N items from distribution
   */
  static getTopItems(
    distribution: PropertyDistribution,
    count: number = 5
  ): Array<[string | number, number]> {
    const sorted = Array.from(distribution.distribution.entries()).sort(
      (a, b) => b[1] - a[1]
    );

    return sorted.slice(0, count);
  }

  /**
   * Get distribution as percentage
   */
  static getDistributionPercentages(
    distribution: PropertyDistribution,
    total: number
  ): Map<string | number, number> {
    const percentages = new Map<string | number, number>();

    for (const [value, count] of distribution.distribution.entries()) {
      percentages.set(value, (count / total) * 100);
    }

    return percentages;
  }

  /**
   * Check if queue is suitable for continuous playback
   * (all tracks are reasonable length)
   */
  static assessPlayQuality(stats: QueueStats): {
    rating: 'excellent' | 'good' | 'fair' | 'poor';
    issues: string[];
  } {
    const issues: string[] = [];

    if (stats.isEmpty) {
      return {
        rating: 'poor',
        issues: ['Queue is empty'],
      };
    }

    // Check for very short tracks
    if (stats.minDuration < 10) {
      issues.push(`Very short tracks detected (${stats.minDuration}s minimum)`);
    }

    // Check for very long tracks
    if (stats.maxDuration > 600) {
      issues.push(`Very long tracks detected (${stats.maxDuration}s maximum)`);
    }

    // Check for duration consistency
    const durationVariance =
      (stats.maxDuration - stats.minDuration) / stats.averageDuration;
    if (durationVariance > 3) {
      issues.push('Highly variable track lengths (may affect crossfading)');
    }

    // Check for diversity
    if (stats.uniqueArtists < 3 && stats.trackCount > 10) {
      issues.push('Low artist diversity (consider adding more variety)');
    }

    // Determine rating
    let rating: 'excellent' | 'good' | 'fair' | 'poor' = 'excellent';
    if (issues.length >= 3) {
      rating = 'poor';
    } else if (issues.length === 2) {
      rating = 'fair';
    } else if (issues.length === 1) {
      rating = 'good';
    }

    return { rating, issues };
  }

  /**
   * Compare two queues
   */
  static compareQueues(
    queue1: Track[],
    queue2: Track[]
  ): {
    addedTracks: Track[];
    removedTracks: Track[];
    movedTracks: Track[];
    similarity: number; // 0-1
  } {
    const ids1 = new Set(queue1.map((t) => t.id));
    const ids2 = new Set(queue2.map((t) => t.id));

    const addedTracks = queue2.filter((t) => !ids1.has(t.id));
    const removedTracks = queue1.filter((t) => !ids2.has(t.id));

    // Calculate Jaccard similarity
    const intersection = queue1.filter((t) => ids2.has(t.id)).length;
    const union = queue1.length + queue2.length - intersection;
    const similarity = union === 0 ? 1 : intersection / union;

    // Find moved tracks (same tracks but different positions)
    const movedTracks: Track[] = [];
    for (const track of queue1) {
      if (ids2.has(track.id)) {
        const oldIndex = queue1.indexOf(track);
        const newIndex = queue2.findIndex((t) => t.id === track.id);
        if (oldIndex !== newIndex) {
          movedTracks.push(track);
        }
      }
    }

    return {
      addedTracks,
      removedTracks,
      movedTracks,
      similarity,
    };
  }
}
