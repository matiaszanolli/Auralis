import React from 'react';
import { Box, IconButton, Typography } from '@mui/material';
import { Close as CloseIcon, MusicNote as MusicNoteIcon } from '@mui/icons-material';
import { tokens } from '../../../design-system/tokens';
import { usePlayerAPI } from '../../../hooks/usePlayerAPI';
import { PanelContainer, Header, LyricsContainer } from './LyricsPanel.styles';
import LyricsLoadingState from './LyricsLoadingState';
import LyricsEmptyState from './LyricsEmptyState';
import LyricsContent from './LyricsContent';
import { useLyricsFetch } from './useLyricsFetch';
import { useLRCParser } from './useLRCParser';
import { useActiveLineTracking } from './useActiveLineTracking';

interface LyricsPanelProps {
  trackId: number | null;
  onClose: () => void;
}

export const LyricsPanel: React.FC<LyricsPanelProps> = ({ trackId, onClose }) => {
  // Get current playback time from player API
  const { currentTime = 0 } = usePlayerAPI();

  // Fetch lyrics from backend
  const { lyrics, format, loading } = useLyricsFetch(trackId);

  // Parse LRC format lyrics
  const parsedLyrics = useLRCParser(format === 'lrc' ? lyrics : null);

  // Track and auto-scroll to active line
  const { activeLine, lyricsContainerRef, activeLineRef } = useActiveLineTracking(
    parsedLyrics,
    currentTime
  );

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
        {loading && <LyricsLoadingState />}

        {!loading && !lyrics && <LyricsEmptyState />}

        {!loading && lyrics && (
          <LyricsContent
            lyrics={lyrics}
            format={format}
            parsedLyrics={parsedLyrics}
            activeLine={activeLine}
            activeLineRef={activeLineRef}
          />
        )}
      </LyricsContainer>
    </PanelContainer>
  );
};

export default LyricsPanel;
