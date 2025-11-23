import React from 'react';
import { TrackCountInfoBox, TrackCountInfoText } from './CreatePlaylistDialog.styles';

interface InitialTracksInfoProps {
  trackIds?: number[];
}

/**
 * InitialTracksInfo - Displays count of tracks to be added to new playlist
 *
 * Shows:
 * - Number of tracks with proper singular/plural form
 * - Only displayed when tracks are provided
 * - Styled info box with aurora theme
 */
export const InitialTracksInfo: React.FC<InitialTracksInfoProps> = ({ trackIds }) => {
  if (!trackIds || trackIds.length === 0) return null;

  return (
    <TrackCountInfoBox>
      <TrackCountInfoText>
        {trackIds.length} track{trackIds.length !== 1 ? 's' : ''} will be added to this playlist
      </TrackCountInfoText>
    </TrackCountInfoBox>
  );
};

export default InitialTracksInfo;
