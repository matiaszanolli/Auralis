/**
 * PlayerControls - Player Control Buttons
 *
 * Displays play/pause, skip, volume, and enhancement controls.
 *
 * Features:
 * - Play/pause button with aurora gradient
 * - Skip previous/next buttons
 * - Volume slider with mouse wheel support
 * - Mute/unmute button
 * - Enhancement toggle switch
 */

import React from 'react';
import {
  Box,
  IconButton,
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
  VolumeDown,
  VolumeMute,
  AutoAwesome
} from '@mui/icons-material';
import { Slider } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';

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

export interface PlayerControlsProps {
  // Playback state
  isPlaying: boolean;
  volume: number;
  isMuted: boolean;
  loading?: boolean;

  // Enhancement state
  enhancementEnabled: boolean;
  enhancementPreset?: string;
  isProcessing?: boolean;

  // Callbacks
  onPlayPause: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onVolumeChange: (volume: number) => void;
  onMuteToggle: () => void;
  onEnhancementToggle: (enabled: boolean) => void;

  // Optional customization
  showEnhancementToggle?: boolean;
}

/**
 * Player Controls Component
 *
 * Renders playback controls with gradient play button and volume slider.
 */
export const PlayerControls: React.FC<PlayerControlsProps> = ({
  isPlaying,
  volume,
  isMuted,
  loading = false,
  enhancementEnabled,
  enhancementPreset = 'adaptive',
  isProcessing = false,
  onPlayPause,
  onNext,
  onPrevious,
  onVolumeChange,
  onMuteToggle,
  onEnhancementToggle,
  showEnhancementToggle = true
}) => {

  // Get volume icon based on current volume level
  const getVolumeIcon = () => {
    if (isMuted || volume === 0) return <VolumeMute />;
    if (volume < 30) return <VolumeDown />;
    return <VolumeUp />;
  };

  // Handle volume slider change
  const handleVolumeChange = (_: Event, value: number | number[]) => {
    onVolumeChange(value as number);
  };

  // Handle mouse wheel on volume slider
  const handleVolumeWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -5 : 5; // Scroll down = decrease, scroll up = increase
    const newVolume = Math.max(0, Math.min(100, volume + delta));
    onVolumeChange(newVolume);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        flex: 1,
        maxWidth: '800px',
        margin: '0 auto',
      }}
    >
      {/* Previous button */}
      <Tooltip title="Previous (Shift+←)" arrow>
        <IconButton
          onClick={onPrevious}
          sx={{
            color: '#ffffff',
            '&:hover': {
              color: '#667eea',
              transform: 'scale(1.1)',
            },
            transition: 'all 0.2s ease',
          }}
        >
          <SkipPrevious />
        </IconButton>
      </Tooltip>

      {/* Play/Pause button */}
      <Tooltip title={isPlaying ? "Pause (Space)" : "Play (Space)"} arrow>
        <span>
          <PlayButton
            onClick={onPlayPause}
            disabled={loading}
            sx={{
              opacity: loading ? 0.5 : 1,
            }}
          >
            {isPlaying ? <Pause /> : <PlayArrow />}
          </PlayButton>
        </span>
      </Tooltip>

      {/* Next button */}
      <Tooltip title="Next (Shift+→)" arrow>
        <IconButton
          onClick={onNext}
          sx={{
            color: '#ffffff',
            '&:hover': {
              color: '#667eea',
              transform: 'scale(1.1)',
            },
            transition: 'all 0.2s ease',
          }}
        >
          <SkipNext />
        </IconButton>
      </Tooltip>

      {/* Volume control section */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          ml: 2,
          minWidth: '160px',
        }}
      >
        {/* Mute/unmute button */}
        <Tooltip title={isMuted ? "Unmute (M)" : "Mute (M)"} arrow>
          <IconButton
            onClick={onMuteToggle}
            size="small"
            sx={{
              color: '#ffffff',
              '&:hover': {
                color: '#667eea',
              },
            }}
          >
            {getVolumeIcon()}
          </IconButton>
        </Tooltip>

        {/* Volume slider */}
        <Slider variant="gradient"
          value={isMuted ? 0 : volume}
          onChange={handleVolumeChange}
          onWheel={handleVolumeWheel}
          min={0}
          max={100}
          aria-label="Volume"
          sx={{
            width: '120px',
            cursor: 'pointer',
          }}
        />
      </Box>

      {/* Enhancement toggle */}
      {showEnhancementToggle && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            ml: 2,
          }}
        >
          <Tooltip
            title={
              isProcessing
                ? 'Processing...'
                : enhancementEnabled
                ? `Auralis Magic ON (${enhancementPreset})`
                : 'Auralis Magic OFF'
            }
            arrow
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AutoAwesome
                sx={{
                  color: enhancementEnabled ? '#667eea' : '#8b92b0',
                  fontSize: '20px',
                }}
              />
              <Switch
                checked={enhancementEnabled}
                onChange={(e) => onEnhancementToggle(e.target.checked)}
                disabled={isProcessing}
                sx={{
                  '& .MuiSwitch-switchBase.Mui-checked': {
                    color: '#667eea',
                  },
                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                    backgroundColor: '#667eea',
                  },
                }}
              />
            </Box>
          </Tooltip>
        </Box>
      )}
    </Box>
  );
};

export default PlayerControls;
