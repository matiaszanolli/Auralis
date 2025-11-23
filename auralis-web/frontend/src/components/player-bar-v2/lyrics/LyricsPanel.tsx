import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  IconButton,
  CircularProgress,
  styled
} from '@mui/material';
import {
  Close as CloseIcon,
  MusicNote as MusicNoteIcon
} from '@mui/icons-material';
import { colors, gradients } from '../../../theme/auralisTheme';
import { usePlayerAPI } from '../../../hooks/usePlayerAPI';
import { auroraOpacity } from '../../library/Color.styles';
import { tokens } from '../../../design-system/tokens';

interface LyricsPanelProps {
  trackId: number | null;
  onClose: () => void;
}

interface LRCLine {
  time: number;
  text: string;
}

const PanelContainer = styled(Box)({
  width: '320px',
  height: '100%',
  background: colors.background.secondary,
  borderLeft: `1px solid ${auroraOpacity.veryLight}`,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
});

const Header = styled(Box)({
  padding: '16px 20px',
  borderBottom: `1px solid ${auroraOpacity.veryLight}`,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  background: auroraOpacity.minimal,
});

const LyricsContainer = styled(Box)({
  flex: 1,
  overflowY: 'auto',
  padding: '24px 20px',
  position: 'relative',

  '&::-webkit-scrollbar': {
    width: '8px',
  },
  '&::-webkit-scrollbar-track': {
    background: '#0A0E27',
  },
  '&::-webkit-scrollbar-thumb': {
    background: auroraOpacity.strong,
    borderRadius: '4px',
    '&:hover': {
      background: auroraOpacity.stronger,
    },
  },
});

const LyricLine = styled(Typography)<{ isactive?: string; ispast?: string }>(({ isactive, ispast }) => ({
  fontSize: '16px',
  lineHeight: '2',
  marginBottom: '12px',
  transition: 'all 0.3s ease',
  color: isactive === 'true'
    ? '#ffffff'
    : ispast === 'true'
      ? colors.text.secondary
      : colors.text.disabled,
  fontWeight: isactive === 'true' ? 600 : 400,
  transform: isactive === 'true' ? 'scale(1.05)' : 'scale(1)',
  opacity: isactive === 'true' ? 1 : ispast === 'true' ? 0.7 : 0.5,
  ...(isactive === 'true' && {
    background: gradients.aurora,
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  }),
}));

const EmptyState = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  padding: '40px 20px',
  textAlign: 'center',
});

export const LyricsPanel: React.FC<LyricsPanelProps> = ({ trackId, onClose }) => {
  const [lyrics, setLyrics] = useState<string | null>(null);
  const [format, setFormat] = useState<'plain' | 'lrc' | null>(null);
  const [loading, setLoading] = useState(false);
  const [parsedLyrics, setParsedLyrics] = useState<LRCLine[]>([]);
  const [activeLine, setActiveLine] = useState(-1);
  const lyricsContainerRef = useRef<HTMLDivElement>(null);
  const activeLineRef = useRef<HTMLDivElement>(null);

  // Get current playback time from player API
  const { currentTime = 0 } = usePlayerAPI();

  // Fetch lyrics when track changes
  useEffect(() => {
    if (!trackId) {
      setLyrics(null);
      return;
    }

    const fetchLyrics = async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/library/tracks/${trackId}/lyrics`);
        if (response.ok) {
          const data = await response.json();
          setLyrics(data.lyrics);
          setFormat(data.format);

          // Parse LRC format if applicable
          if (data.format === 'lrc' && data.lyrics) {
            setParsedLyrics(parseLRC(data.lyrics));
          } else {
            setParsedLyrics([]);
          }
        }
      } catch (error) {
        console.error('Failed to fetch lyrics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchLyrics();
  }, [trackId]);

  // Parse LRC format lyrics
  const parseLRC = (lrcText: string): LRCLine[] => {
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
  };

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
        behavior: 'smooth'
      });
    }
  }, [activeLine]);

  return (
    <PanelContainer>
      <Header>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <MusicNoteIcon sx={{ color: tokens.colors.accent.purple, fontSize: 20 }} />
          <Typography variant="h6" sx={{ fontSize: '16px', fontWeight: 600 }}>
            Lyrics
          </Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseIcon fontSize="small" />
        </IconButton>
      </Header>

      <LyricsContainer ref={lyricsContainerRef}>
        {loading && (
          <EmptyState>
            <CircularProgress size={40} sx={{ color: tokens.colors.accent.purple }} />
            <Typography sx={{ mt: 2, color: colors.text.secondary }}>
              Loading lyrics...
            </Typography>
          </EmptyState>
        )}

        {!loading && !lyrics && (
          <EmptyState>
            <MusicNoteIcon sx={{ fontSize: 64, color: colors.text.disabled, mb: 2 }} />
            <Typography variant="h6" sx={{ color: colors.text.primary, mb: 1 }}>
              No Lyrics Available
            </Typography>
            <Typography sx={{ color: colors.text.secondary, fontSize: '14px' }}>
              This track doesn't have embedded lyrics
            </Typography>
          </EmptyState>
        )}

        {!loading && lyrics && format === 'lrc' && parsedLyrics.length > 0 && (
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
        )}

        {!loading && lyrics && format === 'plain' && (
          <Box>
            {lyrics.split('\n').map((line, index) => (
              <LyricLine key={index} isactive="false" ispast="false">
                {line}
              </LyricLine>
            ))}
          </Box>
        )}
      </LyricsContainer>
    </PanelContainer>
  );
};

export default LyricsPanel;
