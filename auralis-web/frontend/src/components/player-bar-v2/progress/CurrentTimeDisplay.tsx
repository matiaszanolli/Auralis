/**
 * CurrentTimeDisplay - Current playback time indicator
 *
 * Responsibility: Display the current playback time with monospace styling
 *
 * Extracted from ProgressBar to:
 * - Make time display testable in isolation
 * - Allow styling/formatting customization
 * - Reuse in other contexts (e.g., mini-player, now-playing info)
 */

import React from 'react';
import { Typography, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { formatTime } from '../../utils/timeFormat';

const TimeDisplayText = styled(Typography)({
  fontFamily: tokens.typography.fontFamily.mono,
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.text.secondary,
  minWidth: '45px',
  textAlign: 'right'
});

interface CurrentTimeDisplayProps {
  currentTime: number;
}

/**
 * CurrentTimeDisplay - Shows formatted current playback time
 *
 * @example
 * <CurrentTimeDisplay currentTime={45.32} />
 * // Renders: "0:45"
 */
export const CurrentTimeDisplay: React.FC<CurrentTimeDisplayProps> = ({ currentTime }) => {
  return <TimeDisplayText>{formatTime(currentTime)}</TimeDisplayText>;
};

CurrentTimeDisplay.displayName = 'CurrentTimeDisplay';
