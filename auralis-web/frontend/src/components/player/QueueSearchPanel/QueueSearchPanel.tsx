import React, { useState, useCallback, useRef, useEffect } from 'react';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { useQueueSearch } from '@/hooks/player/useQueueSearch';
import type { SearchResult } from '@/hooks/player/useQueueSearch';
import { SearchResultItem } from './SearchResultItem';
import { panelStyles as styles } from './styles';

interface QueueSearchPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onTrackSelect?: (result: SearchResult) => void;
}

export const QueueSearchPanel = ({
  isOpen,
  onClose,
  onTrackSelect,
}: QueueSearchPanelProps) => {
  const { queue, removeTrack } = usePlaybackQueue();
  const {
    searchQuery,
    setSearchQuery,
    filteredTracks,
    filters: _filters,
    setFilters,
    clearFilters,
    matchCount,
  } = useQueueSearch(queue);

  const [durationFilter, setDurationFilter] = useState<'all' | 'short' | 'medium' | 'long'>('all');
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Focus search input when panel opens (WCAG 2.1 §2.4.3 — fixes #2546)
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    switch (durationFilter) {
      case 'short':
        setFilters({ maxDuration: 180 });
        break;
      case 'medium':
        setFilters({ minDuration: 180, maxDuration: 300 });
        break;
      case 'long':
        setFilters({ minDuration: 300 });
        break;
      case 'all':
        setFilters({});
        break;
    }
  }, [durationFilter, setFilters]);

  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    setDurationFilter('all');
    clearFilters();
  }, [setSearchQuery, clearFilters]);

  if (!isOpen) {
    return null;
  }

  const handleRemoveTrack = async (result: SearchResult) => {
    try {
      await removeTrack(result.originalIndex);
    } catch (err) {
      console.error('Failed to remove track from queue:', err);
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div
        style={styles.panel}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Search queue"
        onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      >
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

export default QueueSearchPanel;
