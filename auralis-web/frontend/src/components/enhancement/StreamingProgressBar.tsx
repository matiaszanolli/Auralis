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
 *
 * Domain math lives in `useStreamingProgressMetrics`; styles live in the
 * `StreamingProgressBar.styles.ts` sidecar (#3939 / CQ-3).
 */

import { tokens } from '@/design-system';
import { formatTime } from '@/utils/timeFormat';
import { styles } from './StreamingProgressBar.styles';
import { useStreamingProgressMetrics } from './useStreamingProgressMetrics';

/**
 * Props for StreamingProgressBar component
 */
export interface StreamingProgressBarProps {
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
export const StreamingProgressBar = ({
  progress,
  bufferedSamples,
  totalChunks,
  processedChunks,
  sampleRate,
  displayTotalChunks,
  showDetails = true,
  currentTime = 0,
}: StreamingProgressBarProps) => {
  const {
    bufferedDuration,
    estimatedRemaining,
    bufferPercentage,
    bufferStatus,
    progressBarColor,
    bufferFillWidth,
  } = useStreamingProgressMetrics({
    progress,
    bufferedSamples,
    totalChunks,
    processedChunks,
    sampleRate,
  });

  return (
    <div style={styles.container}>
      {/* Progress Bar */}
      <div style={styles.section}>
        <div style={styles.progressLabel}>
          <span>Download Progress</span>
          <span style={styles.progressPercent}>{Math.round(progress)}%</span>
        </div>

        <div
          style={styles.progressBarOuter}
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Download progress"
        >
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

        <div
          style={styles.bufferBar}
          role="progressbar"
          aria-valuenow={Math.round(bufferFillWidth)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Buffer status"
        >
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
        <div
          style={styles.gaugeContainer}
          role="progressbar"
          aria-valuenow={Math.round(bufferPercentage)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Buffer health"
        >
          {[20, 40, 60, 80, 100].map((threshold) => (
            <div
              key={threshold}
              style={{
                ...styles.gaugeMark,
                backgroundColor:
                  bufferPercentage >= threshold
                    ? bufferStatus.color
                    : tokens.colors.border.light,
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

export default StreamingProgressBar;
