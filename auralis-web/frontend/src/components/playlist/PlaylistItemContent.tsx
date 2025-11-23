import React from 'react';
import { ListItemText } from '@mui/material';
import { PlaylistIcon, TrackCount } from './DroppablePlaylist.styles';

interface PlaylistItemContentProps {
  playlistName: string;
  trackCount: number;
}

/**
 * PlaylistItemContent - Displays playlist name and track count
 *
 * Shows:
 * - Playlist icon
 * - Playlist name as primary text
 * - Track count as secondary text with proper singular/plural
 */
export const PlaylistItemContent: React.FC<PlaylistItemContentProps> = ({
  playlistName,
  trackCount,
}) => {
  return (
    <>
      <PlaylistIcon fontSize="small" />
      <ListItemText
        primary={playlistName}
        secondary={
          <TrackCount>
            {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
          </TrackCount>
        }
      />
    </>
  );
};

export default PlaylistItemContent;
