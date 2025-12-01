/**
 * QueueSearchPanel Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays search and filter UI for queue management.
 * Allows users to quickly find tracks by name, artist, or album.
 * Provides quick filters for duration and other track properties.
 *
 * Features:
 * - Real-time search input with debouncing
 * - Quick duration filter buttons (< 3 min, 3-5 min, > 5 min)
 * - Clear filters button
 * - Match count display
 * - Search result highlighting
 * - Responsive design
 *
 * Usage:
 * ```typescript
 * <QueueSearchPanel
 *   isOpen={true}
 *   onClose={() => setOpen(false)}
 *   onTrackSelect={(track) => playTrack(track)}
 * />
 * ```
 *
 * @module components/player/QueueSearchPanel
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { tokens } from '@/design-system';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { useQueueSearch } from '@/hooks/player/useQueueSearch';
import type { SearchResult } from '@/hooks/player/useQueueSearch';

interface QueueSearchPanelProps {
  /** Whether search panel is open */
  isOpen: boolean;

  /** Callback when panel is closed */
  onClose: () => void;

  /** Optional callback when track is selected from search results */
  onTrackSelect?: (result: SearchResult) => void;
}

/**
 * QueueSearchPanel Component
 *
 * Provides search and filtering UI for the playback queue.
 * Displays filtered search results with highlight information.
 */
