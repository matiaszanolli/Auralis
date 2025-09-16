import React, { useState } from 'react';
import {
  Box,
  Paper,
  IconButton,
  Typography,
  Slider,
  LinearProgress,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  SkipNext as NextIcon,
  SkipPrevious as PrevIcon,
  VolumeUp as VolumeIcon,
  VolumeOff as VolumeOffIcon,
} from '@mui/icons-material';

interface AudioPlayerProps {
  currentTrack?: {
    id: number;
    title: string;
    artist?: string;
    duration?: number;
  };
}

const AudioPlayer: React.FC<AudioPlayerProps> = ({ currentTrack }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(80);
  const [isMuted, setIsMuted] = useState(false);

  const duration = currentTrack?.duration || 180; // Default 3 minutes for demo

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
    // TODO: Implement actual audio playback
  };

  const handleTimeChange = (value: number | number[]) => {
    const newTime = Array.isArray(value) ? value[0] : value;
    setCurrentTime(newTime);
    // TODO: Seek to new time
  };

  const handleVolumeChange = (value: number | number[]) => {
    const newVolume = Array.isArray(value) ? value[0] : value;
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
    // TODO: Set actual volume
  };

  const handleMuteToggle = () => {
    setIsMuted(!isMuted);
    // TODO: Implement mute/unmute
  };

  if (!currentTrack) {
    return (
      <Paper
        elevation={3}
        sx={{
          p: 2,
          backgroundColor: 'background.paper',
          borderTop: 1,
          borderColor: 'divider',
        }}
      >
        <Box display="flex" alignItems="center" justifyContent="center">
          <Typography variant="body2" color="text.secondary">
            Select a track to start playing
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper
      elevation={3}
      sx={{
        p: 2,
        backgroundColor: 'background.paper',
        borderTop: 1,
        borderColor: 'divider',
      }}
    >
      <Box display="flex" alignItems="center" gap={2}>
        {/* Track Info */}
        <Box sx={{ minWidth: 200, maxWidth: 300 }}>
          <Typography variant="subtitle2" noWrap>
            {currentTrack.title}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            {currentTrack.artist || 'Unknown Artist'}
          </Typography>
        </Box>

        {/* Playback Controls */}
        <Box display="flex" alignItems="center" gap={1}>
          <IconButton color="primary">
            <PrevIcon />
          </IconButton>
          <IconButton
            color="primary"
            onClick={handlePlayPause}
            sx={{
              backgroundColor: 'primary.main',
              color: 'primary.contrastText',
              '&:hover': {
                backgroundColor: 'primary.dark',
              },
            }}
          >
            {isPlaying ? <PauseIcon /> : <PlayIcon />}
          </IconButton>
          <IconButton color="primary">
            <NextIcon />
          </IconButton>
        </Box>

        {/* Progress Bar */}
        <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" sx={{ minWidth: '3em' }}>
            {formatTime(currentTime)}
          </Typography>
          <Slider
            value={currentTime}
            max={duration}
            onChange={(_, value) => handleTimeChange(value)}
            sx={{
              flexGrow: 1,
              '& .MuiSlider-thumb': {
                width: 12,
                height: 12,
              },
            }}
          />
          <Typography variant="caption" sx={{ minWidth: '3em' }}>
            {formatTime(duration)}
          </Typography>
        </Box>

        {/* Volume Control */}
        <Box display="flex" alignItems="center" gap={1} sx={{ minWidth: 120 }}>
          <IconButton size="small" onClick={handleMuteToggle}>
            {isMuted || volume === 0 ? <VolumeOffIcon /> : <VolumeIcon />}
          </IconButton>
          <Slider
            value={isMuted ? 0 : volume}
            max={100}
            onChange={(_, value) => handleVolumeChange(value)}
            sx={{
              width: 80,
              '& .MuiSlider-thumb': {
                width: 12,
                height: 12,
              },
            }}
          />
        </Box>
      </Box>

      {/* Loading progress (when buffering) */}
      {isPlaying && (
        <LinearProgress
          variant="indeterminate"
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 2,
            opacity: 0.3,
          }}
        />
      )}
    </Paper>
  );
};

export default AudioPlayer;