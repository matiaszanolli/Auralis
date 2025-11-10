/**
 * VolumeControl - Volume slider with mute toggle
 *
 * Features:
 * - Horizontal slider with visual feedback
 * - Mute/unmute icon toggle
 * - Smooth transitions
 * - Design token styling
 */

import React, { useState, useCallback } from 'react';
import { Box, IconButton, Slider, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import VolumeDownIcon from '@mui/icons-material/VolumeDown';
import VolumeMuteIcon from '@mui/icons-material/VolumeMute';
import VolumeOffIcon from '@mui/icons-material/VolumeOff';

interface VolumeControlProps {
  volume: number; // 0.0 to 1.0
  onChange: (volume: number) => void;
}

const VolumeContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
  minWidth: '150px',
});

const VolumeButton = styled(IconButton)({
  color: tokens.colors.text.primary,
  transition: tokens.transitions.all,

  '&:hover': {
    transform: 'scale(1.1)',
    backgroundColor: tokens.colors.bg.elevated,
  },

  '& .MuiSvgIcon-root': {
    fontSize: '22px',
  },
});

const VolumeSlider = styled(Slider)({
  color: tokens.colors.accent.primary,
  height: 4,
  width: '100px',

  '& .MuiSlider-track': {
    border: 'none',
    background: tokens.gradients.auroraSoft,
    height: 4,
  },

  '& .MuiSlider-rail': {
    backgroundColor: tokens.colors.bg.elevated,
    opacity: 1,
    height: 4,
  },

  '& .MuiSlider-thumb': {
    height: 12,
    width: 12,
    backgroundColor: tokens.colors.text.primary,
    border: `2px solid ${tokens.colors.accent.primary}`,
    transition: tokens.transitions.all,

    '&:hover, &.Mui-focusVisible': {
      boxShadow: tokens.shadows.glow,
      transform: 'scale(1.3)',
    },

    '&.Mui-active': {
      boxShadow: tokens.shadows.glowStrong,
    },
  },
});

/**
 * Get appropriate volume icon based on volume level
 */
function getVolumeIcon(volume: number, isMuted: boolean): React.ReactElement {
  if (isMuted || volume === 0) {
    return <VolumeOffIcon />;
  } else if (volume < 0.3) {
    return <VolumeMuteIcon />;
  } else if (volume < 0.7) {
    return <VolumeDownIcon />;
  } else {
    return <VolumeUpIcon />;
  }
}

export const VolumeControl: React.FC<VolumeControlProps> = React.memo(({
  volume,
  onChange,
}) => {
  const [isMuted, setIsMuted] = useState(false);
  const [previousVolume, setPreviousVolume] = useState(volume);

  // Handle volume slider change
  const handleVolumeChange = useCallback((event: Event, value: number | number[]) => {
    const newVolume = Array.isArray(value) ? value[0] : value;
    onChange(newVolume);

    if (newVolume > 0 && isMuted) {
      setIsMuted(false);
    }
  }, [onChange, isMuted]);

  // Handle mute/unmute toggle
  const handleMuteToggle = useCallback(() => {
    if (isMuted) {
      // Unmute: restore previous volume
      onChange(previousVolume > 0 ? previousVolume : 0.5);
      setIsMuted(false);
    } else {
      // Mute: save current volume and set to 0
      setPreviousVolume(volume);
      onChange(0);
      setIsMuted(true);
    }
  }, [isMuted, volume, previousVolume, onChange]);

  return (
    <VolumeContainer>
      <VolumeButton
        onClick={handleMuteToggle}
        aria-label={isMuted ? 'Unmute' : 'Mute'}
        title={isMuted ? 'Unmute (M)' : 'Mute (M)'}
      >
        {getVolumeIcon(volume, isMuted)}
      </VolumeButton>

      <VolumeSlider
        value={volume}
        min={0}
        max={1}
        step={0.01}
        onChange={handleVolumeChange}
        aria-label="Volume"
      />
    </VolumeContainer>
  );
});

VolumeControl.displayName = 'VolumeControl';
