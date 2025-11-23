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
export const TrackRowPlayButton: React.FC<TrackRowPlayButtonProps> = ({
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

export default TrackRowPlayButton;
