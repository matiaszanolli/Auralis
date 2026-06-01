/**
 * useStreamingProgressMetrics Hook
 *
 * Encapsulates the buffer-health / progress domain math previously inlined in
 * StreamingProgressBar.tsx (#3939 / CQ-3). Keeping it as a standalone hook makes
 * the computations independently unit-testable and shrinks the component body.
 */

import { useMemo } from 'react';
import { tokens } from '@/design-system';

/** Inputs needed to derive the streaming-progress metrics. */
export interface StreamingProgressMetricsInput {
  /** Overall progress (0-100). */
  progress: number;
  /** Number of buffered samples in the circular buffer. */
  bufferedSamples: number;
  /** Total number of chunks in the stream. */
  totalChunks: number;
  /** Number of chunks already processed. */
  processedChunks: number;
  /** Sample rate in Hz (e.g. 48000). */
  sampleRate: number;
}

/** Buffer status label + the token color used to render it. */
export interface BufferStatus {
  label: string;
  color: string;
}

/** Derived metrics consumed by StreamingProgressBar. */
export interface StreamingProgressMetrics {
  /** Buffered audio duration in seconds. */
  bufferedDuration: number;
  /** Estimated remaining time in seconds (0 when total is unknown). */
  estimatedRemaining: number;
  /** Buffer fill relative to a 2 s "healthy" target, 0-100. */
  bufferPercentage: number;
  /** Buffer health label + color. */
  bufferStatus: BufferStatus;
  /** Progress-bar color keyed off progress thresholds. */
  progressBarColor: string;
  /** Buffer fill bar width, capped at 100. */
  bufferFillWidth: number;
}

/** Buffer is considered "healthy" once it holds this many seconds of audio. */
const HEALTHY_BUFFER_SECONDS = 2.0;
/** Rough per-chunk cost: ~100 ms processing + ~100 ms network. */
const SECONDS_PER_REMAINING_CHUNK = 0.2;

export const useStreamingProgressMetrics = ({
  progress,
  bufferedSamples,
  totalChunks,
  processedChunks,
  sampleRate,
}: StreamingProgressMetricsInput): StreamingProgressMetrics => {
  const bufferedDuration = useMemo(() => {
    // Guard against a zero/invalid sample rate producing NaN/Infinity.
    if (!sampleRate) return 0;
    return bufferedSamples / sampleRate;
  }, [bufferedSamples, sampleRate]);

  const estimatedRemaining = useMemo(() => {
    if (totalChunks === 0) return 0;
    const remainingChunks = Math.max(0, totalChunks - processedChunks);
    return remainingChunks * SECONDS_PER_REMAINING_CHUNK;
  }, [totalChunks, processedChunks]);

  const bufferPercentage = useMemo(() => {
    if (bufferedDuration === 0) return 0;
    return Math.min(100, (bufferedDuration / HEALTHY_BUFFER_SECONDS) * 100);
  }, [bufferedDuration]);

  const bufferStatus = useMemo<BufferStatus>(() => {
    if (bufferedDuration < 0.5) {
      return { label: 'Critical', color: tokens.colors.semantic.error };
    } else if (bufferedDuration < 1.0) {
      return { label: 'Low', color: tokens.colors.semantic.warning };
    } else if (bufferedDuration < HEALTHY_BUFFER_SECONDS) {
      return { label: 'Adequate', color: tokens.colors.semantic.info };
    }
    return { label: 'Healthy', color: tokens.colors.semantic.success };
  }, [bufferedDuration]);

  const progressBarColor = useMemo(() => {
    if (progress >= 100) return tokens.colors.semantic.success;
    if (progress >= 75) return tokens.colors.semantic.info;
    if (progress >= 50) return tokens.colors.semantic.warning;
    return tokens.colors.semantic.error;
  }, [progress]);

  const bufferFillWidth = useMemo(() => {
    // Buffer fill renders on a separate bar, capped at 100%.
    return Math.min(100, bufferPercentage);
  }, [bufferPercentage]);

  return {
    bufferedDuration,
    estimatedRemaining,
    bufferPercentage,
    bufferStatus,
    progressBarColor,
    bufferFillWidth,
  };
};
