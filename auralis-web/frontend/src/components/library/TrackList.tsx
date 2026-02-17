/**
 * TrackList Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Displays a scrollable list of tracks with infinite scroll pagination.
 * Handles selection, playback, and metadata display.
 *
 * Uses @tanstack/react-virtual for windowed rendering — only ~20 DOM
 * nodes exist at any time regardless of library size.
 *
 * Usage:
 * ```typescript
 * <TrackList />
 * ```
 *
 * Props: None required (uses hooks internally)
 *
 * Features:
 * - Virtualized rendering (bounded DOM node count)
 * - Infinite scroll pagination
 * - Track selection and multi-select
 * - Quick play on click
 * - Responsive design
 * - Loading and error states
 *
 * @module components/library/TrackList
 */

import React, { useCallback, useRef, useEffect, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { tokens } from '@/design-system';
import { useTracksQuery } from '@/hooks/library/useLibraryQuery';
import { formatDuration } from '@/types/domain';
import type { Track } from '@/types/domain';

/** Fixed row height in pixels — must match trackItem padding + two text lines */
const ROW_HEIGHT = 56;

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
 * Displays tracks in a virtualized scrollable list with infinite scroll.
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

  // The scroll element — passed to useVirtualizer as getScrollElement
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: tracks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
  });

  const virtualItems = virtualizer.getVirtualItems();

  // Trigger fetchMore when the user scrolls near the end of the loaded list
  useEffect(() => {
    const lastItem = virtualItems[virtualItems.length - 1];
    if (!lastItem) return;
    if (lastItem.index >= tracks.length - 1 && hasMore && !isLoading) {
      fetchMore().catch((err) => console.error('Failed to fetch more tracks:', err));
    }
  }, [virtualItems, tracks.length, hasMore, isLoading, fetchMore]);

  // Scroll selected track into view using the virtualizer's scroll API
  useEffect(() => {
    if (selectedIndex !== null) {
      virtualizer.scrollToIndex(selectedIndex, { align: 'auto' });
    }
  }, [selectedIndex, virtualizer]);

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
    <div style={styles.container}>
      {/* Scrollable viewport — virtualizer scroll element */}
      <div ref={parentRef} style={styles.trackList}>
        {/* Inner container sized to total virtual height */}
        <div
          style={{
            height: virtualizer.getTotalSize(),
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualItems.map((virtualItem) => {
            const track = tracks[virtualItem.index];
            const isSelected = selectedIndex === virtualItem.index;

            return (
              <div
                key={virtualItem.key}
                data-index={virtualItem.index}
                onClick={() => handleTrackClick(track, virtualItem.index)}
                style={{
                  ...styles.trackItem,
                  ...(isSelected && styles.trackItemSelected),
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualItem.size}px`,
                  transform: `translateY(${virtualItem.start}px)`,
                }}
                role="button"
                tabIndex={0}
                aria-selected={isSelected}
              >
                {/* Track number */}
                <span style={styles.trackNumber}>{virtualItem.index + 1}</span>

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
            );
          })}
        </div>
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
    boxSizing: 'border-box' as const,
  },

  trackItemSelected: {
    backgroundColor: tokens.colors.bg.level2,
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
    minWidth: 0,
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
    fontFamily: tokens.typography.fontFamily.mono,
    flexShrink: 0,
    minWidth: '40px',
    textAlign: 'right' as const,
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
    backgroundColor: tokens.colors.semantic.error,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primary,
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
