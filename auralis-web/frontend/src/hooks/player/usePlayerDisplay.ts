/**
 * usePlayerDisplay - Player display formatting utilities hook
 *
 * Provides formatted display strings for player time, progress, and buffering information.
 * Memoizes results to prevent unnecessary recalculations.
 *
 * @module hooks/usePlayerDisplay
 */

import { useMemo } from 'react';

/**
 * Formatted display strings for player UI
 */
export interface PlayerDisplayInfo {
  // Time display
  currentTimeStr: string; // e.g., "1:30"
  durationStr: string; // e.g., "3:45"
  timeRemainingStr: string; // e.g., "-2:15"

  // Progress display
  progressPercentage: number; // 0-100
  bufferedPercentageStr: string; // e.g., "75%"

  // State display
  playPauseLabel: string; // "Play" or "Pause"
  isLiveContent: boolean; // Duration === 0 or Infinity

  // Full formatted strings for UI
  fullTimeDisplay: string; // e.g., "1:30 / 3:45"
  fullTimeWithRemaining: string; // e.g., "1:30 / 3:45 (-2:15)"
}

/**
 * Format seconds to mm:ss or h:mm:ss
 * @param seconds Time in seconds
 * @param showHours Show hours even if 0 (default: false)
 * @returns Formatted time string
 */
function formatTime(seconds: number, showHours = false): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return '0:00';
  }

  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  // Show hours if > 0 or if requested
  if (hours > 0 || showHours) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Configuration for display hook
 */
export interface UsePlayerDisplayConfig {
  /**
   * Current playback position in seconds
   */
  currentTime: number;

  /**
   * Total track duration in seconds
   */
  duration: number;

  /**
   * Whether currently playing
   * Default: false
   */
  isPlaying?: boolean;

  /**
   * Buffered percentage (0-100)
   * Default: 0
   */
  bufferedPercentage?: number;

  /**
   * Show hours in time display even if 0
   * Default: false (only show h:mm:ss if duration > 1 hour)
   */
  forceShowHours?: boolean;
}

/**
 * usePlayerDisplay - Player UI formatting hook
 *
 * Provides memoized formatted strings for player time, progress, and state display.
 * All calculations are memoized and only recalculate when dependencies change.
 *
 * Usage:
 * ```tsx
 * const display = usePlayerDisplay({
 *   currentTime: 90,      // 1:30
 *   duration: 225,        // 3:45
 *   isPlaying: true,
 *   bufferedPercentage: 75,
 * });
 *
 * return (
 *   <>
 *     <span>{display.currentTimeStr}</span>
 *     <span>{display.durationStr}</span>
 *     <span>{display.playPauseLabel}</span>
 *     <progress value={display.progressPercentage} max={100} />
 *   </>
 * );
 * ```
 */
export function usePlayerDisplay({
  currentTime,
  duration,
  isPlaying = false,
  bufferedPercentage = 0,
  forceShowHours = false,
}: UsePlayerDisplayConfig): PlayerDisplayInfo {
  // Format time strings
  const currentTimeStr = useMemo(() => {
    return formatTime(currentTime, forceShowHours || duration >= 3600);
  }, [currentTime, forceShowHours, duration]);

  const durationStr = useMemo(() => {
    return formatTime(duration, forceShowHours || duration >= 3600);
  }, [duration, forceShowHours]);

  // Calculate progress percentage
  const progressPercentage = useMemo(() => {
    if (!Number.isFinite(duration) || duration <= 0) {
      return 0;
    }
    const percentage = (currentTime / duration) * 100;
    return Math.min(Math.max(percentage, 0), 100);
  }, [currentTime, duration]);

  // Time remaining
  const timeRemaining = useMemo(() => {
    if (!Number.isFinite(duration) || duration <= 0) {
      return 0;
    }
    return duration - currentTime;
  }, [currentTime, duration]);

  const timeRemainingStr = useMemo(() => {
    const remaining = timeRemaining;
    if (remaining <= 0) {
      return '0:00';
    }
    return `-${formatTime(remaining, forceShowHours || duration >= 3600)}`;
  }, [timeRemaining, forceShowHours, duration]);

  // Buffered percentage string
  const bufferedPercentageStr = useMemo(() => {
    const clamped = Math.min(Math.max(bufferedPercentage, 0), 100);
    return `${Math.round(clamped)}%`;
  }, [bufferedPercentage]);

  // Determine if live content
  const isLiveContent = useMemo(() => {
    return !Number.isFinite(duration) || duration === 0;
  }, [duration]);

  // Play/pause label
  const playPauseLabel = useMemo(() => {
    return isPlaying ? 'Pause' : 'Play';
  }, [isPlaying]);

  // Full display strings
  const fullTimeDisplay = useMemo(() => {
    if (isLiveContent) {
      return 'LIVE';
    }
    return `${currentTimeStr} / ${durationStr}`;
  }, [currentTimeStr, durationStr, isLiveContent]);

  const fullTimeWithRemaining = useMemo(() => {
    if (isLiveContent) {
      return 'LIVE';
    }
    return `${currentTimeStr} / ${durationStr} (${timeRemainingStr})`;
  }, [currentTimeStr, durationStr, timeRemainingStr, isLiveContent]);

  return {
    currentTimeStr,
    durationStr,
    timeRemainingStr,
    progressPercentage,
    bufferedPercentageStr,
    playPauseLabel,
    isLiveContent,
    fullTimeDisplay,
    fullTimeWithRemaining,
  };
}

/**
 * Standalone utility function to format seconds to time string
 * Can be used outside of React hooks
 *
 * Usage:
 * ```tsx
 * import { formatSecondToTime } from '@/hooks/usePlayerDisplay';
 *
 * const timeStr = formatSecondToTime(125);  // "2:05"
 * ```
 */
export function formatSecondToTime(seconds: number, showHours = false): string {
  return formatTime(seconds, showHours);
}

/**
 * Calculate progress percentage
 * Can be used outside of React hooks
 */
export function calculateProgressPercentage(
  currentTime: number,
  duration: number
): number {
  if (!Number.isFinite(duration) || duration <= 0) {
    return 0;
  }
  const percentage = (currentTime / duration) * 100;
  return Math.min(Math.max(percentage, 0), 100);
}

/**
 * Format buffered percentage for display
 * Can be used outside of React hooks
 */
export function formatBufferedPercentage(bufferedPercentage: number): string {
  const clamped = Math.min(Math.max(bufferedPercentage, 0), 100);
  return `${Math.round(clamped)}%`;
}

export default usePlayerDisplay;
