/**
 * TrackCard Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Thin wrapper around MediaCard for track display.
 */

import { memo } from 'react';
import { MediaCard } from '@/components/shared/MediaCard';
import { trackArtworkUrl } from '@/services/artworkService';
import { useArtworkRevision } from '@/hooks/library/useArtworkUpdates';

interface TrackCardProps {
  id: number;
  title: string;
  artist: string;
  album: string;
  albumId?: number;
  duration: number;
  albumArt?: string;
  artworkSize?: number;
  isPlaying?: boolean;
  onPlay: (id: number) => void;
}

/**
 * TrackCard - Track display component
 *
 * Wrapper around MediaCard with track-specific props, used by the track grid views.
 */
export const TrackCard = memo(function TrackCard({
  id,
  title,
  artist,
  album,
  albumId,
  duration,
  albumArt,
  artworkSize = 216,
  isPlaying = false,
  onPlay,
}: TrackCardProps) {
  // For tracks, clicking anywhere on the card should trigger playback
  const handleClick = () => {
    onPlay(id);
  };

  // Cache-bust on artwork_updated like the album views do (#5473) — without
  // this a mounted card keeps the old (or broken) image after the album's
  // artwork is extracted, downloaded, or deleted — and a card whose album had
  // no art at load fetches the new art by album id (#6586).
  const artworkRevision = useArtworkRevision(albumId ?? 0);

  return (
    <MediaCard
      variant="track"
      id={id}
      title={title}
      artist={artist}
      album={album}
      albumId={albumId}
      duration={duration}
      artworkUrl={trackArtworkUrl(albumArt, albumId, artworkSize, artworkRevision)}
      isPlaying={isPlaying}
      onPlay={onPlay}
      onClick={handleClick}
    />
  );
});

export default TrackCard;
