import { useState } from 'react';
import type { Track } from '@/types/domain';
import { styles } from './styles';

interface DiscoveryTabProps {
  tracks: Track[];
  onAddTrack: (track: Track) => void;
}

export const DiscoveryTab = ({ tracks, onAddTrack }: DiscoveryTabProps) => {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  if (tracks.length === 0) {
    return (
      <div style={styles.emptyState}>
        <p>No discovery tracks available</p>
      </div>
    );
  }

  return (
    <div style={styles.tabContent}>
      {tracks.map((track, index) => (
        <div
          key={`${track.id}-${index}`}
          style={{
            ...styles.trackItem,
            ...(hoveredId === track.id ? styles.trackItemHovered : {}),
          }}
          onMouseEnter={() => setHoveredId(track.id)}
          onMouseLeave={() => setHoveredId(null)}
        >
          <div style={styles.trackIndex}>{index + 1}</div>
          <div style={styles.trackInfo}>
            <div style={styles.trackTitle}>{track.title}</div>
            <div style={styles.trackArtist}>{track.artist}</div>
          </div>

          {hoveredId === track.id && (
            <button
              style={styles.addButton}
              onClick={() => onAddTrack(track)}
              title="Add to queue"
            >
              +
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
