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

import { useMemo, memo } from 'react';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

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
const TrackDisplayComponent = ({
  title,
  artist,
  album,
  isLoading = false,
  className = '',
  ariaLabel,
}: TrackDisplayProps) => {
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
            backgroundColor: themeVars.surfaceRaised,
            borderRadius: '4px',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          }}
          data-testid="track-display-loading"
        />
        {artist && (
          <div
            style={{
              height: '16px',
              backgroundColor: themeVars.surfaceRaised,
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
      {/* Screen-reader live region for track changes (fixes #2362) */}
      <div
        aria-live="polite"
        aria-atomic="true"
        style={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clipPath: 'inset(50%)', whiteSpace: 'nowrap' }}
      >
        {`Now playing: ${title}${artist ? ` by ${artist}` : ''}${album ? ` from ${album}` : ''}`}
      </div>

      {/* Track Title */}
      <div
        style={{
          fontSize: tokens.typography.fontSize.md,
          fontWeight: tokens.typography.fontWeight.bold,
          color: themeVars.textPrimary,
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
            color: themeVars.textSecondary,
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

/**
 * Memoized (#4632): `Player` re-renders 10x/second while a track is playing —
 * it subscribes to the 10Hz position tick via `usePlaybackProgress()` because it
 * renders the progress bar. This component's props do not change on that tick,
 * so without `memo` its whole body re-executed 10x/second for the entire
 * duration of every playback session, on a machine that is simultaneously
 * running the Python DSP engine.
 *
 * This only holds while every prop stays referentially stable: an inline arrow
 * or object literal at the call site defeats it silently. See Player.tsx, where
 * the handlers are `useCallback`-wrapped for exactly this reason.
 */
export const TrackDisplay = memo(TrackDisplayComponent);

TrackDisplay.displayName = 'TrackDisplay';

export default TrackDisplay;
