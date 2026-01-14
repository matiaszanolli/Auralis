/**
 * TrackCard Component (Unified)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Thin wrapper around MediaCard for track display.
 * Maintains backwards compatibility while using unified MediaCard internally.
 *
 * Migration: Refactored from 92 lines to 40 lines by delegating to MediaCard.
 * Eliminates duplication with AlbumCard.
 */

import React from 'react';
import { MediaCard } from '@/components/shared/MediaCard';

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
 * TrackCard - Track display component
 *
 * Wrapper around MediaCard with track-specific props.
 * Provides backwards compatibility for existing track grid views.
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
  // For tracks, clicking anywhere on the card should trigger playback
  const handleClick = () => {
    onPlay(id);
  };

  return (
    <MediaCard
      variant="track"
      id={id}
      title={title}
      artist={artist}
      album={album}
      albumId={albumId}
      duration={duration}
      artworkUrl={albumArt}
      isPlaying={isPlaying}
      onPlay={onPlay}
      onClick={handleClick}
    />
  );
};

export default TrackCard;
