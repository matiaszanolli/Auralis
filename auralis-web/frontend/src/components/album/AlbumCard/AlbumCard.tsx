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
 *
 * Fingerprint Support:
 * - Accepts optional fingerprint prop (median of album tracks)
 * - Used to generate unique gradient placeholders when no artwork exists
 * - Falls back to hash-based gradient if fingerprint not provided
 */

import React from 'react';
import { MediaCard } from '@/components/shared/MediaCard';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';

export interface AlbumCardProps {
  albumId: number;
  title: string;
  artist: string;
  hasArtwork?: boolean;
  trackCount?: number;
  duration?: number;
  year?: number;
  fingerprint?: Partial<AudioFingerprint>;
  onClick?: () => void;
  onArtworkUpdated?: () => void;
  onHoverEnter?: (albumId: number) => void;
  onHoverLeave?: () => void;
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
  fingerprint,
  onClick,
  onArtworkUpdated,
  onHoverEnter,
  onHoverLeave,
}) => {
  // Build artwork URL from albumId if artwork exists
  const artworkUrl = hasArtwork ? `/api/albums/${albumId}/artwork` : undefined;

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
      fingerprint={fingerprint}
      onClick={onClick}
      onArtworkUpdated={onArtworkUpdated}
      onHoverEnter={onHoverEnter}
      onHoverLeave={onHoverLeave}
    />
  );
};

export default AlbumCard;
