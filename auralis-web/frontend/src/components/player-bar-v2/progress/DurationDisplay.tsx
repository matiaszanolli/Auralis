/**
 * DurationDisplay - Total track duration indicator
 *
 * Responsibility: Display the total track duration with monospace styling
 *
 * Extracted from ProgressBar to:
 * - Make duration display testable in isolation
 * - Allow styling/formatting customization
 * - Reuse in other contexts
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

interface DurationDisplayProps {
  duration: number;
}

/**
 * DurationDisplay - Shows formatted total track duration
 *
 * @example
 * <DurationDisplay duration={295.5} />
 * // Renders: "4:55"
 */
export const DurationDisplay: React.FC<DurationDisplayProps> = ({ duration }) => {
  return <TimeDisplayText>{formatTime(duration)}</TimeDisplayText>;
};

DurationDisplay.displayName = 'DurationDisplay';
