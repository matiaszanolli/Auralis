/**
 * useQueueStatistics Hook
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides queue statistics and analytics.
 * Automatically recalculates when queue changes.
 *
 * Usage:
 * ```typescript
 * const {
 *   stats,
 *   topArtists,
 *   topAlbums,
 *   qualityRating,
 *   isEmpty
 * } = useQueueStatistics(queue);
 *
 * console.log(stats.totalDuration);
 * console.log(topArtists); // Top 5 artists
 * console.log(qualityRating); // Quality assessment
 * ```
 *
 * Features:
 * - Real-time statistics calculation
 * - Genre/artist/album distribution
 * - Duration analysis (min, max, average, median)
 * - Play quality assessment
 * - Queue comparison utilities
 *
 * @module hooks/player/useQueueStatistics
 */

import { useMemo } from 'react';
import { QueueStatistics, type QueueStats, type PropertyDistribution } from '@/utils/queue/queue_statistics';
import type { Track } from '@/types/domain';

/**
 * Top items from distribution (value and count)
 */
export interface TopItem {
  value: string | number;
  count: number;
  percentage: number;
}

/**
 * Quality assessment result
 */
export interface QualityAssessment {
  rating: 'excellent' | 'good' | 'fair' | 'poor';
  issues: string[];
}

/**
 * Return type for useQueueStatistics hook
 */
export interface QueueStatisticsActions {
  /** Complete queue statistics */
  stats: QueueStats;

  /** Top 5 artists by track count */
  topArtists: TopItem[];

  /** Top 5 albums by track count */
  topAlbums: TopItem[];

  /** Top 5 formats by track count */
  topFormats: TopItem[];

  /** Genre distribution (if available) */
  genres: TopItem[];

  /** Quality assessment of queue */
  qualityRating: QualityAssessment;

  /** Whether queue is empty */
  isEmpty: boolean;

  /** Get distribution percentages for any property */
  getDistributionPercentages: (distribution: PropertyDistribution) => Map<string | number, number>;

  /** Compare with another queue */
  compareWith: (otherQueue: Track[]) => {
    added: number;
    removed: number;
    moved: number;
    similarity: number;
  };
}

/**
 * Hook for analyzing queue statistics
 *
 * ⚠️ **IMPORTANT: Queue Size Constraints**
 * This hook is optimized for playback queues (100-500 tracks).
 * DO NOT use with entire music library (will crash).
 *
 * Safe ranges:
 * - Optimal: 100-500 tracks
 * - Maximum: 1000 tracks (risky)
 * - Never: 10K+ tracks (will crash)
 *
 * @param queue Current queue tracks (max 500 recommended)
 * @returns Queue statistics and analysis
 *
 * @example
 * ```typescript
 * const { queue } = usePlaybackQueue();
 * const { stats, topArtists, qualityRating } = useQueueStatistics(queue);
 *
 * console.log(`Total duration: ${stats.estimatedPlayTime}`);
 * console.log(`Top artist: ${topArtists[0].value}`);
 * ```
 */
export function useQueueStatistics(queue: Track[]): QueueStatisticsActions {
  // Guard: Warn if queue exceeds safe size
  if (queue.length > 1000) {
    console.warn(
      `⚠️ useQueueStatistics: Queue size (${queue.length}) exceeds safe limit (1000). ` +
      `This hook is designed for playback queues only (100-500 tracks), not entire libraries. ` +
      `Using with large datasets will cause severe performance degradation or crashes. ` +
      `See: PHASE_7_ARCHITECTURAL_FIX.md for guidance.`
    );
  }
  const stats = useMemo(() => {
    return QueueStatistics.calculateStats(queue);
  }, [queue]);

  const topArtists = useMemo(() => {
    const items = QueueStatistics.getTopItems(stats.artists, 5);
    const percentages = QueueStatistics.getDistributionPercentages(
      stats.artists,
      queue.length
    );

    return items.map(([value, count]) => ({
      value,
      count,
      percentage: percentages.get(value) || 0,
    }));
  }, [stats.artists, queue.length]);

  const topAlbums = useMemo(() => {
    const items = QueueStatistics.getTopItems(stats.albums, 5);
    const percentages = QueueStatistics.getDistributionPercentages(
      stats.albums,
      queue.length
    );

    return items.map(([value, count]) => ({
      value,
      count,
      percentage: percentages.get(value) || 0,
    }));
  }, [stats.albums, queue.length]);

  const topFormats = useMemo(() => {
    const items = QueueStatistics.getTopItems(stats.formats, 5);
    const percentages = QueueStatistics.getDistributionPercentages(
      stats.formats,
      queue.length
    );

    return items.map(([value, count]) => ({
      value,
      count,
      percentage: percentages.get(value) || 0,
    }));
  }, [stats.formats, queue.length]);

  const genres = useMemo(() => {
    const items = QueueStatistics.getTopItems(stats.genres, 5);
    const percentages = QueueStatistics.getDistributionPercentages(
      stats.genres,
      queue.length
    );

    return items.map(([value, count]) => ({
      value,
      count,
      percentage: percentages.get(value) || 0,
    }));
  }, [stats.genres, queue.length]);

  const qualityRating = useMemo(() => {
    return QueueStatistics.assessPlayQuality(stats);
  }, [stats]);

  const getDistributionPercentages = (distribution: PropertyDistribution) => {
    return QueueStatistics.getDistributionPercentages(distribution, queue.length);
  };

  const compareWith = (otherQueue: Track[]) => {
    const comparison = QueueStatistics.compareQueues(queue, otherQueue);
    return {
      added: comparison.addedTracks.length,
      removed: comparison.removedTracks.length,
      moved: comparison.movedTracks.length,
      similarity: comparison.similarity,
    };
  };

  return {
    stats,
    topArtists,
    topAlbums,
    topFormats,
    genres,
    qualityRating,
    isEmpty: stats.isEmpty,
    getDistributionPercentages,
    compareWith,
  };
}
