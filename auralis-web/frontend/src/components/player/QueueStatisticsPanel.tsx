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
 * Usage:
 * ```typescript
 * <QueueStatisticsPanel collapsed={false} onToggleCollapse={() => {}} />
 * ```
 *
 * @module components/player/QueueStatisticsPanel
 */

import React from 'react';
import { tokens } from '@/design-system';
import { usePlaybackQueue } from '@/hooks/player/usePlaybackQueue';
import { useQueueStatistics } from '@/hooks/player/useQueueStatistics';
import type { TopItem, QualityAssessment } from '@/hooks/player/useQueueStatistics';

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
export const QueueStatisticsPanel: React.FC<QueueStatisticsPanelProps> = ({
  collapsed = false,
  onToggleCollapse,
}) => {
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

/**
 * StatItem - displays a statistic with label and value
 */
interface StatItemProps {
  label: string;
  value: string;
}

const StatItem: React.FC<StatItemProps> = ({ label, value }) => (
  <div style={styles.statItem}>
    <div style={styles.statLabel}>{label}</div>
    <div style={styles.statValue}>{value}</div>
  </div>
);

/**
 * StatRow - displays a statistic as a row
 */
interface StatRowProps {
  label: string;
  value: string;
}

const StatRow: React.FC<StatRowProps> = ({ label, value }) => (
  <div style={styles.statRow}>
    <span style={styles.statRowLabel}>{label}</span>
    <span style={styles.statRowValue}>{value}</span>
  </div>
);

/**
 * TopItemRow - displays a top item with rank and percentage
 */
interface TopItemRowProps {
  item: TopItem;
  index: number;
}

const TopItemRow: React.FC<TopItemRowProps> = ({ item, index }) => (
  <div style={styles.topItemRow}>
    <span style={styles.topItemRank}>#{index + 1}</span>
    <span style={styles.topItemValue}>{item.value}</span>
    <span style={styles.topItemStats}>
      {item.count} track{item.count !== 1 ? 's' : ''} ({item.percentage.toFixed(1)}%)
    </span>
  </div>
);

/**
 * QualityRating - displays queue quality assessment
 */
interface QualityRatingProps {
  assessment: QualityAssessment;
}

const QualityRating: React.FC<QualityRatingProps> = ({ assessment }) => {
  const ratingColor =
    assessment.rating === 'excellent'
      ? tokens.colors.semantic.success
      : assessment.rating === 'good'
        ? tokens.colors.accent.primary
        : assessment.rating === 'fair'
          ? tokens.colors.semantic.warning
          : tokens.colors.semantic.error;

  const ratingIcon =
    assessment.rating === 'excellent'
      ? '✓✓'
      : assessment.rating === 'good'
        ? '✓'
        : assessment.rating === 'fair'
          ? '⚠'
          : '✕';

  return (
    <div style={styles.qualityContainer}>
      <div
        style={{
          ...styles.qualityBadge,
          backgroundColor: ratingColor,
        }}
      >
        <span style={styles.qualityIcon}>{ratingIcon}</span>
        <span style={styles.qualityText}>{assessment.rating.toUpperCase()}</span>
      </div>

      {assessment.issues.length > 0 && (
        <div style={styles.issuesList}>
          {assessment.issues.map((issue, index) => (
            <div key={`issue-${index}`} style={styles.issueItem}>
              • {issue}
            </div>
          ))}
        </div>
      )}

      {assessment.issues.length === 0 && (
        <div style={styles.issuesList}>
          <div style={styles.issueItem}>✓ Queue is well-balanced</div>
        </div>
      )}
    </div>
  );
};

/**
 * Format duration in MM:SS or HH:MM:SS format
 */
function formatDuration(seconds: number): string {
  if (!isFinite(seconds)) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

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

  content: {
    flex: 1,
    overflow: 'auto',
    padding: tokens.spacing.md,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.lg,
  },

  section: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
  },

  sectionTitle: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    paddingBottom: tokens.spacing.xs,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  },

  summaryGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: tokens.spacing.md,
  },

  statItem: {
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  statLabel: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    fontWeight: tokens.typography.fontWeight.semibold,
  },

  statValue: {
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  statsGrid: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  statRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.sm,
  },

  statRowLabel: {
    color: tokens.colors.text.tertiary,
    fontWeight: tokens.typography.fontWeight.semibold,
  },

  statRowValue: {
    color: tokens.colors.text.primary,
    fontWeight: tokens.typography.fontWeight.bold,
    fontVariantNumeric: 'tabular-nums' as const,
  },

  listSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  topItemRow: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.sm,
  },

  topItemRank: {
    color: tokens.colors.accent.primary,
    fontWeight: tokens.typography.fontWeight.bold,
    minWidth: '30px',
  },

  topItemValue: {
    flex: 1,
    color: tokens.colors.text.primary,
    fontWeight: tokens.typography.fontWeight.semibold,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  topItemStats: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
    flexShrink: 0,
  },

  qualityContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
  },

  qualityBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primaryFull, // White text on colored badge
    fontWeight: tokens.typography.fontWeight.bold,
    fontSize: tokens.typography.fontSize.sm,
  },

  qualityIcon: {
    fontSize: tokens.typography.fontSize.lg,
  },

  qualityText: {
    flex: 1,
  },

  issuesList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  issueItem: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    padding: tokens.spacing.xs,
    paddingLeft: tokens.spacing.sm,
  },

  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: tokens.colors.text.tertiary,
    textAlign: 'center' as const,
  },

  emptySubtext: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },
};

export default QueueStatisticsPanel;
