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
    return '0:00';
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
 * Format seconds to a compact human-readable duration, keeping the two most
 * significant units: "Xh Ym" from an hour up, "Xm Ys" from a minute up, else "Xs".
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

  if (hours > 0) return `${hours}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

/**
 * Format seconds as hours and minutes only (no seconds), for totals such as a
 * queue or album length.
 * @param seconds Number of seconds
 * @param style 'short' -> "1h 10m" / "3m"; 'long' -> "1 hr 10 min" / "3 min"
 * @example formatHoursMinutes(4200) // "1h 10m"
 * @example formatHoursMinutes(4200, 'long') // "1 hr 10 min"
 */
export function formatHoursMinutes(seconds: number, style: 'short' | 'long' = 'short'): string {
  const safe = isFinite(seconds) && seconds > 0 ? seconds : 0;
  const hours = Math.floor(safe / 3600);
  const mins = Math.floor((safe % 3600) / 60);
  const [h, m] = style === 'long' ? [' hr', ' min'] : ['h', 'm'];
  return hours > 0 ? `${hours}${h} ${mins}${m}` : `${mins}${m}`;
}
