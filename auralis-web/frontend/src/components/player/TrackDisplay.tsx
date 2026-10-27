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

import { useMemo, memo, useState } from 'react';
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
   * Album artwork URL for the current track. The backend emits it on the
   * player_state/queue TrackInfo; null/absent renders a ♪ placeholder.
   * (#5521 wired this into the player bar; #5528 made the backend null-safe.)
   */
  artworkUrl?: string | null;

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
 * Renders the current track's artwork thumbnail, title, artist, and album
 * with proper overflow handling.
 */
const TrackDisplayComponent = ({
  title,
  artist,
  album,
  artworkUrl,
  isLoading = false,
  className = '',
  ariaLabel,
}: TrackDisplayProps) => {
  // Track the URL whose load failed (per-URL, like ArtistHeader #5520) so a
  // blocked/failed image falls back to the placeholder and a different
  // track's artwork is retried.
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const showArtwork = Boolean(artworkUrl) && failedUrl !== artworkUrl;

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

  // Screen-reader live region for track changes (fixes #2362). The region and
  // its wrapper render in BOTH branches (#5667): the region used to sit only
  // in the loaded branch, so every track change — which passes through
  // buffering — unmounted it and re-inserted it already containing its text,
  // which screen readers announce inconsistently or not at all. A region that
  // stays mounted and has its text updated is always announced.
  const announcement = `Now playing: ${title}${artist ? ` by ${artist}` : ''}${album ? ` from ${album}` : ''}`;

  const skeletonStyle = {
    backgroundColor: themeVars.surfaceRaised,
    borderRadius: '4px',
    animation: `pulse ${tokens.animations.pulse.duration} ${tokens.transitions.easeInOut} ${tokens.animations.pulse.iteration}`,
  } as const;

  return (
    // role="group" gives the decorative aria-label a semantics-bearing
    // element (#5667): a plain div ignores aria-label.
    <div
      role="group"
      aria-label={finalAriaLabel}
      className={className}
      data-testid="track-display"
      style={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        gap: tokens.spacing.sm,
        minWidth: '0',
      }}
    >
      <div
        aria-live="polite"
        aria-atomic="true"
        style={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clipPath: 'inset(50%)', whiteSpace: 'nowrap' }}
      >
        {announcement}
      </div>

      {/* Album artwork thumbnail (#5521) */}
      {isLoading ? (
        <div
          style={{
            ...skeletonStyle,
            width: 44,
            height: 44,
            flexShrink: 0,
            borderRadius: '6px',
          }}
          data-testid="track-display-artwork-loading"
        />
      ) : showArtwork && artworkUrl ? (
        <img
          src={artworkUrl}
          alt=""
          style={{
            width: 44,
            height: 44,
            flexShrink: 0,
            borderRadius: '6px',
            objectFit: 'cover',
          }}
          data-testid="track-display-artwork"
          onError={() => setFailedUrl(artworkUrl ?? null)}
        />
      ) : (
        <div
          aria-hidden="true"
          style={{
            width: 44,
            height: 44,
            flexShrink: 0,
            borderRadius: '6px',
            backgroundColor: themeVars.surfaceRaised,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: themeVars.textMuted,
            fontSize: tokens.typography.fontSize.lg,
          }}
          data-testid="track-display-artwork-placeholder"
        >
          ♪
        </div>
      )}

      {/* Track details column */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: tokens.spacing.xs,
          minWidth: '0',
        }}
      >
        {isLoading ? (
          /* Display loading state */
          <>
            <div style={{ ...skeletonStyle, height: '20px' }} data-testid="track-display-loading" />
            {artist && (
              <div style={{ ...skeletonStyle, height: '16px', width: '70%' }} />
            )}
          </>
        ) : (
          <>
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
          </>
        )}
      </div>
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
