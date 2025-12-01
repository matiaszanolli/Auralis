/**
 * AlbumCard Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Card component for displaying an album with artwork and metadata.
 * Used in album grid layouts.
 *
 * Usage:
 * ```typescript
 * <AlbumCard album={album} onClick={() => handleAlbumSelect(album)} />
 * ```
 *
 * Props:
 * - album: Album object with id, title, artist, artwork_url
 * - onClick: Callback when card is clicked
 * - isSelected: Whether album is currently selected
 *
 * @module components/library/AlbumCard
 */

import React, { useCallback } from 'react';
import { tokens } from '@/design-system/tokens';
import type { Album } from '@/types/domain';

interface AlbumCardProps {
  /** Album object */
  album: Album;

  /** Callback when card is clicked */
  onClick?: (album: Album) => void;

  /** Whether album is currently selected */
  isSelected?: boolean;
}

/**
 * AlbumCard component
 *
 * Displays album artwork, title, and artist in a card format.
 * Shows hover effects and selection state.
 * Responsive sizing for grid layouts.
 */
export const AlbumCard: React.FC<AlbumCardProps> = ({
  album,
  onClick,
  isSelected = false,
}) => {
  const handleClick = useCallback(() => {
    onClick?.(album);
  }, [album, onClick]);

  return (
    <div
      onClick={handleClick}
      style={{
        ...styles.card,
        ...(isSelected && styles.cardSelected),
      }}
      role="button"
      tabIndex={0}
      aria-selected={isSelected}
    >
      {/* Album artwork */}
      <div style={styles.artworkContainer}>
        {album.artwork_url ? (
          <img
            src={album.artwork_url}
            alt={album.title}
            style={styles.artwork}
            loading="lazy"
          />
        ) : (
          <div style={styles.artworkPlaceholder}>
            <span style={styles.placeholderIcon}>💿</span>
          </div>
        )}

        {/* Overlay on hover */}
        <div style={styles.overlay}>
          <button style={styles.playButton} aria-label="Play album">
            ▶
          </button>
        </div>
      </div>

      {/* Album info */}
      <div style={styles.info}>
        <h3 style={styles.title} title={album.title}>
          {album.title}
        </h3>
        <p style={styles.artist} title={album.artist}>
          {album.artist}
        </p>
      </div>
    </div>
  );
};

/**
 * Component styles using design tokens
 */
const styles = {
  card: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
    cursor: 'pointer',
    borderRadius: tokens.borderRadius.md,
    overflow: 'hidden',
    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
    backgroundColor: tokens.colors.bg.secondary,

    '&:hover': {
      transform: 'translateY(-4px)',
      boxShadow: tokens.shadows.lg,
    },
  },

  cardSelected: {
    boxShadow: `0 0 0 2px ${tokens.colors.accent.primary}`,
    backgroundColor: tokens.colors.accent.subtle,
  },

  artworkContainer: {
    position: 'relative' as const,
    paddingBottom: '100%', // Square aspect ratio
    width: '100%',
    overflow: 'hidden',
    backgroundColor: tokens.colors.bg.tertiary,
  },

  artwork: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
  },

  artworkPlaceholder: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: tokens.colors.bg.tertiary,
    color: tokens.colors.text.tertiary,
  },

  placeholderIcon: {
    fontSize: '48px',
    opacity: 0.3,
  },

  overlay: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    opacity: 0,
    transition: 'opacity 0.2s ease',
  },

  playButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '48px',
    height: '48px',
    borderRadius: tokens.borderRadius.full,
    backgroundColor: tokens.colors.accent.primary,
    border: 'none',
    cursor: 'pointer',
    color: tokens.colors.text.onAccent,
    fontSize: '20px',
    transition: 'transform 0.2s ease',

    '&:hover': {
      transform: 'scale(1.1)',
    },
  },

  info: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
    padding: `0 ${tokens.spacing.sm}`,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  artist: {
    margin: 0,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
};

export default AlbumCard;
