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

import React, { useCallback, useState } from 'react';
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
 * Shows hover effects with overlay play button and selection state.
 * Premium design with glass morphism and soft hover scale.
 */
export const AlbumCard: React.FC<AlbumCardProps> = ({
  album,
  onClick,
  isSelected = false,
}) => {
  const [isHovering, setIsHovering] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  const handleClick = useCallback(() => {
    onClick?.(album);
  }, [album, onClick]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick?.(album);
      }
    },
    [album, onClick]
  );

  return (
    <div
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      style={{
        ...styles.card,
        ...(isSelected && styles.cardSelected),
        ...(isFocused && styles.cardFocused),
      }}
      role="button"
      tabIndex={0}
      aria-selected={isSelected}
      aria-label={`${album.title} by ${album.artist}`}
    >
      {/* Album artwork */}
      <div style={styles.artworkContainer}>
        {album.artwork_url ? (
          <img
            src={album.artwork_url}
            alt={`${album.title} album cover`}
            style={styles.artwork}
            loading="lazy"
          />
        ) : (
          <div style={styles.artworkPlaceholder} aria-label="Album cover not available">
            <span style={styles.placeholderIcon} aria-hidden="true">💿</span>
          </div>
        )}

        {/* Overlay on hover/focus */}
        <div
          style={{
            ...styles.overlay,
            opacity: isHovering || isFocused ? 1 : 0,
            pointerEvents: isHovering || isFocused ? 'auto' : 'none',
          }}
        >
          <button style={styles.playButton} aria-label={`Play ${album.title}`}>
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
 *
 * Premium album card with glass-morphism hover effects
 * - 200×200px cover (design spec: tokens.components.albumCard.size)
 * - Soft hover scale 1.04 (tokens.components.albumCard.hoverScale)
 * - Play button overlay on hover with Electric Aqua glow
 * - Elevation shadows from design system
 */
const styles = {
  card: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    cursor: 'pointer',
    borderRadius: tokens.borderRadius.lg,
    overflow: 'hidden',
    transition: tokens.transitions.all,
    backgroundColor: 'transparent',
    outline: 'none',

    ':hover': {
      transform: `scale(${tokens.components.albumCard.hoverScale})`,
      // Shadow escalation on hover
    },

    ':focus-visible': {
      outline: `2px solid ${tokens.colors.accent.primary}`,
      outlineOffset: '2px',
    },
  },

  cardSelected: {
    outline: `2px solid ${tokens.colors.accent.primary}`,
    outlineOffset: '2px',
  },

  cardFocused: {
    outline: `3px solid ${tokens.colors.accent.primary}`,
    outlineOffset: '4px',
    boxShadow: tokens.shadows.glowMd,
  },

  artworkContainer: {
    position: 'relative' as const,
    paddingBottom: '100%', // Square aspect ratio (200×200)
    width: '100%',
    overflow: 'hidden',
    backgroundColor: tokens.colors.bg.level3,
    borderRadius: tokens.borderRadius.lg,
    boxShadow: tokens.components.albumCard.hoverShadow,
  },

  artwork: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
    transition: tokens.transitions.all,
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
    backgroundColor: tokens.colors.bg.level3,
    color: tokens.colors.text.tertiary,
    borderRadius: tokens.borderRadius.lg,
  },

  placeholderIcon: {
    fontSize: '64px',
    opacity: 0.2,
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
    backgroundColor: 'rgba(0, 0, 0, 0.40)',
    backdropFilter: 'blur(4px)',
    opacity: 0,
    transition: tokens.transitions.all,
    borderRadius: tokens.borderRadius.lg,
  },

  playButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '56px',
    height: '56px',
    borderRadius: tokens.borderRadius.full,
    background: tokens.gradients.aurora,
    border: 'none',
    cursor: 'pointer',
    color: tokens.colors.text.primary,
    fontSize: '24px',
    transition: tokens.transitions.all,
    boxShadow: tokens.shadows.md,
    outline: 'none',

    ':hover': {
      transform: 'scale(1.08)',
      boxShadow: tokens.shadows.glowMd,
    },

    ':active': {
      transform: 'scale(1.02)',
    },
  },

  info: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
    padding: `${tokens.spacing.sm} 0`,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    color: tokens.colors.text.primary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    transition: tokens.transitions.color,
  },

  artist: {
    margin: 0,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    transition: tokens.transitions.color,
  },
};

export default AlbumCard;
