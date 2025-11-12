/**
 * Time Formatting Utilities
 *
 * Shared time formatting functions used across components
 * to ensure consistent time display across the application.
 */

/**
 * Format seconds to MM:SS format
 * @param seconds Number of seconds
 * @returns Formatted string like "3:45"
 * @example formatTime(225) // "3:45"
 */
export function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) {
    return '0:00';
  }

  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format seconds to HH:MM:SS format
 * @param seconds Number of seconds
 * @returns Formatted string like "1:23:45"
 * @example formatDuration(5025) // "1:23:45"
 */
export function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) {
    return '0:00:00';
  }

  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format seconds to a human-readable duration
 * @param seconds Number of seconds
 * @returns Formatted string like "1h 23m", "23m 45s", or "45s"
 * @example formatHumanDuration(5025) // "1h 23m"
 */
export function formatHumanDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) {
    return '0s';
  }

  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (mins > 0) parts.push(`${mins}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);

  return parts.slice(0, 2).join(' '); // Only show first 2 units
}

/**
 * Get percentage of progress through a track
 * @param current Current time in seconds
 * @param total Total duration in seconds
 * @returns Percentage as 0-100
 * @example getProgress(30, 120) // 25
 */
export function getProgress(current: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, (current / total) * 100);
}
