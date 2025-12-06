/**
 * useGroupedArtists Hook
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Groups artists by their first letter (A-Z) for alphabetical display.
 *
 * Usage:
 * ```typescript
 * const { groupedArtists, sortedLetters } = useGroupedArtists(artists);
 *
 * // Render grouped sections
 * {sortedLetters.map(letter => (
 *   <section key={letter}>
 *     <h2>{letter}</h2>
 *     {groupedArtists[letter].map(artist => ...)}
 *   </section>
 * ))}
 * ```
 */

import { useMemo } from 'react';
import type { Artist } from '@/types/domain';

export interface UseGroupedArtistsResult {
  /** Artists grouped by first letter (uppercase) */
  groupedArtists: Record<string, Artist[]>;
  /** Sorted array of first letters that have artists */
  sortedLetters: string[];
}

/**
 * Groups artists by their first letter
 * @param artists Array of artists to group
 * @returns Object with groupedArtists and sortedLetters
 */
export function useGroupedArtists(artists: Artist[]): UseGroupedArtistsResult {
  const groupedArtists = useMemo(() => {
    return artists.reduce((acc, artist) => {
      const initial = artist.name.charAt(0).toUpperCase();
      if (!acc[initial]) {
        acc[initial] = [];
      }
      acc[initial].push(artist);
      return acc;
    }, {} as Record<string, Artist[]>);
  }, [artists]);

  const sortedLetters = useMemo(() => {
    return Object.keys(groupedArtists).sort();
  }, [groupedArtists]);

  return { groupedArtists, sortedLetters };
}
