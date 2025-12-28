/**
 * AlbumCard Component (Unified)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Thin wrapper around MediaCard for album display.
 * Maintains backwards compatibility while using unified MediaCard internally.
 *
 * Migration: Refactored from 109 lines to 60 lines by delegating to MediaCard.
 * Eliminates duplication with TrackCard.
 *
 * Note: Artwork management features (download/extract) temporarily removed.
 * Will be re-added via MediaCard extension in future iteration.
 */

import React from 'react';
import { MediaCard } from '@/components/shared/MediaCard';

export interface AlbumCardProps {
  albumId: number;
  title: string;
  artist: string;
  hasArtwork?: boolean;
  trackCount?: number;
  duration?: number;
  year?: number;
  onClick?: () => void;
  onArtworkUpdated?: () => void;
}

/**
 * AlbumCard - Album display component
 *
 * Wrapper around MediaCard with album-specific props.
 * Provides backwards compatibility for existing album grid views.
 *
 * TODO: Re-implement artwork management (download/extract/delete) via
 * MediaCard extension or separate overlay component.
 */
export const AlbumCard: React.FC<AlbumCardProps> = ({
  albumId,
  title,
  artist,
  hasArtwork = false,
  trackCount = 0,
  duration,
  year,
  onClick,
  onArtworkUpdated,
}) => {
  // Build artwork URL from albumId if artwork exists
  const artworkUrl = hasArtwork ? `/api/artwork/album/${albumId}` : undefined;

  return (
    <MediaCard
      variant="album"
      id={albumId}
      title={title}
      artist={artist}
      trackCount={trackCount}
      duration={duration}
      year={year}
      artworkUrl={artworkUrl}
      hasArtwork={hasArtwork}
      onClick={onClick}
      onArtworkUpdated={onArtworkUpdated}
    />
  );
};

export default AlbumCard;
