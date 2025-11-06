/**
 * ProgressBar - Audio Playback Progress Bar
 *
 * Displays track progress with seek functionality and time display.
 *
 * Features:
 * - Gradient progress slider
 * - Click/drag to seek
 * - Current time and duration display
 * - Responsive design
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { Slider } from '@mui/material';

export interface ProgressBarProps {
  // Time state
  currentTime: number;
  duration: number;

  // Callbacks
  onSeek: (time: number) => void;

  // Optional customization
  showTime?: boolean;
  height?: number;
}

/**
 * Format time in MM:SS format
 */
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Progress Bar Component
 *
 * Displays playback progress with gradient slider and time display.
 */
export const ProgressBar: React.FC<ProgressBarProps> = ({
  currentTime,
  duration,
  onSeek,
  showTime = true,
  height = 4
}) => {

  // Handle slider change
  const handleSeek = (_: Event, value: number | number[]) => {
    const newTime = value as number;
    onSeek(newTime);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
      }}
    >
      {/* Progress slider */}
      <Slider variant="gradient"
        value={currentTime}
        max={duration || 0}
        onChange={handleSeek}
        sx={{
          height: height,
          padding: 0,
          borderRadius: 0,
          '& .MuiSlider-thumb': {
            width: 12,
            height: 12,
            transition: 'width 0.2s ease, height 0.2s ease',
            '&:hover': {
              width: 14,
              height: 14,
            },
          },
          '& .MuiSlider-track': {
            border: 'none',
          },
          '& .MuiSlider-rail': {
            opacity: 0.3,
          },
        }}
      />

      {/* Time display (optional) */}
      {showTime && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            gap: 1,
            mt: 0.5,
          }}
        >
          <Typography
            variant="caption"
            sx={{
              color: '#8b92b0',
              fontSize: 12,
            }}
          >
            {formatTime(currentTime)}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: '#5a5f7a',
              fontSize: 12,
            }}
          >
            /
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: '#8b92b0',
              fontSize: 12,
            }}
          >
            {formatTime(duration)}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default ProgressBar;
