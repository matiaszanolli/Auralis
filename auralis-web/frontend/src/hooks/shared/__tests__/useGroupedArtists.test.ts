/**
 * useGroupedArtists Hook Tests
 *
 * Tests for alphabetical artist grouping by first letter.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useGroupedArtists } from '../useGroupedArtists';
import type { Artist } from '@/types/domain';

function makeArtist(name: string, id = 1): Artist {
  return { id, name, trackCount: 0, albumCount: 0 };
}

describe('useGroupedArtists', () => {
  it('returns empty groups and letters for an empty array', () => {
    const { result } = renderHook(() => useGroupedArtists([]));

    expect(result.current.groupedArtists).toEqual({});
    expect(result.current.sortedLetters).toEqual([]);
  });

  it('groups artists by different initials and sorts letters', () => {
    const artists = [
      makeArtist('Boards of Canada', 1),
      makeArtist('Aphex Twin', 2),
      makeArtist('Caribou', 3),
    ];

    const { result } = renderHook(() => useGroupedArtists(artists));

    expect(result.current.sortedLetters).toEqual(['A', 'B', 'C']);
    expect(result.current.groupedArtists['A']).toHaveLength(1);
    expect(result.current.groupedArtists['A'][0].name).toBe('Aphex Twin');
    expect(result.current.groupedArtists['B'][0].name).toBe('Boards of Canada');
    expect(result.current.groupedArtists['C'][0].name).toBe('Caribou');
  });

  it('groups artists with the same initial under one letter', () => {
    const artists = [
      makeArtist('Radiohead', 1),
      makeArtist('Run the Jewels', 2),
      makeArtist('Ratatat', 3),
    ];

    const { result } = renderHook(() => useGroupedArtists(artists));

    expect(result.current.sortedLetters).toEqual(['R']);
    expect(result.current.groupedArtists['R']).toHaveLength(3);
    expect(result.current.groupedArtists['R'].map(a => a.name)).toEqual([
      'Radiohead',
      'Run the Jewels',
      'Ratatat',
    ]);
  });

  it('groups mixed-case initials under the uppercase letter', () => {
    const artists = [
      makeArtist('daft punk', 1),
      makeArtist('Depeche Mode', 2),
    ];

    const { result } = renderHook(() => useGroupedArtists(artists));

    expect(result.current.sortedLetters).toEqual(['D']);
    expect(result.current.groupedArtists['D']).toHaveLength(2);
    expect(result.current.groupedArtists['D'].map(a => a.name)).toEqual([
      'daft punk',
      'Depeche Mode',
    ]);
  });
});
