/**
 * QueueRecommendationsPanel Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays track recommendations and discovery content.
 * Shows For You, Similar to Current, Discovery Playlist, and New Artists.
 *
 * Features:
 * - For You recommendations (collaborative filtering)
 * - Similar to current track
 * - Discovery playlist (diverse selection)
 * - New artists to explore
 * - Add to queue functionality
 * - Responsive design with design tokens
 *
 * Usage:
 * ```typescript
 * <QueueRecommendationsPanel collapsed={false} onToggleCollapse={() => {}} />
 * ```
 *
 * @module components/player/QueueRecommendationsPanel
 */

import React, { useState } from 'react';
import { tokens } from '@/design-system';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { useQueueRecommendations } from '@/hooks/player/useQueueRecommendations';
import type { TrackRecommendation } from '@/utils/queue/queue_recommender';

interface QueueRecommendationsPanelProps {
  /** Whether panel is collapsed */
  collapsed?: boolean;

  /** Callback when collapse toggle is clicked */
  onToggleCollapse?: () => void;

  /** Available tracks for recommendations */
  availableTracks?: any[]; // Track[]

  /** Callback when track is added to queue */
  onAddTrack?: (track: any) => void;
}

/**
 * QueueRecommendationsPanel Component
 *
 * Displays recommendations and discovery content.
 */
