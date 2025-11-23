import React, { useRef, useEffect } from 'react';
import { Box } from '@mui/material';
import { LyricLine } from './LyricsPanel.styles';
import { LRCLine } from './useLRCParser';

interface LyricsContentProps {
  lyrics: string | null;
  format: 'plain' | 'lrc' | null;
  parsedLyrics: LRCLine[];
  activeLine: number;
  activeLineRef: React.RefObject<HTMLDivElement>;
}

/**
 * LyricsContent - Renders lyrics in appropriate format
 *
 * Handles:
 * - LRC synchronized lyrics rendering
 * - Plain text lyrics rendering
 * - Active line highlighting
 */
export const LyricsContent: React.FC<LyricsContentProps> = ({
  lyrics,
  format,
  parsedLyrics,
  activeLine,
  activeLineRef,
}) => {
  // LRC Format (synchronized)
  if (format === 'lrc' && parsedLyrics.length > 0) {
    return (
      <Box>
        {parsedLyrics.map((line, index) => (
          <LyricLine
            key={index}
            ref={index === activeLine ? activeLineRef : null}
            isactive={index === activeLine ? 'true' : 'false'}
            ispast={index < activeLine ? 'true' : 'false'}
          >
            {line.text}
          </LyricLine>
        ))}
      </Box>
    );
  }

  // Plain Text Format
  if (format === 'plain' && lyrics) {
    return (
      <Box>
        {lyrics.split('\n').map((line, index) => (
          <LyricLine key={index} isactive="false" ispast="false">
            {line}
          </LyricLine>
        ))}
      </Box>
    );
  }

  return null;
};

export default LyricsContent;
