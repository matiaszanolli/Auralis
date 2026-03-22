/**
 * useDurationFormatter - Custom hook for formatting duration to MM:SS format
 */

import { formatDuration } from '@/utils/timeFormat';

export const useDurationFormatter = () => {
  return { formatDuration };
};

export default useDurationFormatter;
