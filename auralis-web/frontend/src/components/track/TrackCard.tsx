/**
 * TrackCard Component (Refactored)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Card for displaying individual tracks in grid view.
 * Refactored from 248 lines using extracted components and helpers.
 *
 * Extracted modules:
 * - TrackCardHelpers - Utility functions (getAlbumColor, formatDuration)
 * - TrackCardStyles - Styled components
 * - useTrackCardState - Hover state hook
 * - TrackCardOverlay - Play button and duration badge
 * - TrackCardInfo - Track metadata display
 */

import React from 'react';
import { StyledTrackCard, ArtworkContainer } from './TrackCardStyles';
import { TrackCardOverlay } from './TrackCardOverlay';
import { TrackCardInfo } from './TrackCardInfo';
import { useTrackCardState } from './useTrackCardState';
import { getAlbumColor } from './TrackCardHelpers';

interface TrackCardProps {
  id: number;
  title: string;
  artist: string;
  album: string;
  albumId?: number;
  duration: number;
  albumArt?: string;
  isPlaying?: boolean;
  onPlay: (id: number) => void;
}

/**
 * TrackCard - Main orchestrator component
 *
 * Composition:
 * - StyledTrackCard wrapper (with visual anchor for currently playing track)
 * - ArtworkContainer with responsive aspect ratio
 * - TrackCardOverlay for interactive elements
 * - TrackCardInfo for metadata
 */
export const TrackCard: React.FC<TrackCardProps> = ({
  id,
  title,
  artist,
  album,
  albumId,
  duration,
  albumArt,
  isPlaying = false,
  onPlay,
}) => {
  const { isHovered, setIsHovered } = useTrackCardState();

  const handlePlayClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPlay(id);
  };

  return (
    <StyledTrackCard
      isPlaying={isPlaying}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onPlay(id)}
    >
      {/* Artwork or placeholder */}
      <ArtworkContainer
        sx={{
          background: albumArt
            ? `url(${albumArt}) center/cover`
            : getAlbumColor(album),
        }}
      >
        <TrackCardOverlay
          duration={duration}
          hasArtwork={!!albumArt}
          isHovered={isHovered}
          onPlay={handlePlayClick}
        />
      </ArtworkContainer>

      {/* Track info */}
      <TrackCardInfo title={title} artist={artist} album={album} isPlaying={isPlaying} />
    </StyledTrackCard>
  );
};

export default TrackCard;
