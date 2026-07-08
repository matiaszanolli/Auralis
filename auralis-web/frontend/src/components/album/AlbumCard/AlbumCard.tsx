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

import { memo } from 'react';
import { MediaCard } from '@/components/shared/MediaCard';
import { useArtworkRevision } from '@/hooks/library/useArtworkUpdates';
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
  onClick?: (albumId: number) => void;
  onArtworkUpdated?: () => void;
  /**
   * Accepts the full (albumId, title, artist) signature so callers can pass
   * a single stable callback straight through — mirroring `onClick` above —
   * instead of allocating a new per-item arrow closing over `title`/`artist`
   * on every render, which would defeat this component's own React.memo
   * (fixes #3929).
   */
  onHoverEnter?: (albumId: number, title: string, artist: string) => void;
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
export const AlbumCard = memo(function AlbumCard({
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
}: AlbumCardProps) {
  // Subscribe to artwork_updated WS messages for cache-busting (#2867)
  const artworkRevision = useArtworkRevision(albumId);
  const artworkUrl = hasArtwork
    ? `/api/albums/${albumId}/artwork${artworkRevision > 0 ? `?v=${artworkRevision}` : ''}`
    : undefined;

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
      onClick={onClick ? () => onClick(albumId) : undefined}
      onArtworkUpdated={onArtworkUpdated}
      onHoverEnter={onHoverEnter ? () => onHoverEnter(albumId, title, artist) : undefined}
      onHoverLeave={onHoverLeave}
    />
  );
});

export default AlbumCard;
