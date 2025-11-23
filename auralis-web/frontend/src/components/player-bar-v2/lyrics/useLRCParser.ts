import { useMemo } from 'react';

export interface LRCLine {
  time: number;
  text: string;
}

/**
 * useLRCParser - Parses and syncs LRC format lyrics
 *
 * Handles:
 * - LRC format parsing ([mm:ss.xx] format)
 * - Active line detection based on current time
 * - Line sorting by time
 */
export const useLRCParser = (lrcText: string | null) => {
  const parsedLyrics = useMemo(() => {
    if (!lrcText) return [];

    const lines: LRCLine[] = [];
    const lrcLines = lrcText.split('\n');

    for (const line of lrcLines) {
      // Match [mm:ss.xx] or [mm:ss] format
      const match = line.match(/\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\](.*)/);
      if (match) {
        const minutes = parseInt(match[1]);
        const seconds = parseInt(match[2]);
        const centiseconds = match[3] ? parseInt(match[3].padEnd(2, '0')) : 0;
        const text = match[4].trim();

        const time = minutes * 60 + seconds + centiseconds / 100;
        lines.push({ time, text });
      }
    }

    return lines.sort((a, b) => a.time - b.time);
  }, [lrcText]);

  return parsedLyrics;
};
