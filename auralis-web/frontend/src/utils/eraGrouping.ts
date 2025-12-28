/**
 * Era Grouping Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Groups albums by era (year ranges) for visual organization.
 * Creates natural groupings like "1978 - 1982" based on album years.
 *
 * Philosophy: Albums from the same era share sonic and cultural context.
 * Grouping by era helps users browse with temporal awareness.
 */

/**
 * Era group containing albums of the same era
 */
export interface EraGroup<T> {
  /** Era label (e.g., "1978 - 1982" or "Unknown Year") */
  label: string;
  /** Start year of era (undefined for unknown) */
  startYear?: number;
  /** End year of era (undefined for unknown) */
  endYear?: number;
  /** Albums in this era */
  albums: T[];
}

/**
 * Default era span in years
 * 5-year spans create natural groupings that align with cultural eras
 */
const DEFAULT_ERA_SPAN = 5;

/**
 * Compute era start year for a given year
 * Aligns to era span boundaries (e.g., 1978 -> 1975 for 5-year spans)
 */
const getEraStart = (year: number, eraSpan: number): number => {
  return Math.floor(year / eraSpan) * eraSpan;
};

/**
 * Group albums by era (year ranges)
 *
 * @param albums - Array of albums with id and optional year property
 * @param eraSpan - Number of years per era (default: 5)
 * @returns Array of era groups, sorted by era (most recent first)
 *
 * @example
 * ```ts
 * const groups = groupAlbumsByEra(albums);
 * // [
 * //   { label: "2020 - 2024", startYear: 2020, albums: [...] },
 * //   { label: "2015 - 2019", startYear: 2015, albums: [...] },
 * //   { label: "Unknown Year", albums: [...] }
 * // ]
 * ```
 */
export function groupAlbumsByEra<T extends { id: number; year?: number }>(
  albums: T[],
  eraSpan: number = DEFAULT_ERA_SPAN
): EraGroup<T>[] {
  // Separate albums with and without years
  const albumsWithYear: T[] = [];
  const albumsWithoutYear: T[] = [];

  for (const album of albums) {
    if (album.year && album.year > 1900 && album.year <= new Date().getFullYear() + 1) {
      albumsWithYear.push(album);
    } else {
      albumsWithoutYear.push(album);
    }
  }

  // Group albums by era
  const eraMap = new Map<number, T[]>();

  for (const album of albumsWithYear) {
    const eraStart = getEraStart(album.year!, eraSpan);
    const existing = eraMap.get(eraStart) || [];
    existing.push(album);
    eraMap.set(eraStart, existing);
  }

  // Convert to array of era groups, sorted by era (most recent first)
  const eraGroups: EraGroup<T>[] = Array.from(eraMap.entries())
    .sort(([a], [b]) => b - a) // Most recent first
    .map(([startYear, eraAlbums]) => {
      const endYear = startYear + eraSpan - 1;
      return {
        label: `${startYear} - ${endYear}`,
        startYear,
        endYear,
        // Sort albums within era by year (most recent first)
        albums: eraAlbums.sort((a, b) => (b.year ?? 0) - (a.year ?? 0)),
      };
    });

  // Add unknown year group at the end if there are any
  if (albumsWithoutYear.length > 0) {
    eraGroups.push({
      label: 'Unknown Year',
      albums: albumsWithoutYear,
    });
  }

  return eraGroups;
}

/**
 * Get era label for a single year
 *
 * @param year - Album year
 * @param eraSpan - Number of years per era (default: 5)
 * @returns Era label string
 */
export function getEraLabel(year: number | undefined, eraSpan: number = DEFAULT_ERA_SPAN): string {
  if (!year || year < 1900) {
    return 'Unknown Year';
  }
  const startYear = getEraStart(year, eraSpan);
  const endYear = startYear + eraSpan - 1;
  return `${startYear} - ${endYear}`;
}
