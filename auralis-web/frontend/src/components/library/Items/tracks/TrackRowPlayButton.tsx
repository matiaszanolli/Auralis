import React from 'react';
import { PlayArrow, Pause } from '@mui/icons-material';
import { PlayButton } from './TrackRow.styles';

interface TrackRowPlayButtonProps {
  isCurrent: boolean;
  isPlaying: boolean;
  onClick: (e: React.MouseEvent) => void;
}

/**
 * TrackRowPlayButton - Play/pause button for track row
 *
 * Shows play icon normally, pause when track is current and playing.
 */
const TrackRowPlayButtonComponent: React.FC<TrackRowPlayButtonProps> = ({
  isCurrent,
  isPlaying,
  onClick,
}) => {
  return (
    <PlayButton onClick={onClick} size="small" className="play-button">
      {isCurrent && isPlaying ? <Pause /> : <PlayArrow />}
    </PlayButton>
  );
};

/**
 * Memoized TrackRowPlayButton with custom comparator
 * Only re-renders when isCurrent or isPlaying change
 * onClick is excluded as it's recreated on parent render but doesn't affect button state
 */
export const TrackRowPlayButton = React.memo<TrackRowPlayButtonProps>(
  TrackRowPlayButtonComponent,
  (prev, next) => {
    return (
      prev.isCurrent === next.isCurrent &&
      prev.isPlaying === next.isPlaying
    );
  }
);

export default TrackRowPlayButton;
