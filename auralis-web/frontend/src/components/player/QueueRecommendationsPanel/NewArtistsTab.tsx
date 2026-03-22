import React, { useState } from 'react';
import { styles } from './styles';

interface NewArtistsTabProps {
  newArtists: any[];
  onAddTrack: (track: any) => void;
}

export const NewArtistsTab = ({ newArtists, onAddTrack }: NewArtistsTabProps) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (newArtists.length === 0) {
    return (
      <div style={styles.emptyState}>
        <p>No new artists to discover</p>
      </div>
    );
  }

  return (
    <div style={styles.tabContent}>
      {newArtists.map((artist, index) => (
        <div
          key={`artist-${artist.artist}`}
          style={{
            ...styles.artistCard,
            ...(hoveredIndex === index ? styles.artistCardHovered : {}),
          }}
          onMouseEnter={() => setHoveredIndex(index)}
          onMouseLeave={() => setHoveredIndex(null)}
        >
          <div style={styles.artistName}>{artist.artist}</div>
          <div style={styles.artistCount}>
            {artist.trackCount} track{artist.trackCount !== 1 ? 's' : ''}
          </div>

          <div style={styles.artistTracks}>
            {artist.tracks?.slice(0, 2).map((track: any, tIndex: number) => (
              <div
                key={track.id ?? tIndex}
                style={{
                  ...styles.artistTrackItem,
                  ...(hoveredIndex === index ? styles.artistTrackItemVisible : {}),
                }}
              >
                <span style={styles.artistTrackTitle}>{track.title}</span>
                {hoveredIndex === index && (
                  <button
                    style={styles.addButtonSmall}
                    onClick={() => onAddTrack(track)}
                    title="Add to queue"
                  >
                    +
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
