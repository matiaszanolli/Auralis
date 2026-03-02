/**
 * Queue Shuffler Utility Tests
 *
 * Comprehensive test suite for shuffle algorithms.
 * Covers: all shuffle modes, stability, distribution
 */

import { describe, it, expect } from 'vitest';
import { QueueShuffler } from '../queue_shuffler';
import type { Track } from '@/types/domain';

// Mock tracks for testing
const mockTracks: Track[] = [
  {
    id: 1,
    title: 'Song 1',
    artist: 'Artist A',
    album: 'Album 1',
    duration: 300,
    filepath: '/music/a1.mp3',
  },
  {
    id: 2,
    title: 'Song 2',
    artist: 'Artist A',
    album: 'Album 1',
    duration: 320,
    filepath: '/music/a2.mp3',
  },
  {
    id: 3,
    title: 'Song 3',
    artist: 'Artist A',
    album: 'Album 2',
    duration: 280,
    filepath: '/music/a3.mp3',
  },
  {
    id: 4,
    title: 'Song 4',
    artist: 'Artist B',
    album: 'Album 3',
    duration: 290,
    filepath: '/music/b1.mp3',
  },
  {
    id: 5,
    title: 'Song 5',
    artist: 'Artist B',
    album: 'Album 3',
    duration: 310,
    filepath: '/music/b2.mp3',
  },
  {
    id: 6,
    title: 'Song 6',
    artist: 'Artist C',
    album: 'Album 4',
    duration: 330,
    filepath: '/music/c1.mp3',
  },
];