export const QueueSearchPanel: React.FC<QueueSearchPanelProps> = ({
  isOpen,
  onClose,
  onTrackSelect,
}) => {
  const { queue, removeTrack } = usePlaybackQueue();
  const {
    searchQuery,
    setSearchQuery,
    filteredTracks,
    filters,
    setFilters,
    clearFilters,
    matchCount,
  } = useQueueSearch(queue);

  // UI state
  const [durationFilter, setDurationFilter] = useState<'all' | 'short' | 'medium' | 'long'>('all');
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Apply duration filter when duration button is clicked
  useEffect(() => {
    switch (durationFilter) {
      case 'short':
        setFilters({ maxDuration: 180 }); // < 3 minutes
        break;
      case 'medium':
        setFilters({ minDuration: 180, maxDuration: 300 }); // 3-5 minutes
        break;
      case 'long':
        setFilters({ minDuration: 300 }); // > 5 minutes
        break;
      case 'all':
        // Clear duration filters
        setFilters({});
        break;
    }
  }, [durationFilter, setFilters]);

  if (!isOpen) {
    return null;
  }

  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    setDurationFilter('all');
    clearFilters();
  }, [setSearchQuery, clearFilters]);

  const handleRemoveTrack = async (result: SearchResult) => {
    try {
      await removeTrack(result.originalIndex);
    } catch (err) {
      console.error('Failed to remove track from queue:', err);
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={styles.header}>
          <h2 style={styles.title}>Search Queue</h2>
          <button
            style={styles.closeButton}
            onClick={onClose}
            aria-label="Close search panel"
          >
            ✕
          </button>
        </div>

        {/* Search Input */}
        <div style={styles.searchSection}>
          <div style={styles.searchInputWrapper}>
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search by title, artist, or album..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={styles.searchInput}
              aria-label="Search queue"
            />
            {searchQuery && (
              <button
                style={styles.clearSearchButton}
                onClick={() => setSearchQuery('')}
                aria-label="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          {/* Duration Filter Buttons */}
          <div style={styles.filterButtons}>
            <button
              style={{
                ...styles.filterButton,
                ...(durationFilter === 'all' ? styles.filterButtonActive : {}),
              }}
              onClick={() => setDurationFilter('all')}
              title="All durations"
            >
              All
            </button>
            <button
              style={{
                ...styles.filterButton,
                ...(durationFilter === 'short' ? styles.filterButtonActive : {}),
              }}
              onClick={() => setDurationFilter('short')}
              title="Less than 3 minutes"
            >
              Short (&lt;3m)
            </button>
            <button
              style={{
                ...styles.filterButton,
                ...(durationFilter === 'medium' ? styles.filterButtonActive : {}),
              }}
              onClick={() => setDurationFilter('medium')}
              title="3 to 5 minutes"
            >
              Medium (3-5m)
            </button>
            <button
              style={{
                ...styles.filterButton,
                ...(durationFilter === 'long' ? styles.filterButtonActive : {}),
              }}
              onClick={() => setDurationFilter('long')}
              title="More than 5 minutes"
            >
              Long (&gt;5m)
            </button>
          </div>

          {/* Results Info */}
          <div style={styles.resultsInfo}>
            {searchQuery || durationFilter !== 'all' ? (
              <span>
                {matchCount} result{matchCount !== 1 ? 's' : ''} found
                {searchQuery && ` for "${searchQuery}"`}
              </span>
            ) : (
              <span>Start typing to search...</span>
            )}
          </div>
        </div>

        {/* Search Results */}
        <div style={styles.resultsContainer}>
          {filteredTracks.length === 0 && (searchQuery || durationFilter !== 'all') ? (
            <div style={styles.noResults}>
              <p>No tracks found</p>
              {searchQuery && (
                <p style={styles.noResultsHint}>
                  Try searching for different keywords
                </p>
              )}
            </div>
          ) : (
            <ul style={styles.resultsList}>
              {filteredTracks.map((result) => (
                <SearchResultItem
                  key={`${result.track.id}-${result.originalIndex}`}
                  result={result}
                  onSelect={onTrackSelect}
                  onRemove={() => handleRemoveTrack(result)}
                />
              ))}
            </ul>
          )}
        </div>

        {/* Footer */}
        {(searchQuery || durationFilter !== 'all') && (
          <div style={styles.footer}>
            <button
              style={styles.clearAllButton}
              onClick={handleClearSearch}
            >
              Clear All Filters
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * SearchResultItem Component
 *
 * Displays a single search result with highlight indicators.
 */
interface SearchResultItemProps {
  result: SearchResult;
  onSelect?: (result: SearchResult) => void;
  onRemove: () => void;
}

const SearchResultItem: React.FC<SearchResultItemProps> = ({
  result,
  onSelect,
  onRemove,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const handleClick = () => {
    if (onSelect) {
      onSelect(result);
    }
  };

  return (
    <li
      style={{
        ...styles.resultItem,
        ...(isHovered ? styles.resultItemHovered : {}),
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div style={styles.resultItemContent}>
        {/* Track Info */}
        <div
          style={styles.resultInfo}
          onClick={handleClick}
          role="button"
          tabIndex={0}
          onKeyPress={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              handleClick();
            }
          }}
        >
          <div style={styles.resultTitle}>
            {result.track.title}
            {result.titleMatch && <span style={styles.matchBadge}>Title</span>}
          </div>
          <div style={styles.resultSubtitle}>
            {result.track.artist}
            {result.artistMatch && <span style={styles.matchBadge}>Artist</span>}
          </div>
          {result.track.album && (
            <div style={styles.resultAlbum}>
              {result.track.album}
              {result.albumMatch && <span style={styles.matchBadge}>Album</span>}
            </div>
          )}
        </div>

        {/* Duration and Actions */}
        <div style={styles.resultActions}>
          <span style={styles.resultDuration}>
            {formatDuration(result.track.duration)}
          </span>
          {isHovered && (
            <button
              style={styles.resultRemoveButton}
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              title="Remove from queue"
              aria-label="Remove from queue"
            >
              ✕
            </button>
          )}
        </div>
      </div>
    </li>
  );
};

/**
 * Format duration in MM:SS or HH:MM:SS format
 */
function formatDuration(seconds: number): string {
  if (!isFinite(seconds)) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Component styles using design tokens
 */
const styles = {
  overlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    paddingTop: tokens.spacing.xl,
    zIndex: 1000,
  },

  panel: {
    backgroundColor: tokens.colors.bg.primary,
    borderRadius: tokens.borderRadius.lg,
    border: `1px solid ${tokens.colors.border.default}`,
    display: 'flex',
    flexDirection: 'column' as const,
    width: '90%',
    maxWidth: '600px',
    maxHeight: '80vh',
    boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)',
  },

  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: tokens.spacing.lg,
    borderBottom: `1px solid ${tokens.colors.border.default}`,
    flexShrink: 0,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  closeButton: {
    background: 'none',
    border: 'none',
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    padding: tokens.spacing.sm,
    borderRadius: tokens.borderRadius.md,
    transition: 'background-color 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  searchSection: {
    padding: tokens.spacing.lg,
    borderBottom: `1px solid ${tokens.colors.border.default}`,
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
  },

  searchInputWrapper: {
    position: 'relative' as const,
    display: 'flex',
    alignItems: 'center',
  },

  searchInput: {
    width: '100%',
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.default}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
    fontFamily: 'inherit',
    transition: 'border-color 0.2s',

    ':focus': {
      outline: 'none',
      borderColor: tokens.colors.accent.primary || '#0066cc',
    },

    '::placeholder': {
      color: tokens.colors.text.tertiary,
    },
  },

  clearSearchButton: {
    position: 'absolute' as const,
    right: tokens.spacing.sm,
    background: 'none',
    border: 'none',
    color: tokens.colors.text.tertiary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    padding: tokens.spacing.xs,
    borderRadius: tokens.borderRadius.sm,
    transition: 'color 0.2s',

    ':hover': {
      color: tokens.colors.text.primary,
    },
  },

  filterButtons: {
    display: 'flex',
    gap: tokens.spacing.sm,
    flexWrap: 'wrap' as const,
  },

  filterButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.default}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
    },
  },

  filterButtonActive: {
    backgroundColor: tokens.colors.accent.primary || '#0066cc',
    color: tokens.colors.text.inverse || '#ffffff',
    borderColor: tokens.colors.accent.primary || '#0066cc',
  },

  resultsInfo: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
  },

  resultsContainer: {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column' as const,
  },

  resultsList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
  },

  resultItem: {
    borderBottom: `1px solid ${tokens.colors.border.default}`,
    transition: 'background-color 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  resultItemHovered: {
    backgroundColor: tokens.colors.bg.secondary,
  },

  resultItemContent: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
  },

  resultInfo: {
    flex: 1,
    minWidth: 0,
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  resultTitle: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  resultSubtitle: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  resultAlbum: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  matchBadge: {
    display: 'inline-block',
    backgroundColor: tokens.colors.accent.primary || '#0066cc',
    color: tokens.colors.text.inverse || '#ffffff',
    padding: `2px 6px`,
    borderRadius: tokens.borderRadius.sm,
    fontSize: '10px',
    fontWeight: tokens.typography.fontWeight.bold,
    whiteSpace: 'nowrap' as const,
    flexShrink: 0,
  },

  resultActions: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    flexShrink: 0,
  },

  resultDuration: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    fontVariantNumeric: 'tabular-nums' as const,
    minWidth: '48px',
    textAlign: 'right' as const,
  },

  resultRemoveButton: {
    padding: tokens.spacing.xs,
    borderRadius: tokens.borderRadius.md,
    border: 'none',
    backgroundColor: tokens.colors.accent.error || '#ff4444',
    color: tokens.colors.text.inverse || '#ffffff',
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    transition: 'opacity 0.2s',
    flexShrink: 0,

    ':hover': {
      opacity: 0.8,
    },
  },

  noResults: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: tokens.colors.text.tertiary,
    textAlign: 'center' as const,
    padding: tokens.spacing.xl,
  },

  noResultsHint: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },

  footer: {
    padding: tokens.spacing.lg,
    borderTop: `1px solid ${tokens.colors.border.default}`,
    display: 'flex',
    justifyContent: 'flex-end',
    flexShrink: 0,
  },

  clearAllButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.default}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.accent.error || '#ff4444',
      color: tokens.colors.text.inverse || '#ffffff',
    },
  },
};

export default QueueSearchPanel;
