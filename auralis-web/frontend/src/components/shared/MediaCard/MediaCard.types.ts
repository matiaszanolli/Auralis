/**
 * MediaCard Types
 * ~~~~~~~~~~~~~~~
 *
 * Unified type definitions for MediaCard component.
 * Supports both track and album variants with shared and variant-specific props.
 */

export type MediaCardVariant = 'track' | 'album';

/**
 * Base props shared by all media card variants
 */
export interface BaseMediaCardProps {
  /** Unique identifier */
  id: number;
  /** Display title */
  title: string;
  /** Artist name */
  artist: string;
  /** Duration in seconds */
  duration?: number;
  /** Artwork URL (optional) */
  artworkUrl?: string;
  /** Whether this item is currently playing */
  isPlaying?: boolean;
  /** Click handler */
  onClick?: () => void;
  /** Play handler */
  onPlay?: (id: number) => void;
}

/**
 * Track-specific props
 */
export interface TrackMediaCardProps extends BaseMediaCardProps {
  variant: 'track';
  /** Album name */
  album: string;
  /** Album ID for navigation */
  albumId?: number;
}

/**
 * Album-specific props
 */
export interface AlbumMediaCardProps extends BaseMediaCardProps {
  variant: 'album';
  /** Number of tracks in album */
  trackCount?: number;
  /** Release year */
  year?: number;
  /** Whether album has artwork */
  hasArtwork?: boolean;
  /** Artwork update callback */
  onArtworkUpdated?: () => void;
}

/**
 * Union type for all MediaCard variants
 */
export type MediaCardProps = TrackMediaCardProps | AlbumMediaCardProps;

/**
 * Metadata to display below artwork
 */
export interface MediaMetadata {
  /** Primary line (artist name) */
  primary: string;
  /** Secondary line (album name for tracks, track count + year for albums) */
  secondary: string;
}
