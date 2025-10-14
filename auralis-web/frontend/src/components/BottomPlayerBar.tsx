import React, { useState } from 'react';
import {
  Box,
  IconButton,
  Slider,
  Typography,
  Switch,
  Tooltip
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
      <Box
        sx={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: 90,
          background: 'var(--charcoal)',
          borderTop: '1px solid rgba(226, 232, 240, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}
      >
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'var(--font-body)',
            color: 'var(--silver)',
            opacity: 0.5
          }}
        >
          No track playing
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: 90,
        background: 'var(--charcoal)',
        borderTop: '1px solid rgba(226, 232, 240, 0.1)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 1000
      }}
    >
      {/* Progress Bar */}
      <Slider
        value={currentTime}
        max={currentTrack.duration}
        onChange={(_, value) => setCurrentTime(value as number)}
        sx={{
          height: 4,
          padding: 0,
          '& .MuiSlider-track': {
            background: 'var(--aurora-horizontal)',
            border: 'none'
          },
          '& .MuiSlider-rail': {
            background: 'rgba(226, 232, 240, 0.2)'
          },
          '& .MuiSlider-thumb': {
            width: 12,
            height: 12,
            background: 'var(--aurora-violet)',
            '&:hover': {
              boxShadow: 'var(--glow-medium)'
            },
            '&.Mui-active': {
              boxShadow: 'var(--glow-medium)'
            }
          }
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
          <Box
            component="img"
            src={currentTrack.albumArt || '/placeholder-album.jpg'}
            alt={currentTrack.album}
            sx={{
              width: 56,
              height: 56,
              borderRadius: 'var(--radius-sm)',
              flexShrink: 0
            }}
          />

          {/* Track Details */}
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography
              variant="body2"
              sx={{
                fontFamily: 'var(--font-body)',
                fontWeight: 500,
                color: 'var(--silver)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}
            >
              {currentTrack.title}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--silver)',
                opacity: 0.7,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                display: 'block'
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
              color: isLoved ? '#F472B6' : 'var(--silver)',
              '&:hover': {
                color: '#F472B6'
              }
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
                color: 'var(--silver)',
                '&:hover': {
                  color: 'white'
                }
              }}
            >
              <SkipPrevious />
            </IconButton>

            <IconButton
              onClick={onPlayPause}
              sx={{
                background: 'var(--aurora-gradient)',
                color: 'white',
                width: 40,
                height: 40,
                '&:hover': {
                  transform: 'scale(1.05)',
                  boxShadow: 'var(--glow-medium)'
                }
              }}
            >
              {isPlaying ? <Pause /> : <PlayArrow />}
            </IconButton>

            <IconButton
              onClick={onNext}
              sx={{
                color: 'var(--silver)',
                '&:hover': {
                  color: 'white'
                }
              }}
            >
              <SkipNext />
            </IconButton>
          </Box>

          {/* Time Display */}
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--silver)',
                opacity: 0.7,
                fontSize: 11
              }}
            >
              {formatTime(currentTime)}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--silver)',
                opacity: 0.5,
                fontSize: 11
              }}
            >
              /
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--silver)',
                opacity: 0.7,
                fontSize: 11
              }}
            >
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
                  color: isEnhanced ? 'var(--aurora-violet)' : 'var(--silver)',
                  opacity: isEnhanced ? 1 : 0.5
                }}
              />
              <Switch
                size="small"
                checked={isEnhanced}
                onChange={handleEnhancementToggle}
                sx={{
                  '& .MuiSwitch-switchBase.Mui-checked': {
                    color: 'var(--aurora-violet)'
                  },
                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                    backgroundColor: 'var(--aurora-violet)'
                  }
                }}
              />
            </Box>
          </Tooltip>

          {/* Volume Control */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120 }}>
            <IconButton
              size="small"
              onClick={handleMuteToggle}
              sx={{
                color: 'var(--silver)',
                '&:hover': {
                  color: 'white'
                }
              }}
            >
              {isMuted || volume === 0 ? <VolumeOff fontSize="small" /> : <VolumeUp fontSize="small" />}
            </IconButton>
            <Slider
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              sx={{
                maxWidth: 100,
                '& .MuiSlider-track': {
                  background: 'rgba(226, 232, 240, 0.5)'
                },
                '& .MuiSlider-rail': {
                  background: 'rgba(226, 232, 240, 0.2)'
                },
                '& .MuiSlider-thumb': {
                  width: 10,
                  height: 10,
                  background: 'var(--silver)',
                  '&:hover': {
                    boxShadow: '0 0 8px rgba(226, 232, 240, 0.5)'
                  }
                }
              }}
            />
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default BottomPlayerBar;
