/**
 * ProgressBar - Orchestrator for seek bar with crossfade visualization
 *
 * Composition:
 * - CurrentTimeDisplay: Shows current playback time
 * - SeekSlider: Interactive seeking with preview
 *   - CrossfadeVisualization: Overlaid crossfade region indicators
 * - DurationDisplay: Shows total track duration
 *
 * Responsibility: Compose sub-components, manage layout
 *
 * Refactored to use composition for:
 * - Better separation of concerns
 * - Easier testing of individual features
 * - Simpler modifications to seeking or visualization
 * - Reuse of sub-components in other contexts
 */

import React from 'react';
import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { CurrentTimeDisplay } from './progress/CurrentTimeDisplay';
import { DurationDisplay } from './progress/DurationDisplay';
import { SeekSlider } from './progress/SeekSlider';
import { CrossfadeVisualization } from './progress/CrossfadeVisualization';

interface ProgressBarProps {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  chunkDuration: number; // 15s
  chunkInterval: number; // 10s
}

const ProgressContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
  width: '100%'
});

/**
 * ProgressBar - Main component
 *
 * Layout:
 * ┌─────────────────────────────────────────┐
 * │ [0:45] [======●========] [4:55]         │
 * │         └── Crossfade regions overlaid  │
 * └─────────────────────────────────────────┘
 *
 * @example
 * <ProgressBar
 *   currentTime={45.32}
 *   duration={295}
 *   onSeek={(time) => player.seek(time)}
 *   chunkDuration={15}
 *   chunkInterval={10}
 * />
 */
export const ProgressBar: React.FC<ProgressBarProps> = ({
  currentTime,
  duration,
  onSeek,
  chunkDuration,
  chunkInterval
}) => {
  return (
    <ProgressContainer>
      {/* Current playback time */}
      <CurrentTimeDisplay currentTime={currentTime} />

      {/* Seek slider with overlaid crossfade visualization */}
      <SeekSlider currentTime={currentTime} duration={duration} onSeek={onSeek}>
        <CrossfadeVisualization duration={duration} chunkDuration={chunkDuration} chunkInterval={chunkInterval} />
      </SeekSlider>

      {/* Total duration */}
      <DurationDisplay duration={duration} />
    </ProgressContainer>
  );
};

ProgressBar.displayName = 'ProgressBar';
