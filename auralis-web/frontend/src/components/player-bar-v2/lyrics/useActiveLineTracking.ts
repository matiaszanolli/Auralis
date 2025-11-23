import { useState, useEffect, useRef } from 'react';
import { LRCLine } from './useLRCParser';

/**
 * useActiveLineTracking - Tracks and auto-scrolls to active lyric line
 *
 * Handles:
 * - Finding active line based on current time
 * - Auto-scrolling to center active line
 * - Smooth scroll animation
 */
export const useActiveLineTracking = (
  parsedLyrics: LRCLine[],
  currentTime: number
) => {
  const [activeLine, setActiveLine] = useState(-1);
  const lyricsContainerRef = useRef<HTMLDivElement>(null);
  const activeLineRef = useRef<HTMLDivElement>(null);

  // Update active line based on current time
  useEffect(() => {
    if (parsedLyrics.length === 0) return;

    // Find the current line
    let currentLine = -1;
    for (let i = parsedLyrics.length - 1; i >= 0; i--) {
      if (currentTime >= parsedLyrics[i].time) {
        currentLine = i;
        break;
      }
    }

    setActiveLine(currentLine);
  }, [currentTime, parsedLyrics]);

  // Auto-scroll to active line
  useEffect(() => {
    if (activeLineRef.current && lyricsContainerRef.current) {
      const container = lyricsContainerRef.current;
      const activeLine = activeLineRef.current;

      const containerHeight = container.clientHeight;
      const lineOffsetTop = activeLine.offsetTop;
      const lineHeight = activeLine.clientHeight;

      // Scroll to center the active line
      const scrollTo = lineOffsetTop - containerHeight / 2 + lineHeight / 2;
      container.scrollTo({
        top: scrollTo,
        behavior: 'smooth',
      });
    }
  }, [activeLine]);

  return {
    activeLine,
    lyricsContainerRef,
    activeLineRef,
  };
};
