import React, { useState } from 'react';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { useQueueRecommendations } from '@/hooks/player/useQueueRecommendations';
import { RecommendationTab } from './RecommendationTab';
import { DiscoveryTab } from './DiscoveryTab';
import { NewArtistsTab } from './NewArtistsTab';
import { styles } from './styles';

interface QueueRecommendationsPanelProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  availableTracks?: any[];
  onAddTrack?: (track: any) => void;
}

export const QueueRecommendationsPanel = ({
  collapsed = false,
  onToggleCollapse,
  availableTracks = [],
  onAddTrack,
}: QueueRecommendationsPanelProps) => {
  const { queue, currentTrack, addTrack } = usePlaybackQueue();
  const {
    forYouRecommendations,
    similarToCurrentTrack,
    discoveryPlaylist,
    newArtists,
    hasEnoughData,
  } = useQueueRecommendations(queue, currentTrack, availableTracks);

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

export default QueueRecommendationsPanel;
