/**
 * Queue Shuffler Utility
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Provides advanced shuffle algorithms for playback order.
 * Supports multiple shuffle modes beyond standard random shuffling.
 *
 * Shuffle Modes:
 * - RANDOM: Standard random shuffle
 * - WEIGHTED: Biased shuffle (prefer highly-rated tracks)
 * - ALBUM: Keep album tracks together, shuffle albums
 * - ARTIST: Keep artist tracks together, shuffle artists
 * - TEMPORAL: Shuffle preserving recent/older track distribution
 * - NO_REPEAT: Avoid similar tracks appearing close together
 *
 * Usage:
 * ```typescript
 * import { QueueShuffler } from '@/utils/queue/queue_shuffler';
 *
 * const shuffled = QueueShuffler.shuffle(queue, 'weighted');
 * const groupedShuffled = QueueShuffler.shuffle(queue, 'album');
 * ```
 */

import type { Track } from '@/types/domain';

/**
 * Shuffle mode type
 */
export type ShuffleMode = 'random' | 'weighted' | 'album' | 'artist' | 'temporal' | 'no_repeat';

/**
 * Shuffle configuration
 */
export interface ShuffleOptions {
  /** Seed for reproducible shuffles */
  seed?: number;

  /** Preserve start position (for weighted/intelligent shuffles) */
  keepStart?: boolean;

  /** Minimum distance between similar tracks */
  minSimilarityDistance?: number;
}

/**
 * Queue Shuffler utility class
 */
export class QueueShuffler {
  /**
   * Shuffle queue using specified mode
   */
  static shuffle(
    queue: Track[],
    mode: ShuffleMode = 'random',
    options: ShuffleOptions = {}
  ): Track[] {
    if (queue.length <= 1) return [...queue];

    switch (mode) {
      case 'random':
        return this.shuffleRandom(queue, options);
      case 'weighted':
        return this.shuffleWeighted(queue, options);
      case 'album':
        return this.shuffleByAlbum(queue, options);
      case 'artist':
        return this.shuffleByArtist(queue, options);
      case 'temporal':
        return this.shuffleTemporal(queue, options);
      case 'no_repeat':
        return this.shuffleNoRepeat(queue, options);
      default:
        return this.shuffleRandom(queue, options);
    }
  }

  /**
   * Standard random shuffle (Fisher-Yates)
   */
  private static shuffleRandom(
    queue: Track[],
    options: ShuffleOptions
  ): Track[] {
    const shuffled = [...queue];
    const rng = options.seed !== undefined ? this.seededRandom(options.seed) : Math.random;

    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }

    return shuffled;
  }

  /**
   * Weighted shuffle - prefer high-duration tracks earlier
   * (simulates "liked/important" tracks appearing more often)
   */
  private static shuffleWeighted(
    queue: Track[],
    options: ShuffleOptions
  ): Track[] {
    const shuffled = [...queue];

    // Calculate weights based on track properties
    const weights = shuffled.map((track) => {
      // Weight = duration (longer tracks get higher weight)
      // This simulates preferring tracks that get more playtime
      return Math.max(track.duration / 10, 1); // Normalize to reasonable scale
    });

    // Weighted Fisher-Yates shuffle
    const rng = options.seed !== undefined ? this.seededRandom(options.seed) : Math.random;

    for (let i = shuffled.length - 1; i > 0; i--) {
      // Select weighted random index
      const j = this.weightedRandomIndex(weights.slice(0, i + 1), rng);
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];

      // Swap weights too
      [weights[i], weights[j]] = [weights[j], weights[i]];
    }

    return shuffled;
  }

  /**
   * Album shuffle - keep album tracks together, shuffle album order
   */
  private static shuffleByAlbum(
    queue: Track[],
    options: ShuffleOptions
  ): Track[] {
    // Group tracks by album
    const albumGroups = new Map<string, Track[]>();

    for (const track of queue) {
      const album = track.album || 'Unknown Album';
      if (!albumGroups.has(album)) {
        albumGroups.set(album, []);
      }
      albumGroups.get(album)!.push(track);
    }

    // Shuffle album order
    const albums = Array.from(albumGroups.values());
    const rng = options.seed !== undefined ? this.seededRandom(options.seed) : Math.random;

    for (let i = albums.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [albums[i], albums[j]] = [albums[j], albums[i]];
    }

    // Flatten back to track list
    const shuffled: Track[] = [];
    for (const album of albums) {
      shuffled.push(...album);
    }

    return shuffled;
  }

  /**
   * Artist shuffle - keep artist tracks together, shuffle artist order
   */
  private static shuffleByArtist(
    queue: Track[],
    options: ShuffleOptions
  ): Track[] {
    // Group tracks by artist
    const artistGroups = new Map<string, Track[]>();

    for (const track of queue) {
      const artist = track.artist;
      if (!artistGroups.has(artist)) {
        artistGroups.set(artist, []);
      }
      artistGroups.get(artist)!.push(track);
    }

    // Shuffle artist order
    const artists = Array.from(artistGroups.values());
    const rng = options.seed !== undefined ? this.seededRandom(options.seed) : Math.random;

    for (let i = artists.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [artists[i], artists[j]] = [artists[j], artists[i]];
    }

    // Flatten back to track list
    const shuffled: Track[] = [];
    for (const artist of artists) {
      shuffled.push(...artist);
    }

    return shuffled;
  }

  /**
   * Temporal shuffle - preserve distribution of old/new tracks
   * Shuffles while maintaining relative chronological order patterns
   */
  private static shuffleTemporal(
    queue: Track[],
    options: ShuffleOptions
  ): Track[] {
    const shuffled = [...queue];
    const rng = options.seed !== undefined ? this.seededRandom(options.seed) : Math.random;

    // Calculate "temporal weight" based on position (older tracks have higher weight)
    const weights = shuffled.map((_, i) => {
      // Earlier tracks (higher indices conceptually) get higher weight
      return (queue.length - i) / queue.length;
    });

    // Weighted shuffle
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = this.weightedRandomIndex(weights.slice(0, i + 1), rng);
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
      [weights[i], weights[j]] = [weights[j], weights[i]];
    }

    return shuffled;
  }

  /**
   * No-repeat shuffle - avoid similar tracks appearing close together
   */
  private static shuffleNoRepeat(
    queue: Track[],
    options: ShuffleOptions
  ): Track[] {
    const minDistance = options.minSimilarityDistance ?? 2;
    const shuffled: Track[] = [];
    const available = new Set(queue.map((_, i) => i));
    const rng = options.seed !== undefined ? this.seededRandom(options.seed) : Math.random;

    // Start with random track
    let currentIndex = Math.floor(rng() * queue.length);
    shuffled.push(queue[currentIndex]);
    available.delete(currentIndex);

    // Pick remaining tracks, avoiding similar ones nearby
    while (available.size > 0) {
      const candidates = Array.from(available);
      let nextIndex: number | null = null;

      // Try to find a track that's different from recent tracks
      for (const idx of candidates) {
        const track = queue[idx];
        let isDifferent = true;

        // Check against last N tracks
        for (let i = 0; i < Math.min(minDistance, shuffled.length); i++) {
          const recentTrack = shuffled[shuffled.length - 1 - i];
          if (this.tracksAreSimilar(track, recentTrack)) {
            isDifferent = false;
            break;
          }
        }

        if (isDifferent) {
          nextIndex = idx;
          break;
        }
      }

      // If no different track found, just pick random
      if (nextIndex === null) {
        nextIndex = candidates[Math.floor(rng() * candidates.length)];
      }

      shuffled.push(queue[nextIndex]);
      available.delete(nextIndex);
    }

    return shuffled;
  }

  /**
   * Check if two tracks are similar (same artist or album)
   */
  private static tracksAreSimilar(track1: Track, track2: Track): boolean {
    return (
      track1.artist === track2.artist ||
      (track1.album && track1.album === track2.album)
    );
  }

  /**
   * Select random index based on weights
   */
  private static weightedRandomIndex(
    weights: number[],
    rng: () => number
  ): number {
    const totalWeight = weights.reduce((sum, w) => sum + w, 0);
    let random = rng() * totalWeight;

    for (let i = 0; i < weights.length; i++) {
      random -= weights[i];
      if (random <= 0) {
        return i;
      }
    }

    return weights.length - 1;
  }

  /**
   * Seeded random number generator (LCG - Linear Congruential Generator)
   */
  private static seededRandom(seed: number): () => number {
    return () => {
      // LCG parameters (same as used in many systems)
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed / 0x7fffffff;
    };
  }

  /**
   * Unshuffle - restore original order from shuffled queue
   * (requires tracking original indices)
   */
  static unshuffle(
    shuffledQueue: Track[],
    originalQueue: Track[]
  ): Track[] {
    // Create map of track ID to original position
    const originalPositions = new Map<number, number>();
    originalQueue.forEach((track, index) => {
      originalPositions.set(track.id, index);
    });

    // Sort shuffled tracks by original position
    return [...shuffledQueue].sort((a, b) => {
      const posA = originalPositions.get(a.id) ?? 0;
      const posB = originalPositions.get(b.id) ?? 0;
      return posA - posB;
    });
  }

  /**
   * Get all available shuffle modes with descriptions
   */
  static getModes(): Array<{ mode: ShuffleMode; name: string; description: string }> {
    return [
      {
        mode: 'random',
        name: 'Random',
        description: 'Standard random shuffle',
      },
      {
        mode: 'weighted',
        name: 'Weighted',
        description: 'Biased shuffle - prefer longer/more important tracks',
      },
      {
        mode: 'album',
        name: 'By Album',
        description: 'Keep album tracks together, shuffle albums',
      },
      {
        mode: 'artist',
        name: 'By Artist',
        description: 'Keep artist tracks together, shuffle artists',
      },
      {
        mode: 'temporal',
        name: 'Temporal',
        description: 'Preserve distribution of old and new tracks',
      },
      {
        mode: 'no_repeat',
        name: 'No Repeat',
        description: 'Avoid similar tracks appearing close together',
      },
    ];
  }
}
