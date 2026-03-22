import { formatDuration } from '@/utils/timeFormat';

/**
 * useTrackFormatting - Formatting utilities for track display
 *
 * Delegates to shared @/utils/timeFormat utilities.
 */
export const useTrackFormatting = () => {
  return {
    formatDuration,
  };
};
