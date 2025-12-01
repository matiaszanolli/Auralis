/**
 * AlbumGrid Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Grid layout for displaying albums using AlbumCard components.
 * Handles pagination and responsive columns.
 *
 * Usage:
 * ```typescript
 * <AlbumGrid />
 * ```
 *
 * @module components/library/AlbumGrid
 */

import React, { useCallback, useState } from 'react';
import { tokens } from '@/design-system/tokens';
import { useAlbumsQuery } from '@/hooks/library/useLibraryQuery';
import AlbumCard from './AlbumCard';
import type { Album } from '@/types/domain';

interface AlbumGridProps {
  /** Callback when album is selected */
  onAlbumSelect?: (album: Album) => void;

  /** Number of albums per page */
  limit?: number;
}

/**
 * AlbumGrid component
 *
 * Responsive grid of album cards with infinite scroll.
 * Adapts column count based on viewport width.
 */
export const AlbumGrid: React.FC<AlbumGridProps> = ({
  onAlbumSelect,
  limit = 20,
}) => {
  const { data: albums, isLoading, error, hasMore, fetchMore } = useAlbumsQuery({ limit });
  const [selectedAlbumId, setSelectedAlbumId] = useState<number | null>(null);

  const handleAlbumSelect = useCallback(
    (album: Album) => {
      setSelectedAlbumId(album.id);
      onAlbumSelect?.(album);
    },
    [onAlbumSelect]
  );

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <p>Failed to load albums</p>
        <p style={styles.errorSubtext}>{error.message}</p>
      </div>
    );
  }

  if (albums.length === 0 && !isLoading) {
    return (
      <div style={styles.emptyContainer}>
        <p>No albums found</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.grid}>
        {albums.map((album) => (
          <AlbumCard
            key={album.id}
            album={album}
            onClick={handleAlbumSelect}
            isSelected={selectedAlbumId === album.id}
          />
        ))}
      </div>

      {isLoading && <div style={styles.loadingMessage}>Loading more albums...</div>}

      {!hasMore && albums.length > 0 && (
        <div style={styles.endMessage}>End of list</div>
      )}

      {hasMore && (
        <button onClick={fetchMore} disabled={isLoading} style={styles.loadMoreButton}>
          {isLoading ? 'Loading...' : 'Load More'}
        </button>
      )}
    </div>
  );
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    width: '100%',
  },

  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: tokens.spacing.md,
    width: '100%',
  },

  errorContainer: {
    padding: tokens.spacing.lg,
    backgroundColor: tokens.colors.error,
    color: tokens.colors.text.onError,
    borderRadius: tokens.borderRadius.md,
    textAlign: 'center' as const,
  },

  errorSubtext: {
    fontSize: tokens.typography.fontSize.sm,
    opacity: 0.8,
  },

  emptyContainer: {
    padding: tokens.spacing.lg,
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
  },

  loadingMessage: {
    textAlign: 'center' as const,
    color: tokens.colors.text.secondary,
    padding: tokens.spacing.md,
  },

  endMessage: {
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
    padding: tokens.spacing.md,
    fontSize: tokens.typography.fontSize.sm,
  },

  loadMoreButton: {
    alignSelf: 'center' as const,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.onAccent,
    border: 'none',
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
  },
};

export default AlbumGrid;