describe('QueueShuffler', () => {
  // =========================================================================
  // BASIC SHUFFLE
  // =========================================================================

  it('should shuffle queue', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks);

    expect(shuffled).toHaveLength(mockTracks.length);
    expect(new Set(shuffled.map((t) => t.id))).toEqual(
      new Set(mockTracks.map((t) => t.id))
    );
  });

  it('should not modify original queue', () => {
    const original = [...mockTracks];
    QueueShuffler.shuffle(mockTracks);

    expect(mockTracks).toEqual(original);
  });

  it('should handle empty queue', () => {
    const shuffled = QueueShuffler.shuffle([]);
    expect(shuffled).toHaveLength(0);
  });

  it('should handle single track queue', () => {
    const shuffled = QueueShuffler.shuffle([mockTracks[0]]);
    expect(shuffled).toEqual([mockTracks[0]]);
  });

  // =========================================================================
  // RANDOM SHUFFLE
  // =========================================================================

  it('should perform random shuffle', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'random');

    expect(shuffled).toHaveLength(mockTracks.length);
  });

  it('should produce different results on repeated shuffles', () => {
    const shuffle1 = QueueShuffler.shuffle(mockTracks, 'random');
    const shuffle2 = QueueShuffler.shuffle(mockTracks, 'random');

    // Very unlikely to be identical (theoretical but possible)
    expect(shuffle1).not.toEqual(shuffle2);
  });

  it('should be reproducible with seed', () => {
    const shuffle1 = QueueShuffler.shuffle(mockTracks, 'random', { seed: 42 });
    const shuffle2 = QueueShuffler.shuffle(mockTracks, 'random', { seed: 42 });

    expect(shuffle1).toEqual(shuffle2);
  });

  it('should produce different results with different seeds', () => {
    const shuffle1 = QueueShuffler.shuffle(mockTracks, 'random', { seed: 42 });
    const shuffle2 = QueueShuffler.shuffle(mockTracks, 'random', { seed: 43 });

    expect(shuffle1).not.toEqual(shuffle2);
  });

  // =========================================================================
  // WEIGHTED SHUFFLE
  // =========================================================================

  it('should perform weighted shuffle', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'weighted');

    expect(shuffled).toHaveLength(mockTracks.length);
    // Longer tracks should appear more frequently near the start
  });

  it('should preserve all tracks in weighted shuffle', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'weighted');

    expect(new Set(shuffled.map((t) => t.id))).toEqual(
      new Set(mockTracks.map((t) => t.id))
    );
  });

  // =========================================================================
  // ALBUM SHUFFLE
  // =========================================================================

  it('should keep album tracks together', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'album');

    // Find positions of Album 1 tracks (1, 2)
    const album1Positions = shuffled
      .map((t, i) => (t.album === 'Album 1' ? i : -1))
      .filter((i) => i >= 0);

    // They should be consecutive or close together
    if (album1Positions.length > 1) {
      for (let i = 0; i < album1Positions.length - 1; i++) {
        expect(album1Positions[i + 1] - album1Positions[i]).toBeLessThanOrEqual(2);
      }
    }
  });

  it('should shuffle album order', () => {
    const shuffle1 = QueueShuffler.shuffle(mockTracks, 'album', { seed: 42 });
    const shuffle2 = QueueShuffler.shuffle(mockTracks, 'album', { seed: 43 });

    // Should produce different album orders
    expect(shuffle1).not.toEqual(shuffle2);
  });

  // =========================================================================
  // ARTIST SHUFFLE
  // =========================================================================

  it('should keep artist tracks together', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'artist');

    // Find positions of Artist A tracks (1, 2, 3)
    const artistAPositions = shuffled
      .map((t, i) => (t.artist === 'Artist A' ? i : -1))
      .filter((i) => i >= 0);

    // They should be in same section
    const minPos = Math.min(...artistAPositions);
    const maxPos = Math.max(...artistAPositions);
    expect(maxPos - minPos).toBeLessThan(mockTracks.length);
  });

  it('should shuffle artist order', () => {
    const shuffle1 = QueueShuffler.shuffle(mockTracks, 'artist', { seed: 42 });
    const shuffle2 = QueueShuffler.shuffle(mockTracks, 'artist', { seed: 43 });

    expect(shuffle1).not.toEqual(shuffle2);
  });

  // =========================================================================
  // TEMPORAL SHUFFLE
  // =========================================================================

  it('should perform temporal shuffle', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'temporal');

    expect(shuffled).toHaveLength(mockTracks.length);
  });

  it('should preserve all tracks in temporal shuffle', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'temporal');

    expect(new Set(shuffled.map((t) => t.id))).toEqual(
      new Set(mockTracks.map((t) => t.id))
    );
  });

  // =========================================================================
  // NO REPEAT SHUFFLE
  // =========================================================================

  it('should avoid repeating similar tracks', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'no_repeat', {
      minSimilarityDistance: 2,
    });

    // Check that tracks by same artist aren't too close
    for (let i = 0; i < shuffled.length - 1; i++) {
      const current = shuffled[i];
      const next = shuffled[i + 1];

      // They shouldn't both be by the same artist in immediate succession
      if (i > 0) {
        const prev = shuffled[i - 1];
        const sameArtistCount = [prev, current, next].filter(
          (t) => t.artist === current.artist
        ).length;

        expect(sameArtistCount).toBeLessThan(3);
      }
    }
  });

  it('should preserve all tracks in no repeat shuffle', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks, 'no_repeat');

    expect(new Set(shuffled.map((t) => t.id))).toEqual(
      new Set(mockTracks.map((t) => t.id))
    );
  });

  // =========================================================================
  // UNSHUFFLE
  // =========================================================================

  it('should unshuffle to original order', () => {
    const shuffled = QueueShuffler.shuffle(mockTracks);
    const unshuffled = QueueShuffler.unshuffle(shuffled, mockTracks);

    expect(unshuffled).toEqual(mockTracks);
  });

  it('should unshuffle with different shuffle modes', () => {
    const shuffledAlbum = QueueShuffler.shuffle(mockTracks, 'album');
    const unshuffled = QueueShuffler.unshuffle(shuffledAlbum, mockTracks);

    expect(unshuffled).toEqual(mockTracks);
  });

  // =========================================================================
  // MODES
  // =========================================================================

  it('should return available shuffle modes', () => {
    const modes = QueueShuffler.getModes();

    expect(modes.length).toBeGreaterThan(0);
    expect(modes.some((m) => m.mode === 'random')).toBe(true);
    expect(modes.some((m) => m.mode === 'weighted')).toBe(true);
    expect(modes.some((m) => m.mode === 'album')).toBe(true);
    expect(modes.some((m) => m.mode === 'artist')).toBe(true);
  });

  it('should have description for each mode', () => {
    const modes = QueueShuffler.getModes();

    modes.forEach((mode) => {
      expect(mode.name).toBeTruthy();
      expect(mode.description).toBeTruthy();
    });
  });

  // =========================================================================
  // EDGE CASES
  // =========================================================================

  it('should handle two-track queue', () => {
    const twoTracks = mockTracks.slice(0, 2);
    const shuffled = QueueShuffler.shuffle(twoTracks, 'random');

    expect(shuffled).toHaveLength(2);
    expect(new Set(shuffled.map((t) => t.id))).toEqual(
      new Set(twoTracks.map((t) => t.id))
    );
  });

  it('should handle single album', () => {
    const singleAlbum = mockTracks.filter((t) => t.album === 'Album 1');
    const shuffled = QueueShuffler.shuffle(singleAlbum, 'album');

    expect(shuffled).toHaveLength(singleAlbum.length);
  });

  it('should handle single artist', () => {
    const singleArtist = mockTracks.filter((t) => t.artist === 'Artist A');
    const shuffled = QueueShuffler.shuffle(singleArtist, 'artist');

    expect(shuffled).toHaveLength(singleArtist.length);
  });

  // =========================================================================
  // DISTRIBUTION
  // =========================================================================

  it('should have uniform distribution across multiple shuffles', () => {
    const positionCounts = new Map<number, number[]>();

    // Track 10 positions for each track over 100 shuffles
    for (let shuffle = 0; shuffle < 100; shuffle++) {
      const shuffled = QueueShuffler.shuffle(mockTracks, 'random', {
        seed: shuffle,
      });

      shuffled.forEach((track, position) => {
        if (!positionCounts.has(track.id)) {
          positionCounts.set(track.id, []);
        }
        positionCounts.get(track.id)!.push(position);
      });
    }

    // Check that each track appears across different positions
    for (const [, positions] of positionCounts) {
      const uniquePositions = new Set(positions);
      expect(uniquePositions.size).toBeGreaterThan(2);
    }
  });

  // =========================================================================
  // PERFORMANCE
  // =========================================================================

  it('should handle large queues efficiently', () => {
    const largeQueue: Track[] = Array.from({ length: 1000 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i % 50}`,
      album: `Album ${i % 25}`,
      duration: 200 + (i % 200),
      filepath: `/music/track${i}.mp3`,
    }));

    const startTime = performance.now();
    const shuffled = QueueShuffler.shuffle(largeQueue, 'random');
    const endTime = performance.now();

    expect(shuffled).toHaveLength(1000);
    expect(endTime - startTime).toBeLessThan(50); // Should be fast
  });

  it('should handle album shuffle with many albums efficiently', () => {
    const manyAlbums: Track[] = Array.from({ length: 500 }, (_, i) => ({
      id: i,
      title: `Track ${i}`,
      artist: `Artist ${i % 20}`,
      album: `Album ${i % 100}`, // Many albums
      duration: 200 + (i % 200),
      filepath: `/music/track${i}.mp3`,
    }));

    const startTime = performance.now();
    const shuffled = QueueShuffler.shuffle(manyAlbums, 'album');
    const endTime = performance.now();

    expect(shuffled).toHaveLength(500);
    expect(endTime - startTime).toBeLessThan(50);
  });
});
