import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Chip,
  Divider,
  IconButton,
  styled,
} from '@mui/material';
import {
  Close,
  MusicNote,
  Person,
  Album as AlbumIcon,
  AccessTime,
  CalendarToday,
  QueueMusic,
  Star,
  Info,
} from '@mui/icons-material';
import { colors, gradients } from '../../theme/auralisTheme';
import GradientButton from '../shared/GradientButton';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  quality?: number;
  genre?: string;
  year?: number;
  bitrate?: number;
  sampleRate?: number;
  fileFormat?: string;
  fileSize?: number;
}

interface TrackInfoModalProps {
  open: boolean;
  track: Track | null;
  onClose: () => void;
  onPlay?: (track: Track) => void;
  onAddToQueue?: (track: Track) => void;
}

const StyledDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    background: colors.background.secondary,
    backgroundImage: 'none',
    borderRadius: '16px',
    border: `1px solid rgba(102, 126, 234, 0.2)`,
    boxShadow: '0 12px 48px rgba(0, 0, 0, 0.6)',
    minWidth: '500px',
    maxWidth: '600px',
  },
}));

const AlbumArtContainer = styled(Box)({
  width: '200px',
  height: '200px',
  borderRadius: '12px',
  overflow: 'hidden',
  flexShrink: 0,
  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
  background: gradients.aurora,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',

  '& img': {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
});

const InfoRow = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '12px 0',
  borderBottom: `1px solid rgba(102, 126, 234, 0.1)`,

  '&:last-child': {
    borderBottom: 'none',
  },
});

const InfoLabel = styled(Typography)({
  fontSize: '13px',
  fontWeight: 600,
  color: colors.text.secondary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  minWidth: '120px',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
});

const InfoValue = styled(Typography)({
  fontSize: '14px',
  fontWeight: 500,
  color: colors.text.primary,
  flex: 1,
});

export const TrackInfoModal: React.FC<TrackInfoModalProps> = ({
  open,
  track,
  onClose,
  onPlay,
  onAddToQueue,
}) => {
  if (!track) return null;

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'Unknown';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  const formatBitrate = (bitrate?: number): string => {
    if (!bitrate) return 'Unknown';
    return `${Math.round(bitrate / 1000)} kbps`;
  };

  return (
    <StyledDialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pr: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Info sx={{ color: '#667eea', fontSize: 24 }} />
            <Typography variant="h6" sx={{ fontWeight: 600, color: colors.text.primary }}>
              Track Information
            </Typography>
          </Box>
          <IconButton
            onClick={onClose}
            size="small"
            sx={{
              color: colors.text.secondary,
              '&:hover': {
                color: colors.text.primary,
                background: 'rgba(102, 126, 234, 0.1)',
              },
            }}
          >
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: 'flex', gap: 3, mb: 3 }}>
          <AlbumArtContainer>
            {track.albumArt ? (
              <img src={track.albumArt} alt={track.album} />
            ) : (
              <MusicNote sx={{ fontSize: 64, color: 'rgba(255, 255, 255, 0.3)' }} />
            )}
          </AlbumArtContainer>

          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Typography variant="h5" sx={{ fontWeight: 700, color: colors.text.primary, mb: 0.5 }}>
              {track.title}
            </Typography>
            <Typography variant="body1" sx={{ color: colors.text.secondary, mb: 1 }}>
              {track.artist}
            </Typography>
            {track.genre && (
              <Chip
                label={track.genre}
                size="small"
                sx={{
                  background: gradients.aurora,
                  color: '#fff',
                  fontWeight: 600,
                  alignSelf: 'flex-start',
                }}
              />
            )}
            {track.quality && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                <Star sx={{ fontSize: 18, color: '#ffa502' }} />
                <Typography variant="body2" sx={{ color: colors.text.secondary }}>
                  Quality: {Math.round(track.quality * 100)}%
                </Typography>
              </Box>
            )}
          </Box>
        </Box>

        <Divider sx={{ borderColor: 'rgba(102, 126, 234, 0.1)', my: 2 }} />

        <Box>
          <Typography
            variant="caption"
            sx={{
              color: colors.text.secondary,
              textTransform: 'uppercase',
              letterSpacing: '1px',
              fontWeight: 600,
              mb: 2,
              display: 'block',
            }}
          >
            Details
          </Typography>

          <InfoRow>
            <InfoLabel>
              <AlbumIcon fontSize="small" />
              Album
            </InfoLabel>
            <InfoValue>{track.album}</InfoValue>
          </InfoRow>

          <InfoRow>
            <InfoLabel>
              <Person fontSize="small" />
              Artist
            </InfoLabel>
            <InfoValue>{track.artist}</InfoValue>
          </InfoRow>

          <InfoRow>
            <InfoLabel>
              <AccessTime fontSize="small" />
              Duration
            </InfoLabel>
            <InfoValue>{formatDuration(track.duration)}</InfoValue>
          </InfoRow>

          {track.year && (
            <InfoRow>
              <InfoLabel>
                <CalendarToday fontSize="small" />
                Year
              </InfoLabel>
              <InfoValue>{track.year}</InfoValue>
            </InfoRow>
          )}

          {track.fileFormat && (
            <InfoRow>
              <InfoLabel>
                <MusicNote fontSize="small" />
                Format
              </InfoLabel>
              <InfoValue>{track.fileFormat.toUpperCase()}</InfoValue>
            </InfoRow>
          )}

          {track.bitrate && (
            <InfoRow>
              <InfoLabel>
                <QueueMusic fontSize="small" />
                Bitrate
              </InfoLabel>
              <InfoValue>{formatBitrate(track.bitrate)}</InfoValue>
            </InfoRow>
          )}

          {track.sampleRate && (
            <InfoRow>
              <InfoLabel>Sample Rate</InfoLabel>
              <InfoValue>{(track.sampleRate / 1000).toFixed(1)} kHz</InfoValue>
            </InfoRow>
          )}

          {track.fileSize && (
            <InfoRow>
              <InfoLabel>File Size</InfoLabel>
              <InfoValue>{formatFileSize(track.fileSize)}</InfoValue>
            </InfoRow>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 3, gap: 1 }}>
        <GradientButton
          onClick={() => {
            onAddToQueue?.(track);
            onClose();
          }}
          sx={{ flex: 1 }}
        >
          Add to Queue
        </GradientButton>
        <GradientButton
          onClick={() => {
            onPlay?.(track);
            onClose();
          }}
          sx={{ flex: 1 }}
        >
          Play Now
        </GradientButton>
      </DialogActions>
    </StyledDialog>
  );
};

export default TrackInfoModal;
