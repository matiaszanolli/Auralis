import React, { useMemo } from 'react';
import { tokens } from '@/design-system';
import { formatTime } from '@/utils/timeFormat';

interface StreamingStatusProps {
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';
  progress: number;
  processedChunks: number;
  totalChunks: number;
  currentTime: number;
  isStreaming: boolean;
}

export const StreamingStatus = ({
  streamingState,
  progress,
  processedChunks,
  totalChunks,
  currentTime,
  isStreaming,
}: StreamingStatusProps) => {
  const estimatedRemaining = useMemo(() => {
    if (!isStreaming || totalChunks === 0) return null;
    const remainingChunks = totalChunks - processedChunks;
    return remainingChunks * 0.1;
  }, [isStreaming, totalChunks, processedChunks]);

  const statusColor = useMemo(() => {
    switch (streamingState) {
      case 'buffering':
        return tokens.colors.semantic.warning;
      case 'streaming':
        return tokens.colors.semantic.success;
      case 'error':
        return tokens.colors.semantic.error;
      case 'complete':
        return tokens.colors.semantic.success;
      default:
        return tokens.colors.text.secondary;
    }
  }, [streamingState]);

  const statusLabel = useMemo(() => {
    switch (streamingState) {
      case 'buffering':
        return '\uD83D\uDCE5 Buffering...';
      case 'streaming':
        return '\uD83C\uDFB5 Streaming';
      case 'error':
        return '\u274C Error';
      case 'complete':
        return '\u2705 Complete';
      default:
        return '\u23F8\uFE0F Ready';
    }
  }, [streamingState]);

  if (!isStreaming) return null;

  return (
    <div
      style={{
        ...styles.statusDisplay,
        borderLeftColor: statusColor,
      }}
    >
      <div style={styles.statusRow}>
        <span style={{ color: statusColor }}>{statusLabel}</span>
        <span style={styles.statusMetrics}>
          {processedChunks}/{totalChunks} chunks
          {estimatedRemaining && (
            <> (~{formatTime(estimatedRemaining)} left)</>
          )}
        </span>
      </div>

      <div style={styles.progressBarContainer}>
        <div
          style={{
            ...styles.progressBar,
            width: `${Math.min(progress, 100)}%`,
            backgroundColor:
              streamingState === 'buffering'
                ? tokens.colors.semantic.warning
                : tokens.colors.semantic.success,
          }}
        />
      </div>

      <div style={styles.timeDisplay}>
        {formatTime(currentTime)}
        {estimatedRemaining && (
          <> / ~{formatTime(currentTime + estimatedRemaining)}</>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  statusDisplay: {
    padding: tokens.spacing.md,
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,
    border: tokens.glass.subtle.border,
    boxShadow: tokens.glass.subtle.boxShadow,
    borderLeft: `3px solid ${tokens.colors.semantic.success}`,
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.primary,
  },

  statusRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: tokens.spacing.sm,
    fontWeight: tokens.typography.fontWeight.medium,
  },

  statusMetrics: {
    color: tokens.colors.text.secondary,
    fontSize: tokens.typography.fontSize.sm,
  },

  progressBarContainer: {
    width: '100%',
    height: '4px',
    backgroundColor: tokens.colors.border.medium,
    borderRadius: tokens.borderRadius.full,
    overflow: 'hidden',
    marginBottom: tokens.spacing.xs,
  },

  progressBar: {
    height: '100%',
    backgroundColor: tokens.colors.accent.primary,
    transition: `width ${tokens.transitions.slow}`,
  },

  timeDisplay: {
    color: tokens.colors.text.secondary,
    fontSize: tokens.typography.fontSize.sm,
  },
};
