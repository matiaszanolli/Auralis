import React, { useState } from 'react';
import type { TrackRecommendation } from '@/utils/queue/queue_recommender';
import { styles } from './styles';

interface RecommendationTabProps {
  title: string;
  recommendations: TrackRecommendation[];
  onAddTrack: (track: any) => void;
}

export const RecommendationTab = ({
  title: _title,
  recommendations,
  onAddTrack,
}: RecommendationTabProps) => {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  if (recommendations.length === 0) {
    return (
      <div style={styles.emptyState}>
        <p>No recommendations found</p>
      </div>
    );
  }

  return (
    <div style={styles.tabContent}>
      {recommendations.map((rec, index) => (
        <div
          key={`${rec.track.id}-${index}`}
          style={{
            ...styles.recommendationItem,
            ...(hoveredId === rec.track.id ? styles.recommendationItemHovered : {}),
          }}
          onMouseEnter={() => setHoveredId(rec.track.id)}
          onMouseLeave={() => setHoveredId(null)}
        >
          <div style={styles.recInfo}>
            <div style={styles.recTitle}>{rec.track.title}</div>
            <div style={styles.recArtist}>{rec.track.artist}</div>
            <div style={styles.recReason}>{rec.reason}</div>
          </div>

          <div style={styles.recScore}>
            <div style={styles.scoreValue}>
              {Math.round(rec.score * 100)}%
            </div>
          </div>

          {hoveredId === rec.track.id && (
            <button
              style={styles.addButton}
              onClick={() => onAddTrack(rec.track)}
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
