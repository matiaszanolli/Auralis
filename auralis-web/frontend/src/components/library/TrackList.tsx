/**
 * TrackList Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Displays a scrollable list of tracks with infinite scroll pagination.
 * Handles selection, playback, and metadata display.
 *
 * Usage:
 * ```typescript
 * <TrackList />
 * ```
 *
 * Props: None required (uses hooks internally)
 *
 * Features:
 * - Infinite scroll pagination
 * - Track selection and multi-select
 * - Quick play on click
 * - Responsive design
 * - Loading and error states
 *
 * @module components/library/TrackList
 */

import React, { useCallback, useRef, useEffect, useState } from 'react';
import { tokens } from '@/design-system/tokens';
import { useTracksQuery } from '@/hooks/library/useLibraryQuery';
import { formatDuration } from '@/types/domain';
import type { Track } from '@/types/domain';

interface TrackListProps {
  /** Search query to filter tracks */
  search?: string;

  /** Number of tracks per page (default: 50) */
  limit?: number;

  /** Callback when track is selected/played */
  onTrackSelect?: (track: Track) => void;
}

/**
 * TrackList component
 *
 * Displays tracks in a scrollable list with infinite scroll.
 * Each track shows title, artist, album, and duration.
 * Clicking a track triggers playback via callback.
 */
export const TrackList: React.FC<TrackListProps> = ({
  search,
  limit = 50,
  onTrackSelect,
}) => {
  const { data: tracks, isLoading, error, hasMore, fetchMore } = useTracksQuery({
    search,
    limit,
  });

  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  /**
   * Set up Intersection Observer for infinite scroll
   */
  useEffect(() => {
    if (!sentinelRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMore && !isLoading) {
          fetchMore().catch((err) => console.error('Failed to fetch more tracks:', err));
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(sentinelRef.current);

    return () => observer.disconnect();
  }, [hasMore, isLoading, fetchMore]);

  /**
   * Handle track click
   */
  const handleTrackClick = useCallback(
    (track: Track, index: number) => {
      setSelectedIndex(index);
      onTrackSelect?.(track);
    },
    [onTrackSelect]
  );

  /**
   * Scroll into view when selected
   */
  const handleTrackSelect = useCallback((element: HTMLDivElement | null) => {
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, []);

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <p style={styles.errorText}>Failed to load tracks</p>
        <p style={styles.errorSubtext}>{error.message}</p>
      </div>
    );
  }

  if (tracks.length === 0 && !isLoading) {
    return (
      <div style={styles.emptyContainer}>
        <p style={styles.emptyText}>No tracks found</p>
        {search && <p style={styles.emptySubtext}>Try a different search</p>}
      </div>
    );
  }

  return (
    <div style={styles.container} ref={containerRef}>
      {/* Track list */}
      <div style={styles.trackList}>
        {tracks.map((track, index) => (
          <div
            key={`${track.id}-${index}`}
            ref={selectedIndex === index ? handleTrackSelect : null}
            onClick={() => handleTrackClick(track, index)}
            style={{
              ...styles.trackItem,
              ...(selectedIndex === index && styles.trackItemSelected),
            }}
            role="button"
            tabIndex={0}
            aria-selected={selectedIndex === index}
          >
            {/* Track number */}
            <span style={styles.trackNumber}>{index + 1}</span>

            {/* Track info */}
            <div style={styles.trackInfo}>
              <div style={styles.trackTitle} title={track.title}>
                {track.title}
              </div>
              <div style={styles.trackMeta}>
                <span style={styles.artist}>{track.artist}</span>
                {track.album && (
                  <>
                    <span style={styles.separator}>•</span>
                    <span style={styles.album}>{track.album}</span>
                  </>
                )}
              </div>
            </div>

            {/* Duration */}
            <span style={styles.duration}>{formatDuration(track.duration)}</span>
          </div>
        ))}

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} style={styles.sentinel} />
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <div style={styles.loadingContainer}>
          <span style={styles.loadingText}>Loading more tracks...</span>
        </div>
      )}

      {/* End of list indicator */}
      {!hasMore && tracks.length > 0 && (
        <div style={styles.endMessage}>
          <span>End of list ({tracks.length} tracks)</span>
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
    width: '100%',
    height: '100%',
    overflow: 'hidden',
    backgroundColor: tokens.colors.bg.primary,
    borderRadius: tokens.borderRadius.md,
  },

  trackList: {
    display: 'flex',
    flexDirection: 'column' as const,
    flex: 1,
    overflow: 'auto',
    overscrollBehavior: 'contain' as const,
  },

  trackItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    cursor: 'pointer',
    transition: 'background-color 0.15s ease',

    '&:hover': {
      backgroundColor: tokens.colors.bg.level2,
    },
  },

  trackItemSelected: {
    backgroundColor: tokens.colors.accent.subtle,
    borderLeftColor: tokens.colors.accent.primary,
    borderLeftWidth: '3px',
    paddingLeft: `calc(${tokens.spacing.md} - 3px)`,
  },

  trackNumber: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '32px',
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    fontWeight: tokens.typography.fontWeight.bold,
  },

  trackInfo: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
    flex: 1,
    minWidth: 0, // Enable text overflow
  },

  trackTitle: {
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    color: tokens.colors.text.primary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  trackMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  artist: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  album: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  separator: {
    opacity: 0.5,
    flexShrink: 0,
  },

  duration: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    fontFamily: tokens.typography.fontFamily.monospace,
    flexShrink: 0,
    minWidth: '40px',
    textAlign: 'right' as const,
  },

  sentinel: {
    height: '10px',
    flexShrink: 0,
  },

  loadingContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: tokens.spacing.md,
    borderTop: `1px solid ${tokens.colors.border.light}`,
  },

  loadingText: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
  },

  endMessage: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: tokens.spacing.md,
    borderTop: `1px solid ${tokens.colors.border.light}`,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    fontStyle: 'italic' as const,
  },

  errorContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: tokens.spacing.lg,
    gap: tokens.spacing.sm,
    backgroundColor: tokens.colors.error,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.onError,
  },

  errorText: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
  },

  errorSubtext: {
    margin: 0,
    fontSize: tokens.typography.fontSize.sm,
    opacity: 0.8,
  },

  emptyContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: tokens.spacing.lg,
    gap: tokens.spacing.sm,
    color: tokens.colors.text.tertiary,
  },

  emptyText: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
  },

  emptySubtext: {
    margin: 0,
    fontSize: tokens.typography.fontSize.sm,
  },
};

export default TrackList;
