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

import React, { useCallback } from 'react';
import { tokens } from '@/design-system';
import { useAlbumsQuery } from '@/hooks/library/useLibraryQuery';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
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

  const handleAlbumSelect = useCallback(
    (album: Album) => {
      onAlbumSelect?.(album);
    },
    [onAlbumSelect]
  );

  if (error) {
    return (
      <section style={styles.errorContainer} role="alert" aria-live="assertive">
        <p>Failed to load albums</p>
        <p style={styles.errorSubtext}>{error.message}</p>
      </section>
    );
  }

  if (albums.length === 0 && !isLoading) {
    return (
      <section style={styles.emptyContainer} role="status" aria-live="polite">
        <p>No albums found</p>
      </section>
    );
  }

  return (
    <section style={styles.container} aria-label="Albums library">
      <div style={styles.grid} role="list">
        {albums.map((album) => (
          <div key={album.id} role="listitem">
            <AlbumCard
              albumId={album.id}
              title={album.title}
              artist={album.artist}
              trackCount={album.trackCount}
              hasArtwork={!!album.artworkUrl}
              year={album.year}
              onClick={() => handleAlbumSelect(album)}
            />
          </div>
        ))}
      </div>

      {isLoading && (
        <div style={styles.loadingMessage} role="status" aria-live="polite" aria-atomic="true">
          Loading more albums...
        </div>
      )}

      {!hasMore && albums.length > 0 && (
        <div style={styles.endMessage} role="status" aria-live="polite">
          End of list
        </div>
      )}

      {hasMore && (
        <button
          onClick={fetchMore}
          disabled={isLoading}
          style={styles.loadMoreButton}
          aria-label={`Load more albums (${albums.length} loaded)`}
        >
          {isLoading ? 'Loading...' : 'Load More'}
        </button>
      )}
    </section>
  );
};

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.lg,
    width: '100%',
    padding: `0 ${tokens.spacing.lg}`,
  },

  grid: {
    display: 'grid',
    // Responsive columns: 2 (mobile) → 3 (tablet) → 4 (desktop) → 5-6 (ultra)
    // Album cards: 200×200px per spec (tokens.components.albumCard.size)
    gridTemplateColumns: 'repeat(auto-fill, minmax(216px, 1fr))',
    gap: tokens.spacing.lg,
    width: '100%',

    // Mobile: 2 columns
    '@media (max-width: 640px)': {
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: tokens.spacing.md,
      padding: `0 ${tokens.spacing.sm}`,
    },

    // Tablet: 3 columns
    '@media (min-width: 641px) and (max-width: 1023px)': {
      gridTemplateColumns: 'repeat(3, 1fr)',
      gap: tokens.spacing.md,
    },

    // Desktop: 4 columns
    '@media (min-width: 1024px) and (max-width: 1439px)': {
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: tokens.spacing.lg,
    },

    // Ultra-wide: 5+ columns
    '@media (min-width: 1440px)': {
      gridTemplateColumns: 'repeat(auto-fill, minmax(216px, 1fr))',
      gap: tokens.spacing.lg,
    },
  },

  errorContainer: {
    padding: tokens.spacing.lg,
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primary,
    borderRadius: tokens.borderRadius.lg,
    textAlign: 'center' as const,
  },

  errorSubtext: {
    fontSize: tokens.typography.fontSize.sm,
    opacity: 0.8,
    marginTop: tokens.spacing.sm,
  },

  emptyContainer: {
    padding: tokens.spacing.xl,
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
    borderRadius: tokens.borderRadius.lg,
    backgroundColor: tokens.colors.bg.level2,
  },

  loadingMessage: {
    textAlign: 'center' as const,
    color: tokens.colors.text.secondary,
    padding: tokens.spacing.md,
    fontSize: tokens.typography.fontSize.sm,
  },

  endMessage: {
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
    padding: tokens.spacing.md,
    fontSize: tokens.typography.fontSize.sm,
  },

  loadMoreButton: {
    alignSelf: 'center' as const,
    padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
    background: tokens.gradients.aurora,
    color: tokens.colors.text.primary,
    border: 'none',
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: tokens.transitions.all,
    boxShadow: tokens.shadows.md,
    outline: 'none',

    ':hover': {
      boxShadow: tokens.shadows.glowMd,
      transform: 'translateY(-2px)',
    },

    ':active': {
      transform: 'translateY(0)',
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },
};

export default AlbumGrid;
