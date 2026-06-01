/**
 * QueueStatisticsPanel sub-components
 *
 * The small presentational rows used by QueueStatisticsPanel, extracted from the
 * main file (#3938 / CQ-2) to keep it under the 300-line module limit. Behavior
 * and markup are unchanged.
 *
 * @module components/player/QueueStatisticsPanel.parts
 */

import { tokens } from '@/design-system';
import type { TopItem, QualityAssessment } from '@/hooks/player/useQueueStatistics';
import { styles } from './QueueStatisticsPanel.styles';

/**
 * StatItem - displays a statistic with label and value
 */
interface StatItemProps {
  label: string;
  value: string;
}

export const StatItem = ({ label, value }: StatItemProps) => (
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

export const StatRow = ({ label, value }: StatRowProps) => (
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

export const TopItemRow = ({ item, index }: TopItemRowProps) => (
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

export const QualityRating = ({ assessment }: QualityRatingProps) => {
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
          {/* #3075: include index in the key so duplicate issue
              strings (rare but possible — multiple instances of the
              same warning) don't collide on the React key. Matches
              the pattern used by the artists/albums/formats lists
              above. */}
          {assessment.issues.map((issue, index) => (
            <div key={`${issue}-${index}`} style={styles.issueItem}>
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
