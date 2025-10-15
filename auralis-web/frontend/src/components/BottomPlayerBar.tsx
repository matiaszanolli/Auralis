import React, { useState } from 'react';
import {
  Box,
  IconButton,
  Typography,
  Switch,
  Tooltip,
  styled
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  VolumeUp,
  VolumeOff,
  Favorite,
  FavoriteOutlined,
  AutoAwesome
} from '@mui/icons-material';
import { GradientSlider } from './shared/GradientSlider';
import { colors, gradients } from '../theme/auralisTheme';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  isEnhanced?: boolean;
}

interface BottomPlayerBarProps {
  currentTrack?: Track;
  isPlaying?: boolean;
  onPlayPause?: () => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onEnhancementToggle?: (enabled: boolean) => void;
}

const PlayerContainer = styled(Box)({
  position: 'fixed',
  bottom: 0,
  left: 0,
  right: 0,
  height: '96px',
  background: colors.background.secondary,
  borderTop: `1px solid rgba(102, 126, 234, 0.1)`,
  display: 'flex',
  flexDirection: 'column',
  zIndex: 1000,
  boxShadow: '0 -4px 24px rgba(0, 0, 0, 0.3)',
});

const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  color: '#ffffff',
  width: '48px',
  height: '48px',
  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
  transition: 'all 0.3s ease',

  '&:hover': {
    background: gradients.aurora,
    transform: 'scale(1.1)',
    boxShadow: '0 6px 20px rgba(102, 126, 234, 0.5)',
  },

  '&:active': {
    transform: 'scale(1.05)',
  },
});

const AlbumArt = styled(Box)({
  width: '64px',
  height: '64px',
  borderRadius: '6px',
  flexShrink: 0,
  objectFit: 'cover',
  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
});

const BottomPlayerBar: React.FC<BottomPlayerBarProps> = ({
  currentTrack,
  isPlaying = false,
  onPlayPause,
  onNext,
  onPrevious,
  onEnhancementToggle
}) => {
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(80);
  const [isMuted, setIsMuted] = useState(false);
  const [isLoved, setIsLoved] = useState(false);
  const [isEnhanced, setIsEnhanced] = useState(true);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleEnhancementToggle = () => {
    const newState = !isEnhanced;
    setIsEnhanced(newState);
    onEnhancementToggle?.(newState);
  };

  const handleVolumeChange = (_: Event, value: number | number[]) => {
    const newVolume = value as number;
    setVolume(newVolume);
    if (newVolume > 0 && isMuted) {
      setIsMuted(false);
    }
  };

  const handleMuteToggle = () => {
    setIsMuted(!isMuted);
  };

  if (!currentTrack) {
    return (
      <PlayerContainer>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
          }}
        >
          <Typography variant="body2" sx={{ color: colors.text.secondary, opacity: 0.5 }}>
            No track playing
          </Typography>
        </Box>
      </PlayerContainer>
    );
  }

  return (
    <PlayerContainer>
      {/* Progress Bar */}
      <GradientSlider
        value={currentTime}
        max={currentTrack.duration}
        onChange={(_, value) => setCurrentTime(value as number)}
        sx={{
          height: 4,
          padding: 0,
          borderRadius: 0,
          '& .MuiSlider-thumb': {
            width: 12,
            height: 12,
          },
        }}
      />

      {/* Main Player Controls */}
      <Box
        sx={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '1fr 2fr 1fr',
          alignItems: 'center',
          px: 3,
          gap: 2
        }}
      >
        {/* Left: Track Info */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0 }}>
          {/* Album Art */}
          <AlbumArt
            component="img"
            src={currentTrack.albumArt || '/placeholder-album.jpg'}
            alt={currentTrack.album}
          />

          {/* Track Details */}
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.text.primary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {currentTrack.title}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: colors.text.secondary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                display: 'block',
              }}
            >
              {currentTrack.artist}
            </Typography>
          </Box>

          {/* Love Button */}
          <IconButton
            size="small"
            onClick={() => setIsLoved(!isLoved)}
            sx={{
              color: isLoved ? '#ff6b9d' : colors.text.secondary,
              transition: 'all 0.2s ease',
              '&:hover': {
                color: '#ff6b9d',
                transform: 'scale(1.1)',
              },
            }}
          >
            {isLoved ? <Favorite fontSize="small" /> : <FavoriteOutlined fontSize="small" />}
          </IconButton>
        </Box>

        {/* Center: Playback Controls */}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton
              onClick={onPrevious}
              sx={{
                color: colors.text.secondary,
                transition: 'all 0.2s ease',
                '&:hover': {
                  color: colors.text.primary,
                  transform: 'scale(1.1)',
                },
              }}
            >
              <SkipPrevious />
            </IconButton>

            <PlayButton onClick={onPlayPause}>
              {isPlaying ? <Pause /> : <PlayArrow />}
            </PlayButton>

            <IconButton
              onClick={onNext}
              sx={{
                color: colors.text.secondary,
                transition: 'all 0.2s ease',
                '&:hover': {
                  color: colors.text.primary,
                  transform: 'scale(1.1)',
                },
              }}
            >
              <SkipNext />
            </IconButton>
          </Box>

          {/* Time Display */}
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Typography variant="caption" sx={{ color: colors.text.secondary, fontSize: 12 }}>
              {formatTime(currentTime)}
            </Typography>
            <Typography variant="caption" sx={{ color: colors.text.disabled, fontSize: 12 }}>
              /
            </Typography>
            <Typography variant="caption" sx={{ color: colors.text.secondary, fontSize: 12 }}>
              {formatTime(currentTrack.duration)}
            </Typography>
          </Box>
        </Box>

        {/* Right: Volume & Enhancement */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 2 }}>
          {/* Magic Toggle */}
          <Tooltip title="Auralis Magic" placement="top">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AutoAwesome
                fontSize="small"
                sx={{
                  color: isEnhanced ? '#667eea' : colors.text.secondary,
                  opacity: isEnhanced ? 1 : 0.5,
                  transition: 'all 0.3s ease',
                }}
              />
              <Switch size="small" checked={isEnhanced} onChange={handleEnhancementToggle} />
            </Box>
          </Tooltip>

          {/* Volume Control */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120 }}>
            <IconButton
              size="small"
              onClick={handleMuteToggle}
              sx={{
                color: colors.text.secondary,
                transition: 'all 0.2s ease',
                '&:hover': {
                  color: colors.text.primary,
                  transform: 'scale(1.1)',
                },
              }}
            >
              {isMuted || volume === 0 ? <VolumeOff fontSize="small" /> : <VolumeUp fontSize="small" />}
            </IconButton>
            <GradientSlider
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              sx={{ maxWidth: 100 }}
            />
          </Box>
        </Box>
      </Box>
    </PlayerContainer>
  );
};

export default BottomPlayerBar;
