import React, { useState } from 'react';
import { formatDuration } from '@/utils/timeFormat';
import type { SearchResult } from '@/hooks/player/useQueueSearch';
import { resultItemStyles as styles } from './resultItemStyles';

interface SearchResultItemProps {
  result: SearchResult;
  onSelect?: (result: SearchResult) => void;
  onRemove: () => void;
}

export const SearchResultItem = ({
  result,
  onSelect,
  onRemove,
}: SearchResultItemProps) => {
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
          aria-label={`Play ${result.track.title} by ${result.track.artist}`}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
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
