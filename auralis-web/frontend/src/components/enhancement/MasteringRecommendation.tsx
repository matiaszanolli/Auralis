/**
 * MasteringRecommendation Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays mastering recommendation for current track.
 * Shows recommended preset based on audio analysis.
 *
 * @module components/enhancement/MasteringRecommendation
 */

import React, { useEffect, useState } from 'react';
import { tokens } from '@/design-system/tokens';
import { useWebSocketLatestMessage } from '@/hooks/websocket/useWebSocketSubscription';
import type { MasteringRecommendationMessage } from '@/types/websocket';

/**
 * MasteringRecommendation component
 *
 * Shows AI-generated mastering recommendation for current track.
 * Displays confidence and recommended settings.
 */
export const MasteringRecommendation: React.FC = () => {
  const recMessage = useWebSocketLatestMessage('mastering_recommendation') as MasteringRecommendationMessage | null;
  const [isExpanded, setIsExpanded] = useState(false);

  if (!recMessage) {
    return (
      <div style={styles.container}>
        <div style={styles.emptyMessage}>No recommendation yet</div>
      </div>
    );
  }

  const data = recMessage.data;
  const confidence = Math.round((data.confidence || 0.5) * 100);

  return (
    <div style={styles.container}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={styles.header}
      >
        <span style={styles.title}>AI Recommendation</span>
        <span style={styles.icon}>{isExpanded ? '▼' : '▶'}</span>
      </button>

      {isExpanded && (
        <div style={styles.content}>
          <div style={styles.recommendation}>
            <div style={styles.label}>Recommended Preset</div>
            <div style={styles.value}>{data.recommended_preset}</div>
          </div>

          <div style={styles.confidence}>
            <div style={styles.label}>Confidence: {confidence}%</div>
            <div
              style={{
                ...styles.confidenceBar,
                width: `${confidence}%`,
              }}
            />
          </div>

          {data.reasoning && (
            <div style={styles.reasoning}>
              <div style={styles.label}>Analysis</div>
              <p style={styles.reasoningText}>{data.reasoning}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const styles = {
  container: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
  },

  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    padding: 0,
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
  },

  title: {
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  icon: {
    color: tokens.colors.text.secondary,
  },

  content: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
    marginTop: tokens.spacing.md,
    paddingTop: tokens.spacing.md,
    borderTop: `1px solid ${tokens.colors.border.subtle}`,
  },

  recommendation: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  label: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
  },

  value: {
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.accent.primary,
    textTransform: 'capitalize' as const,
  },

  confidence: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  confidenceBar: {
    height: '8px',
    backgroundColor: tokens.colors.accent.primary,
    borderRadius: tokens.borderRadius.full,
    transition: 'width 0.3s ease',
  },

  reasoning: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  reasoningText: {
    margin: 0,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
    lineHeight: 1.5,
  },

  emptyMessage: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    textAlign: 'center' as const,
    padding: tokens.spacing.md,
  },
};

export default MasteringRecommendation;
