/**
 * QueueStatisticsPanel Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays queue statistics and analytics.
 * Shows metrics like total duration, track count, genre distribution, etc.
 *
 * Features:
 * - Queue summary (count, duration, artists, albums)
 * - Top artists, albums, and formats
 * - Quality assessment rating
 * - Estimated play time
 * - Responsive design with design tokens
 *
 * The presentational sub-components live in `QueueStatisticsPanel.parts.tsx` and
 * the styles object in `QueueStatisticsPanel.styles.ts` (#3938 / CQ-2), keeping
 * this file under the 300-line module limit.
 *
 * Usage:
 * ```typescript
 * <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
 * ```
 *
 * @module components/player/QueueStatisticsPanel
 */

import { formatDuration } from '@/utils/timeFormat';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { useQueueStatistics } from '@/hooks/player/useQueueStatistics';
import { styles } from './QueueStatisticsPanel.styles';
import { StatItem, StatRow, TopItemRow, QualityRating } from './QueueStatisticsPanel.parts';

interface QueueStatisticsPanelProps {
  /** Whether panel is collapsed */
  collapsed?: boolean;

  /** Callback when collapse toggle is clicked */
  onToggleCollapse?: () => void;
}

/**
 * QueueStatisticsPanel Component
 *
 * Displays comprehensive queue statistics and analytics.
 */
export const QueueStatisticsPanel = ({
  collapsed = false,
  onToggleCollapse,
}: QueueStatisticsPanelProps) => {
  const { queue } = usePlaybackQueue();
  const {
    stats,
    topArtists,
    topAlbums,
    topFormats,
    qualityRating,
    isEmpty,
  } = useQueueStatistics(queue);

  if (collapsed) {
    return (
      <div style={styles.collapsedContainer}>
        <button
          style={styles.toggleButton}
          onClick={onToggleCollapse}
          title="Expand statistics"
          aria-label="Expand statistics panel"
        >
          📊 Stats
        </button>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h3 style={styles.title}>Queue Statistics</h3>
          <button
            style={styles.toggleButton}
            onClick={onToggleCollapse}
            title="Collapse statistics"
            aria-label="Collapse statistics panel"
          >
            ▼
          </button>
        </div>
        <div style={styles.emptyState}>
          <p>No queue to analyze</p>
          <p style={styles.emptySubtext}>Add tracks to see statistics</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h3 style={styles.title}>Queue Statistics</h3>
        <button
          style={styles.toggleButton}
          onClick={onToggleCollapse}
          title="Collapse statistics"
          aria-label="Collapse statistics panel"
        >
          ▼
        </button>
      </div>

      {/* Content */}
      <div style={styles.content}>
        {/* Summary Section */}
        <div style={styles.section}>
          <h4 style={styles.sectionTitle}>Summary</h4>
          <div style={styles.summaryGrid}>
            <StatItem label="Tracks" value={stats.trackCount.toString()} />
            <StatItem label="Duration" value={stats.estimatedPlayTime} />
            <StatItem label="Artists" value={stats.uniqueArtists.toString()} />
            <StatItem label="Albums" value={stats.uniqueAlbums.toString()} />
          </div>
        </div>

        {/* Duration Analysis */}
        <div style={styles.section}>
          <h4 style={styles.sectionTitle}>Duration Analysis</h4>
          <div style={styles.statsGrid}>
            <StatRow label="Min" value={formatDuration(stats.minDuration)} />
            <StatRow label="Max" value={formatDuration(stats.maxDuration)} />
            <StatRow
              label="Average"
              value={formatDuration(stats.averageDuration)}
            />
            <StatRow label="Median" value={formatDuration(stats.medianDuration)} />
          </div>
        </div>

        {/* Top Artists */}
        {topArtists.length > 0 && (
          <div style={styles.section}>
            <h4 style={styles.sectionTitle}>Top Artists</h4>
            <div style={styles.listSection}>
              {topArtists.map((artist, index) => (
                <TopItemRow
                  key={`${artist.value}-${index}`}
                  item={artist}
                  index={index}
                />
              ))}
            </div>
          </div>
        )}

        {/* Top Albums */}
        {topAlbums.length > 0 && (
          <div style={styles.section}>
            <h4 style={styles.sectionTitle}>Top Albums</h4>
            <div style={styles.listSection}>
              {topAlbums.map((album, index) => (
                <TopItemRow
                  key={`${album.value}-${index}`}
                  item={album}
                  index={index}
                />
              ))}
            </div>
          </div>
        )}

        {/* Top Formats */}
        {topFormats.length > 0 && (
          <div style={styles.section}>
            <h4 style={styles.sectionTitle}>File Formats</h4>
            <div style={styles.listSection}>
              {topFormats.map((format, index) => (
                <TopItemRow
                  key={`${format.value}-${index}`}
                  item={format}
                  index={index}
                />
              ))}
            </div>
          </div>
        )}

        {/* Quality Assessment */}
        <div style={styles.section}>
          <h4 style={styles.sectionTitle}>Quality Assessment</h4>
          <QualityRating assessment={qualityRating} />
        </div>
      </div>
    </div>
  );
};

export default QueueStatisticsPanel;
