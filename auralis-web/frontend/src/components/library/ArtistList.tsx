/**
 * ArtistList Component
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * List of artists with pagination.
 * Click artist to view their albums/tracks.
 *
 * @module components/library/ArtistList
 */

import React, { useCallback, useState } from 'react';
import { tokens } from '@/design-system';
import { useArtistsQuery } from '@/hooks/library/useLibraryQuery';
import type { Artist } from '@/types/domain';

interface ArtistListProps {
  onArtistSelect?: (artist: Artist) => void;
  limit?: number;
}

export const ArtistList: React.FC<ArtistListProps> = ({ onArtistSelect, limit = 50 }) => {
  const { data: artists, isLoading, error, hasMore, fetchMore } = useArtistsQuery({ limit });
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const handleSelect = useCallback(
    (artist: Artist) => {
      setSelectedId(artist.id);
      onArtistSelect?.(artist);
    },
    [onArtistSelect]
  );

  if (error) {
    return <div style={styles.error}>Failed to load artists</div>;
  }

  return (
    <div style={styles.container}>
      <div style={styles.list}>
        {artists.map((artist) => (
          <div
            key={artist.id}
            onClick={() => handleSelect(artist)}
            style={{
              ...styles.item,
              ...(selectedId === artist.id && styles.itemSelected),
            }}
          >
            <div style={styles.itemName}>{artist.name}</div>
          </div>
        ))}
      </div>

      {hasMore && (
        <button onClick={fetchMore} disabled={isLoading} style={styles.loadMore}>
          Load More
        </button>
      )}
    </div>
  );
};

const styles = {
  container: { display: 'flex', flexDirection: 'column' as const, gap: tokens.spacing.md },
  list: { display: 'flex', flexDirection: 'column' as const, gap: tokens.spacing.sm },
  item: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
  },
  itemSelected: { backgroundColor: tokens.colors.bg.level3 },
  itemName: { color: tokens.colors.text.primary, fontWeight: tokens.typography.fontWeight.bold },
  error: { color: tokens.colors.semantic.error },
  loadMore: {
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.accent.primary,
    border: 'none',
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
  },
};

export default ArtistList;
