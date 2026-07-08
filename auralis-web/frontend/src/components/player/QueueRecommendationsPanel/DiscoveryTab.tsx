import { useState } from 'react';
import type { Track } from '@/types/domain';
import { styles } from './styles';

interface DiscoveryTabProps {
  tracks: Track[];
  onAddTrack: (track: Track) => void;
}

export const DiscoveryTab = ({ tracks, onAddTrack }: DiscoveryTabProps) => {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [focusedId, setFocusedId] = useState<number | null>(null);

  if (tracks.length === 0) {
    return (
      <div style={styles.emptyState}>
        <p>No discovery tracks available</p>
      </div>
    );
  }

  return (
    <div style={styles.tabContent}>
      {tracks.map((track, index) => {
        // Show the Add button on focus as well as hover (fixes #3932) — a
        // hover-only button never appears in the DOM for a keyboard user to
        // reach, since Tab focus only lands on elements already rendered.
        const showActions = hoveredId === track.id || focusedId === track.id;
        return (
          <div
            key={`${track.id}-${index}`}
            style={{
              ...styles.trackItem,
              ...(showActions ? styles.trackItemHovered : {}),
            }}
            tabIndex={0}
            onMouseEnter={() => setHoveredId(track.id)}
            onMouseLeave={() => setHoveredId(null)}
            onFocus={() => setFocusedId(track.id)}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                setFocusedId(null);
              }
            }}
          >
            <div style={styles.trackIndex}>{index + 1}</div>
            <div style={styles.trackInfo}>
              <div style={styles.trackTitle}>{track.title}</div>
              <div style={styles.trackArtist}>{track.artist}</div>
            </div>

            {showActions && (
              <button
                style={styles.addButton}
                onClick={() => onAddTrack(track)}
                title="Add to queue"
                aria-label={`Add ${track.title} to queue`}
              >
                +
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
};
