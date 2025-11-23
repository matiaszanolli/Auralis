/**
 * TrackInfo - Display current track information
 *
 * Features:
 * - Album artwork with fallback
 * - Track title and artist
 * - Favorite button toggle
 * - Text truncation for long names
 * - Smooth animations
 *
 * Styled components extracted to TrackInfo.styles.ts
 */

import React, { useState } from 'react';
import { Tooltip } from '@mui/material';
import FavoriteIcon from '@mui/icons-material/Favorite';
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';
import LyricsIcon from '@mui/icons-material/Lyrics';
import { AlbumArtDisplay } from '../shared/ui/media';
import {
  TrackInfoContainer,
  TrackDetails,
  TitleContainer,
  ActionButtonsContainer,
  ActionButton,
  TrackTitle,
  TrackArtist,
} from './TrackInfo.styles';

interface TrackInfoProps {
  track: {
    id?: number;
    title?: string;
    artist?: string;
    album?: string;
    artwork_url?: string;
  } | null;
  onToggleLyrics?: () => void;
  showLyricsButton?: boolean;
}

export const TrackInfo: React.FC<TrackInfoProps> = React.memo(({
  track,
  onToggleLyrics,
  showLyricsButton = true
}) => {
  const [isFavorite, setIsFavorite] = useState(false);

  const handleFavoriteToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsFavorite(!isFavorite);
  };

  if (!track) {
    return (
      <TrackInfoContainer>
        <AlbumArtDisplay
          size={56}
          title="No track"
          album="No track"
        />
        <TrackDetails>
          <TrackTitle>No track playing</TrackTitle>
          <TrackArtist>Select a track to start</TrackArtist>
        </TrackDetails>
      </TrackInfoContainer>
    );
  }

  return (
    <TrackInfoContainer>
      <AlbumArtDisplay
        size={56}
        artworkPath={track.artwork_url}
        title={track.title}
        album={track.album}
      />

      <TrackDetails>
        <TitleContainer>
          <TrackTitle title={track.title} sx={{ flex: 1 }}>
            {track.title || 'Unknown Track'}
          </TrackTitle>
          <ActionButtonsContainer>
            <Tooltip title={isFavorite ? 'Remove from favorites' : 'Add to favorites'} arrow>
              <ActionButton
                onClick={handleFavoriteToggle}
                aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                size="small"
              >
                {isFavorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
              </ActionButton>
            </Tooltip>
            {showLyricsButton && onToggleLyrics && (
              <Tooltip title="Toggle lyrics" arrow>
                <ActionButton
                  onClick={onToggleLyrics}
                  aria-label="Toggle lyrics"
                  size="small"
                >
                  <LyricsIcon />
                </ActionButton>
              </Tooltip>
            )}
          </ActionButtonsContainer>
        </TitleContainer>
        <TrackArtist title={track.artist}>
          {track.artist || 'Unknown Artist'}
        </TrackArtist>
      </TrackDetails>
    </TrackInfoContainer>
  );
});

TrackInfo.displayName = 'TrackInfo';