export const QueueRecommendationsPanel: React.FC<QueueRecommendationsPanelProps> = ({
  collapsed = false,
  onToggleCollapse,
  availableTracks = [],
  onAddTrack,
}) => {
  const { queue, currentTrack, addTrack } = usePlaybackQueue();
  const {
    forYouRecommendations,
    similarToCurrentTrack,
    discoveryPlaylist,
    newArtists,
    hasEnoughData,
  } = useQueueRecommendations(queue, currentTrack, availableTracks);

  // Tab state
  const [activeTab, setActiveTab] = useState<'for-you' | 'similar' | 'discovery' | 'new-artists'>(
    'for-you'
  );

  if (collapsed) {
    return (
      <div style={styles.collapsedContainer}>
        <button
          style={styles.toggleButton}
          onClick={onToggleCollapse}
          title="Expand recommendations"
          aria-label="Expand recommendations panel"
        >
          ✨ Recommendations
        </button>
      </div>
    );
  }

  const handleAddTrack = async (track: any) => {
    try {
      if (onAddTrack) {
        onAddTrack(track);
      } else {
        await addTrack(track);
      }
    } catch (err) {
      console.error('Failed to add track:', err);
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h3 style={styles.title}>Recommendations</h3>
        <button
          style={styles.toggleButton}
          onClick={onToggleCollapse}
          title="Collapse recommendations"
          aria-label="Collapse recommendations panel"
        >
          ▼
        </button>
      </div>

      {/* Tab Navigation */}
      {hasEnoughData && (
        <div style={styles.tabBar}>
          <button
            style={{
              ...styles.tab,
              ...(activeTab === 'for-you' ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab('for-you')}
          >
            For You
          </button>
          {currentTrack && (
            <button
              style={{
                ...styles.tab,
                ...(activeTab === 'similar' ? styles.tabActive : {}),
              }}
              onClick={() => setActiveTab('similar')}
            >
              Similar
            </button>
          )}
          <button
            style={{
              ...styles.tab,
              ...(activeTab === 'discovery' ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab('discovery')}
          >
            Discover
          </button>
          <button
            style={{
              ...styles.tab,
              ...(activeTab === 'new-artists' ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab('new-artists')}
          >
            New Artists
          </button>
        </div>
      )}

      {/* Content */}
      <div style={styles.content}>
        {!hasEnoughData ? (
          <div style={styles.emptyState}>
            <p>Add more tracks to queue to see recommendations</p>
            <p style={styles.emptySubtext}>We need at least 3 tracks to suggest similar music</p>
          </div>
        ) : activeTab === 'for-you' ? (
          <RecommendationTab
            title="For You"
            recommendations={forYouRecommendations.slice(0, 10)}
            onAddTrack={handleAddTrack}
          />
        ) : activeTab === 'similar' ? (
          <RecommendationTab
            title="Similar to Current"
            recommendations={similarToCurrentTrack.slice(0, 8)}
            onAddTrack={handleAddTrack}
          />
        ) : activeTab === 'discovery' ? (
          <DiscoveryTab
            tracks={discoveryPlaylist.slice(0, 15)}
            onAddTrack={handleAddTrack}
          />
        ) : (
          <NewArtistsTab newArtists={newArtists.slice(0, 5)} onAddTrack={handleAddTrack} />
        )}
      </div>
    </div>
  );
};

/**
 * RecommendationTab - displays recommendations
 */
interface RecommendationTabProps {
  title: string;
  recommendations: TrackRecommendation[];
  onAddTrack: (track: any) => void;
}

const RecommendationTab: React.FC<RecommendationTabProps> = ({
  title,
  recommendations,
  onAddTrack,
}) => {
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

/**
 * DiscoveryTab - displays discovery playlist
 */
interface DiscoveryTabProps {
  tracks: any[];
  onAddTrack: (track: any) => void;
}

const DiscoveryTab: React.FC<DiscoveryTabProps> = ({ tracks, onAddTrack }) => {
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

/**
 * NewArtistsTab - displays new artists to explore
 */
interface NewArtistsTabProps {
  newArtists: any[];
  onAddTrack: (track: any) => void;
}

const NewArtistsTab: React.FC<NewArtistsTabProps> = ({ newArtists, onAddTrack }) => {
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
          key={index}
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
                key={tIndex}
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

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    height: '100%',
    backgroundColor: tokens.colors.bg.primary,
    borderLeft: `1px solid ${tokens.colors.border.light}`,
    overflow: 'hidden',
  },

  collapsedContainer: {
    display: 'flex',
    padding: tokens.spacing.md,
  },

  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  toggleButton: {
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

  tabBar: {
    display: 'flex',
    gap: tokens.spacing.xs,
    padding: tokens.spacing.sm,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    overflow: 'auto',
  },

  tab: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',
    whiteSpace: 'nowrap' as const,

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
    },
  },

  tabActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull, // White text on accent background
    borderColor: tokens.colors.accent.primary,
  },

  content: {
    flex: 1,
    overflow: 'auto',
  },

  tabContent: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
    padding: tokens.spacing.md,
  },

  recommendationItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    transition: 'background-color 0.2s',
    cursor: 'pointer',
  },

  recommendationItemHovered: {
    backgroundColor: tokens.colors.bg.tertiary,
  },

  recInfo: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  recTitle: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  recArtist: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
  },

  recReason: {
    color: tokens.colors.accent.primary || '#0066cc',
    fontSize: tokens.typography.fontSize.xs,
    fontStyle: 'italic',
  },

  recScore: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    minWidth: '40px',
  },

  scoreValue: {
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.accent.primary || '#0066cc',
  },

  trackItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    transition: 'background-color 0.2s',
    cursor: 'pointer',
  },

  trackItemHovered: {
    backgroundColor: tokens.colors.bg.tertiary,
  },

  trackIndex: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
    minWidth: '24px',
    textAlign: 'center' as const,
  },

  trackInfo: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  trackTitle: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  trackArtist: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
  },

  artistCard: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${tokens.colors.border.light}`,
    transition: 'all 0.2s',
  },

  artistCardHovered: {
    backgroundColor: tokens.colors.bg.tertiary,
    borderColor: tokens.colors.accent.primary || '#0066cc',
  },

  artistName: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    marginBottom: tokens.spacing.xs,
  },

  artistCount: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
    marginBottom: tokens.spacing.sm,
  },

  artistTracks: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  artistTrackItem: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
    opacity: 0.7,
  },

  artistTrackItemVisible: {
    opacity: 1,
  },

  artistTrackTitle: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  addButton: {
    padding: tokens.spacing.xs,
    borderRadius: tokens.borderRadius.sm,
    border: 'none',
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull, // White text on accent background
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    transition: 'opacity 0.2s',
    flexShrink: 0,
    minWidth: '28px',
    height: '28px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',

    ':hover': {
      opacity: 0.8,
    },
  },

  addButtonSmall: {
    padding: '2px 4px',
    borderRadius: tokens.borderRadius.sm,
    border: 'none',
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull, // White text on accent background
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.bold,
    transition: 'opacity 0.2s',
  },

  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: tokens.colors.text.tertiary,
    textAlign: 'center' as const,
    padding: tokens.spacing.xl,
  },

  emptySubtext: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },
};

export default QueueRecommendationsPanel;
