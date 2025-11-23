import React from 'react';
import { TrackCountBox, TrackCountText } from './EditPlaylistDialog.styles';

interface PlaylistTrackCountProps {
  trackCount: number;
}

/**
 * PlaylistTrackCount - Displays the number of tracks in a playlist
 *
 * Shows:
 * - Track count with proper singular/plural form
 * - Styled info box with aurora theme
 */
export const PlaylistTrackCount: React.FC<PlaylistTrackCountProps> = ({ trackCount }) => {
  return (
    <TrackCountBox>
      <TrackCountText>
        {trackCount} track{trackCount !== 1 ? 's' : ''} in this playlist
      </TrackCountText>
    </TrackCountBox>
  );
};

export default PlaylistTrackCount;
