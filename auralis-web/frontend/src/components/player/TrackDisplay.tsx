/**
 * TrackDisplay - Display current track information
 *
 * Shows track title, artist, and album with proper overflow handling.
 *
 * @component
 * @example
 * <TrackDisplay
 *   title="Song Title"
 *   artist="Artist Name"
 *   album="Album Name"
 * />
 */

import React, { useMemo } from 'react';
import { tokens } from '@/design-system';

export interface TrackDisplayProps {
  /**
   * Track title
   */
  title: string;

  /**
   * Artist name
   */
  artist?: string;

  /**
   * Album name
   */
  album?: string;

  /**
   * Whether track info is loading
   * Default: false
   */
  isLoading?: boolean;

  /**
   * Additional CSS class names
   */
  className?: string;

  /**
   * Custom aria label (optional)
   */
  ariaLabel?: string;
}

/**
 * TrackDisplay Component
 *
 * Renders track title, artist, and album information with proper text overflow handling.
 */
export const TrackDisplay: React.FC<TrackDisplayProps> = ({
  title,
  artist,
  album,
  isLoading = false,
  className = '',
  ariaLabel,
}) => {
  // Final aria label
  const finalAriaLabel = useMemo(() => {
    if (ariaLabel) {
      return ariaLabel;
    }
    const parts = [title];
    if (artist) parts.push(artist);
    if (album) parts.push(album);
    return parts.join(' • ');
  }, [title, artist, album, ariaLabel]);

  // Display loading state
  if (isLoading) {
    return (
      <div
        className={className}
        data-testid="track-display"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: tokens.spacing.xs,
          minWidth: '0',
        }}
        aria-label={finalAriaLabel}
      >
        <div
          style={{
            height: '20px',
            backgroundColor: tokens.colors.bg.tertiary,
            borderRadius: '4px',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          }}
          data-testid="track-display-loading"
        />
        {artist && (
          <div
            style={{
              height: '16px',
              backgroundColor: tokens.colors.bg.tertiary,
              borderRadius: '4px',
              width: '70%',
              animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }}
          />
        )}
      </div>
    );
  }

  return (
    <div
      className={className}
      data-testid="track-display"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.xs,
        minWidth: '0',
      }}
      aria-label={finalAriaLabel}
    >
      {/* Track Title */}
      <div
        style={{
          fontSize: tokens.typography.fontSize.md,
          fontWeight: 'bold',
          color: tokens.colors.text.primary,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          lineHeight: '1.4',
        }}
        data-testid="track-display-title"
        title={title}
      >
        {title}
      </div>

      {/* Artist and Album Info */}
      {(artist || album) && (
        <div
          style={{
            fontSize: tokens.typography.fontSize.sm,
            color: tokens.colors.text.secondary,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            lineHeight: '1.4',
          }}
          data-testid="track-display-meta"
          title={[artist, album].filter(Boolean).join(' • ')}
        >
          {artist && <span data-testid="track-display-artist">{artist}</span>}
          {artist && album && <span> • </span>}
          {album && <span data-testid="track-display-album">{album}</span>}
        </div>
      )}
    </div>
  );
};

export default TrackDisplay;
