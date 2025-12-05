/**
 * Streaming Progress Bar Component
 *
 * Visual feedback for audio streaming progress and buffer status.
 * Shows progress bar, buffer fill, chunk count, and time estimates.
 *
 * Features:
 * - Main progress bar (0-100%)
 * - Buffer fill indicator
 * - Chunk counter display
 * - Estimated remaining time
 * - Buffered duration display
 * - Animated transitions
 */

import React, { useMemo } from 'react';
import { tokens } from '@/design-system';

/**
 * Props for StreamingProgressBar component
 */
interface StreamingProgressBarProps {
  /** Overall progress (0-100) */
  progress: number;

  /** Number of buffered samples in circular buffer */
  bufferedSamples: number;

  /** Total number of chunks in stream */
  totalChunks: number;

  /** Number of chunks already processed */
  processedChunks: number;

  /** Sample rate (e.g., 48000 Hz) */
  sampleRate: number;

  /** Optional: total chunks for display (defaults to totalChunks) */
  displayTotalChunks?: number;

  /** Optional: show detailed metrics */
  showDetails?: boolean;

  /** Optional: current playback time in seconds */
  currentTime?: number;
}

/**
 * Format seconds into MM:SS format
 */
const formatTime = (seconds: number): string => {
  if (!isFinite(seconds) || seconds < 0) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

/**
 * Format bytes into human-readable format
 */
const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
};

/**
 * StreamingProgressBar Component
 *
 * Provides visual feedback on audio streaming progress with detailed metrics.
 */
