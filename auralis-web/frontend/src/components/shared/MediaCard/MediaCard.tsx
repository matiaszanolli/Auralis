/**
 * MediaCard Component (Unified)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unified card component for displaying both tracks and albums.
 * Eliminates duplication between TrackCard and AlbumCard.
 *
 * Features:
 * - Variant support (track/album)
 * - Consistent styling via design tokens
 * - Artwork with placeholder fallback
 * - Hover interactions
 * - Play button overlay
 * - Metadata display
 *
 * Architecture:
 * - MediaCardArtwork: Artwork container with placeholders
 * - MediaCardOverlay: Play button and badges
 * - MediaCardInfo: Metadata display
 * - useMediaCardState: Hover state management
 */

import React from 'react';
import { Card } from '@/design-system';
import { tokens } from '@/design-system';
import { MediaCardArtwork } from './MediaCardArtwork';
import { MediaCardOverlay } from './MediaCardOverlay';
import { MediaCardInfo } from './MediaCardInfo';
import { useMediaCardState } from './useMediaCardState';
import type { MediaCardProps } from './MediaCard.types';

/**
 * Format duration in seconds to MM:SS
 */
const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

/**
 * Build metadata strings based on variant
 */
const getMetadata = (props: MediaCardProps) => {
  if (props.variant === 'track') {
    return {
      primary: props.artist,
      secondary: props.album,
      badgeContent: props.duration ? formatDuration(props.duration) : null,
      fallbackText: props.album,
    };
  } else {
    // Album variant
    const parts = [];
    if (props.trackCount) {
      parts.push(`${props.trackCount} track${props.trackCount !== 1 ? 's' : ''}`);
    }
    if (props.year) {
      parts.push(props.year.toString());
    }
    if (props.duration) {
      parts.push(formatDuration(props.duration));
    }

    return {
      primary: props.artist,
      secondary: parts.join(' • '),
      badgeContent: props.trackCount ? `${props.trackCount} tracks` : null,
      fallbackText: props.title,
    };
  }
};

/**
 * MediaCard - Unified media card component
 *
 * Usage:
 * ```tsx
 * // Track variant
 * <MediaCard
 *   variant="track"
 *   id={track.id}
 *   title={track.title}
 *   artist={track.artist}
 *   album={track.album}
 *   duration={track.duration}
 *   artworkUrl={track.albumArt}
 *   onPlay={handlePlay}
 * />
 *
 * // Album variant
 * <MediaCard
 *   variant="album"
 *   id={album.id}
 *   title={album.title}
 *   artist={album.artist}
 *   trackCount={album.trackCount}
 *   year={album.year}
 *   artworkUrl={album.artworkPath}
 *   onClick={handleClick}
 * />
 * ```
 */
export const MediaCard: React.FC<MediaCardProps> = (props) => {
  const { isHovered, setIsHovered } = useMediaCardState();
  const metadata = getMetadata(props);

  const handlePlayClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (props.onPlay) {
      props.onPlay(props.id);
    } else if (props.onClick) {
      props.onClick();
    }
  };

  return (
    <Card
      sx={{
        position: 'relative',
        borderRadius: tokens.borderRadius.lg,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: tokens.transitions.medium,
        background: tokens.colors.bg.level3,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.25)',
          background: tokens.colors.bg.level4,
        },
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={props.onClick}
    >
      {/* Artwork Section */}
      <MediaCardArtwork
        artworkUrl={props.artworkUrl}
        fallbackText={metadata.fallbackText}
        variant={props.variant}
      >
        <MediaCardOverlay
          isHovered={isHovered}
          isPlaying={props.isPlaying}
          onPlay={handlePlayClick}
          badgeContent={metadata.badgeContent}
        />
      </MediaCardArtwork>

      {/* Info Section */}
      <MediaCardInfo
        title={props.title}
        primary={metadata.primary}
        secondary={metadata.secondary}
        isPlaying={props.isPlaying}
      />
    </Card>
  );
};

export default MediaCard;
