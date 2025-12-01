/**
 * TrackInfo Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Displays current track information (title, artist, album, artwork).
 * Shows placeholder when no track is playing.
 *
 * Usage:
 * ```typescript
 * <TrackInfo />
 * ```
 *
 * Props: None required (uses hooks internally)
 *
 * @module components/player/TrackInfo
 */

import React from 'react';
import { tokens } from '@/design-system/tokens';
import { useCurrentTrack } from '@/hooks/player/usePlaybackState';

/**
 * TrackInfo component
 *
 * Displays album artwork, track title, artist, and album name.
 * Shows loading/empty state when no track is playing.
 */
export const TrackInfo: React.FC = () => {
  const track = useCurrentTrack();

  return (
    <div style={styles.container}>
      {track ? (
        <>
          {/* Album artwork */}
          <div style={styles.artworkContainer}>
            {track.artwork_url ? (
              <img
                src={track.artwork_url}
                alt={track.title}
                style={styles.artwork}
                loading="lazy"
              />
            ) : (
              <div style={styles.artworkPlaceholder}>
                <span style={styles.artworkPlaceholderIcon}>♪</span>
              </div>
            )}
          </div>

          {/* Track details */}
          <div style={styles.detailsContainer}>
            {/* Title */}
            <h2 style={styles.title} title={track.title}>
              {track.title}
            </h2>

            {/* Artist */}
            <p style={styles.artist} title={track.artist}>
              {track.artist}
            </p>

            {/* Album */}
            {track.album && (
              <p style={styles.album} title={track.album}>
                {track.album}
              </p>
            )}

            {/* Optional: Metadata badges */}
            {track.year && (
              <div style={styles.metadata}>
                <span style={styles.metadataItem}>{track.year}</span>
                {track.genre && (
                  <>
                    <span style={styles.metadataSeparator}>•</span>
                    <span style={styles.metadataItem}>{track.genre}</span>
                  </>
                )}
              </div>
            )}
          </div>
        </>
      ) : (
        /* No track playing - show empty state */
        <div style={styles.emptyState}>
          <div style={styles.emptyArtwork}>
            <span style={styles.emptyIcon}>♪</span>
          </div>
          <div style={styles.emptyText}>
            <p style={styles.emptyTitle}>No track playing</p>
            <p style={styles.emptySubtitle}>Select a track to begin</p>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
    minHeight: '300px',
    justifyContent: 'center',
  },

  artworkContainer: {
    position: 'relative' as const,
    width: '180px',
    height: '180px',
    borderRadius: tokens.borderRadius.lg,
    overflow: 'hidden',
    boxShadow: tokens.shadows.lg,
  },

  artwork: {
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
    backgroundColor: tokens.colors.bg.tertiary,
  },

  artworkPlaceholder: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    height: '100%',
    backgroundColor: tokens.colors.bg.tertiary,
    color: tokens.colors.text.secondary,
  },

  artworkPlaceholderIcon: {
    fontSize: '60px',
    opacity: 0.5,
  },

  detailsContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: tokens.spacing.sm,
    width: '100%',
    textAlign: 'center' as const,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    width: '100%',
  },

  artist: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    color: tokens.colors.text.secondary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    width: '100%',
  },

  album: {
    margin: 0,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    fontStyle: 'italic' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    width: '100%',
  },

  metadata: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: tokens.spacing.xs,
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },

  metadataItem: {
    padding: `2px ${tokens.spacing.xs}`,
  },

  metadataSeparator: {
    opacity: 0.5,
  },

  /* Empty state styles */
  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: tokens.spacing.lg,
    justifyContent: 'center',
    textAlign: 'center' as const,
  },

  emptyArtwork: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '120px',
    height: '120px',
    borderRadius: tokens.borderRadius.lg,
    backgroundColor: tokens.colors.bg.tertiary,
    color: tokens.colors.text.tertiary,
  },

  emptyIcon: {
    fontSize: '48px',
    opacity: 0.3,
  },

  emptyText: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  emptyTitle: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.secondary,
  },

  emptySubtitle: {
    margin: 0,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
  },
};

export default TrackInfo;
