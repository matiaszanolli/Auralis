import { useState } from 'react';
import type { Track } from '@/types/domain';
import type { TrackRecommendation } from '@/utils/queue/queue_recommender';
import { styles } from './styles';

interface RecommendationTabProps {
  title: string;
  recommendations: TrackRecommendation[];
  onAddTrack: (track: Track) => void;
}

export const RecommendationTab = ({
  title: _title,
  recommendations,
  onAddTrack,
}: RecommendationTabProps) => {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [focusedId, setFocusedId] = useState<number | null>(null);

  if (recommendations.length === 0) {
    return (
      <div style={styles.emptyState}>
        <p>No recommendations found</p>
      </div>
    );
  }

  return (
    <div style={styles.tabContent}>
      {recommendations.map((rec, index) => {
        // Show the Add button on focus as well as hover (fixes #3932) — a
        // hover-only button never appears in the DOM for a keyboard user to
        // reach, since Tab focus only lands on elements already rendered.
        const showActions = hoveredId === rec.track.id || focusedId === rec.track.id;
        return (
          <div
            key={`${rec.track.id}-${index}`}
            style={{
              ...styles.recommendationItem,
              ...(showActions ? styles.recommendationItemHovered : {}),
            }}
            tabIndex={0}
            onMouseEnter={() => setHoveredId(rec.track.id)}
            onMouseLeave={() => setHoveredId(null)}
            onFocus={() => setFocusedId(rec.track.id)}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                setFocusedId(null);
              }
            }}
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

            {showActions && (
              <button
                style={styles.addButton}
                onClick={() => onAddTrack(rec.track)}
                title="Add to queue"
                aria-label={`Add ${rec.track.title} to queue`}
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