export const StreamingProgressBar: React.FC<StreamingProgressBarProps> = ({
  progress,
  bufferedSamples,
  totalChunks,
  processedChunks,
  sampleRate,
  displayTotalChunks,
  showDetails = true,
  currentTime = 0,
}) => {
  /**
   * Calculate buffered duration in seconds
   */
  const bufferedDuration = useMemo(() => {
    return bufferedSamples / sampleRate;
  }, [bufferedSamples, sampleRate]);

  /**
   * Calculate estimated total duration based on chunks
   */
  const estimatedTotalDuration = useMemo(() => {
    if (totalChunks === 0 || sampleRate === 0) return 0;
    // Rough estimate: assume each chunk is ~30 seconds (from backend config)
    return totalChunks * 30;
  }, [totalChunks, sampleRate]);

  /**
   * Calculate estimated remaining time
   */
  const estimatedRemaining = useMemo(() => {
    if (totalChunks === 0) return 0;
    const remainingChunks = Math.max(0, totalChunks - processedChunks);
    // Assume ~100ms processing + ~100ms network per chunk
    return remainingChunks * 0.2;
  }, [totalChunks, processedChunks]);

  /**
   * Calculate buffer percentage
   */
  const bufferPercentage = useMemo(() => {
    if (bufferedDuration === 0) return 0;
    // Consider buffer "healthy" at > 2 seconds
    const healthyBufferDuration = 2.0;
    return Math.min(100, (bufferedDuration / healthyBufferDuration) * 100);
  }, [bufferedDuration]);

  /**
   * Get buffer status label and color
   */
  const bufferStatus = useMemo(() => {
    if (bufferedDuration < 0.5) {
      return { label: 'Critical', color: tokens.colors.error };
    } else if (bufferedDuration < 1.0) {
      return { label: 'Low', color: tokens.colors.warning };
    } else if (bufferedDuration < 2.0) {
      return { label: 'Adequate', color: tokens.colors.info };
    } else {
      return { label: 'Healthy', color: tokens.colors.success };
    }
  }, [bufferedDuration]);

  /**
   * Get progress bar color based on state
   */
  const progressBarColor = useMemo(() => {
    if (progress >= 100) return tokens.colors.success;
    if (progress >= 75) return tokens.colors.info;
    if (progress >= 50) return tokens.colors.warning;
    return tokens.colors.error;
  }, [progress]);

  /**
   * Calculate buffer fill width percentage
   */
  const bufferFillWidth = useMemo(() => {
    // Show buffer fill on a separate bar, capped at 100%
    return Math.min(100, bufferPercentage);
  }, [bufferPercentage]);

  return (
    <div style={styles.container}>
      {/* Progress Bar */}
      <div style={styles.section}>
        <div style={styles.progressLabel}>
          <span>Download Progress</span>
          <span style={styles.progressPercent}>{Math.round(progress)}%</span>
        </div>

        <div style={styles.progressBarOuter}>
          <div
            style={{
              ...styles.progressBarInner,
              width: `${Math.min(progress, 100)}%`,
              backgroundColor: progressBarColor,
            }}
          />
        </div>
      </div>

      {/* Chunk Counter */}
      <div style={styles.section}>
        <div style={styles.chunkInfo}>
          <div style={styles.chunkCount}>
            <span style={styles.label}>Chunks:</span>
            <span style={styles.value}>
              {processedChunks}/{displayTotalChunks || totalChunks}
            </span>
          </div>

          {totalChunks > 0 && (
            <div style={styles.chunkPercentage}>
              ({Math.round((processedChunks / totalChunks) * 100)}%)
            </div>
          )}
        </div>
      </div>

      {/* Buffer Status */}
      <div style={styles.section}>
        <div style={styles.bufferHeader}>
          <span style={styles.label}>Buffer Status</span>
          <span
            style={{
              ...styles.bufferBadge,
              backgroundColor: bufferStatus.color + '20',
              color: bufferStatus.color,
            }}
          >
            {bufferStatus.label}
          </span>
        </div>

        <div style={styles.bufferBar}>
          <div
            style={{
              ...styles.bufferFill,
              width: `${bufferFillWidth}%`,
              backgroundColor: bufferStatus.color,
            }}
          />
        </div>

        {showDetails && (
          <div style={styles.bufferDetails}>
            <div style={styles.bufferMetric}>
              <span style={styles.metricLabel}>Duration:</span>
              <span>{formatTime(bufferedDuration)}</span>
            </div>
            <div style={styles.bufferMetric}>
              <span style={styles.metricLabel}>Size:</span>
              <span>{formatBytes(bufferedSamples * 4)}</span>
            </div>
          </div>
        )}
      </div>

      {/* Time Information */}
      {showDetails && (
        <div style={styles.section}>
          <div style={styles.timeInfo}>
            <div style={styles.timeItem}>
              <span style={styles.label}>Current:</span>
              <span style={styles.value}>{formatTime(currentTime)}</span>
            </div>

            <div style={styles.timeItem}>
              <span style={styles.label}>Buffered:</span>
              <span style={styles.value}>{formatTime(bufferedDuration)}</span>
            </div>

            {estimatedRemaining > 0 && (
              <div style={styles.timeItem}>
                <span style={styles.label}>ETA:</span>
                <span style={styles.value}>
                  ~{formatTime(estimatedRemaining)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Download Speed Estimate */}
      {showDetails && processedChunks > 0 && totalChunks > 0 && (
        <div style={styles.section}>
          <div style={styles.speedInfo}>
            <span style={styles.label}>Speed:</span>
            <span style={styles.value}>
              {((processedChunks / totalChunks) * 100).toFixed(1)}% of chunks
            </span>
          </div>
        </div>
      )}

      {/* Mini Gauge (Buffer Health Visualization) */}
      <div style={styles.gaugeSection}>
        <div style={styles.gaugeContainer}>
          {[20, 40, 60, 80, 100].map((threshold) => (
            <div
              key={threshold}
              style={{
                ...styles.gaugeMark,
                backgroundColor:
                  bufferPercentage >= threshold
                    ? bufferStatus.color
                    : tokens.colors.border,
              }}
            />
          ))}
        </div>
        <div style={styles.gaugeLabels}>
          <span>0s</span>
          <span>2.5s</span>
        </div>
      </div>
    </div>
  );
};

/**
 * Styles for StreamingProgressBar
 */
const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.background.primary,
    borderRadius: '6px',
    border: `1px solid ${tokens.colors.border}`,
    fontSize: '12px',
  },

  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.xs,
  },

  progressLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: tokens.spacing.xs,
  },

  progressPercent: {
    fontWeight: 600,
    color: tokens.colors.text.primary,
    fontSize: '13px',
  },

  progressBarOuter: {
    width: '100%',
    height: '6px',
    backgroundColor: tokens.colors.border,
    borderRadius: '3px',
    overflow: 'hidden',
  },

  progressBarInner: {
    height: '100%',
    transition: 'width 300ms ease-out',
    borderRadius: '3px',
  },

  chunkInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  },

  chunkCount: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  chunkPercentage: {
    color: tokens.colors.text.secondary,
    fontSize: '11px',
  },

  label: {
    color: tokens.colors.text.secondary,
    fontWeight: 500,
  },

  value: {
    color: tokens.colors.text.primary,
    fontWeight: 600,
  },

  bufferHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },

  bufferBadge: {
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
  },

  bufferBar: {
    width: '100%',
    height: '4px',
    backgroundColor: tokens.colors.border,
    borderRadius: '2px',
    overflow: 'hidden',
    marginBottom: tokens.spacing.xs,
  },

  bufferFill: {
    height: '100%',
    transition: 'width 200ms ease-out',
    borderRadius: '2px',
  },

  bufferDetails: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: tokens.spacing.sm,
    paddingTop: tokens.spacing.xs,
  },

  bufferMetric: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 8px',
    backgroundColor: tokens.colors.background.secondary,
    borderRadius: '4px',
  },

  metricLabel: {
    color: tokens.colors.text.secondary,
    fontSize: '11px',
  },

  timeInfo: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
    gap: tokens.spacing.sm,
  },

  timeItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    padding: '8px',
    backgroundColor: tokens.colors.background.secondary,
    borderRadius: '4px',
  },

  speedInfo: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px',
    backgroundColor: tokens.colors.background.secondary,
    borderRadius: '4px',
  },

  gaugeSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    paddingTop: tokens.spacing.xs,
    borderTop: `1px solid ${tokens.colors.border}`,
  },

  gaugeContainer: {
    display: 'flex',
    gap: '4px',
  },

  gaugeMark: {
    flex: 1,
    height: '8px',
    borderRadius: '2px',
    transition: 'background-color 200ms ease-out',
  },

  gaugeLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '10px',
    color: tokens.colors.text.secondary,
  },
};

export default StreamingProgressBar;
