import { useState } from 'react';
import type { Track } from '@/types/domain';
import type { DiscoveryArtist } from '@/hooks/player/useQueueRecommendations';
import { styles } from './styles';

interface NewArtistsTabProps {
  newArtists: DiscoveryArtist[];
  onAddTrack: (track: Track) => void;
}

export const NewArtistsTab = ({ newArtists, onAddTrack }: NewArtistsTabProps) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);

  if (newArtists.length === 0) {
    return (
      <div style={styles.emptyState}>
        <p>No new artists to discover</p>
      </div>
    );
  }

  return (
    <div style={styles.tabContent}>
      {newArtists.map((artist, index) => {
        // Show the Add buttons on focus as well as hover (fixes #3932) — a
        // hover-only button never appears in the DOM for a keyboard user to
        // reach, since Tab focus only lands on elements already rendered.
        const showActions = hoveredIndex === index || focusedIndex === index;
        return (
          <div
            key={`artist-${artist.artist}`}
            style={{
              ...styles.artistCard,
              ...(showActions ? styles.artistCardHovered : {}),
            }}
            tabIndex={0}
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
            onFocus={() => setFocusedIndex(index)}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                setFocusedIndex(null);
              }
            }}
          >
            <div style={styles.artistName}>{artist.artist}</div>
            <div style={styles.artistCount}>
              {artist.trackCount} track{artist.trackCount !== 1 ? 's' : ''}
            </div>

            <div style={styles.artistTracks}>
              {artist.tracks?.slice(0, 2).map((track, tIndex) => (
                <div
                  key={track.id ?? tIndex}
                  style={{
                    ...styles.artistTrackItem,
                    ...(showActions ? styles.artistTrackItemVisible : {}),
                  }}
                >
                  <span style={styles.artistTrackTitle}>{track.title}</span>
                  {showActions && (
                    <button
                      style={styles.addButtonSmall}
                      onClick={() => onAddTrack(track)}
                      title="Add to queue"
                      aria-label={`Add ${track.title} to queue`}
                    >
                      +
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};
