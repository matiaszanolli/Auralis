/**
 * Path Basename Utility
 *
 * The backend sends absolute server paths verbatim, and the desktop build
 * targets Windows as well as POSIX, so a path may use either separator.
 */

/**
 * Last non-empty segment of a POSIX or Windows path.
 * @example pathBasename('C:\\Users\\me\\song.mp3') // "song.mp3"
 * @example pathBasename('/music/album/') // "album"
 */
export function pathBasename(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}
