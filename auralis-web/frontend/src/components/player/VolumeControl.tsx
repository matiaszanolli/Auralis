/**
 * VolumeControl - Volume control slider with mute toggle
 *
 * Provides interactive volume adjustment with mute button and level display.
 * Displays volume percentage and supports click/drag interactions.
 *
 * @component
 * @example
 * <VolumeControl
 *   volume={0.75}
 *   onVolumeChange={(vol) => console.log(`Volume: ${vol}`)}
 *   isMuted={false}
 *   onMuteToggle={() => console.log('toggled mute')}
 * />
 */

import { CSSProperties, useMemo, useState, memo } from 'react';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

export interface VolumeControlProps {
  /**
   * Current volume level (0-1)
   */
  volume: number;

  /**
   * Callback when volume changes (0-1)
   */
  onVolumeChange: (volume: number) => void | Promise<void>;

  /**
   * Whether audio is currently muted
   * Default: false
   */
  isMuted?: boolean;

  /**
   * Callback when mute button is clicked
   */
  onMuteToggle?: () => void | Promise<void>;

  /**
   * Whether controls are currently disabled
   * Default: false
   */
  disabled?: boolean;

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
 * VolumeControl Component
 *
 * Renders volume slider with mute button and percentage display.
 */
const VolumeControlComponent = ({
  volume,
  onVolumeChange,
  isMuted = false,
  onMuteToggle,
  disabled = false,
  className = '',
  ariaLabel,
}: VolumeControlProps) => {
  const [isMuteButtonFocused, setIsMuteButtonFocused] = useState(false);
  const [isSliderFocused, setIsSliderFocused] = useState(false);
  // Clamp volume to valid range (handle NaN)
  const clampedVolume = useMemo(() => {
    const val = Number.isNaN(volume) ? 0 : volume;
    return Math.max(0, Math.min(1, val));
  }, [volume]);

  // Calculate percentage for display
  const volumePercentage = useMemo(() => {
    const percentage = Math.round(clampedVolume * 100);
    return Number.isNaN(percentage) ? 0 : percentage;
  }, [clampedVolume]);

  // Determine mute icon based on state
  const muteIcon = useMemo(() => {
    if (isMuted || clampedVolume === 0) {
      return '🔇';
    }
    if (clampedVolume < 0.5) {
      return '🔈';
    }
    return '🔊';
  }, [isMuted, clampedVolume]);

  // Final aria label
  const finalAriaLabel = useMemo(() => {
    if (ariaLabel) {
      return ariaLabel;
    }
    return `Volume control, ${volumePercentage}%${isMuted ? ', muted' : ''}`;
  }, [ariaLabel, volumePercentage, isMuted]);

  return (
    <div
      className={className}
      data-testid="volume-control"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing.sm,
        padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
        backgroundColor: 'transparent',
        borderRadius: tokens.borderRadius.md,
        border: 'none',
        width: '100%',
        maxWidth: '160px',
      }}
    >
      {/* Mute button */}
      <button
        onClick={onMuteToggle}
        disabled={disabled}
        data-testid="volume-control-mute"
        aria-label={isMuted || clampedVolume === 0 ? 'Unmute (⌨ M )' : 'Mute (⌨ M )'}
        title={isMuted || clampedVolume === 0 ? 'Unmute (⌨ M )' : 'Mute (⌨ M )'}
        onFocus={() => setIsMuteButtonFocused(true)}
        onBlur={() => setIsMuteButtonFocused(false)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '40px',
          height: '40px',
          padding: 0,
          backgroundColor: 'transparent',
          border: `1px solid ${themeVars.borderDefault}`,
          borderRadius: tokens.borderRadius.md,
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: tokens.transitions.all,
          color: disabled ? themeVars.textDisabled : themeVars.textPrimary,
          fontSize: tokens.typography.fontSize.base,
          opacity: disabled ? 0.7 : 1,
          outline: 'none',
          ...(isMuteButtonFocused && !disabled && {
            outline: `3px solid ${themeVars.focusRing}`,
            outlineOffset: '2px',
            background: themeVars.surfaceSecondary,
          }),
        }}
        onMouseEnter={(e) => {
          if (!disabled) {
            e.currentTarget.style.background = themeVars.surfaceSecondary;
            e.currentTarget.style.borderColor = themeVars.accent;
            e.currentTarget.style.transform = 'scale(1.05)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isMuteButtonFocused) {
            e.currentTarget.style.background = 'transparent';
          }
          e.currentTarget.style.borderColor = themeVars.borderDefault;
          e.currentTarget.style.transform = 'scale(1)';
        }}
      >
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          data-testid="volume-control-icon"
        >
          {muteIcon}
        </span>
      </button>

      {/* Volume slider */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          flex: 1,
          minWidth: '100px',
        }}
      >
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={clampedVolume}
          onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
          disabled={disabled}
          data-testid="volume-control-slider"
          aria-label={finalAriaLabel}
          title={`Volume: ${volumePercentage}%`}
          onFocus={() => setIsSliderFocused(true)}
          onBlur={() => setIsSliderFocused(false)}
          style={{
            width: '100%',
            height: '6px',
            cursor: disabled ? 'default' : 'pointer',
            appearance: 'none',
            WebkitAppearance: 'none',
            borderRadius: tokens.borderRadius.full,
            border: 'none',
            outline: isSliderFocused && !disabled ? `3px solid ${themeVars.focusRing}` : 'none',
            outlineOffset: isSliderFocused && !disabled ? '2px' : '0',
            background: `linear-gradient(to right, ${themeVars.accent} 0%, ${themeVars.accent} ${clampedVolume * 100}%, ${themeVars.surfaceRaised} ${clampedVolume * 100}%, ${themeVars.surfaceRaised} 100%)`,
            opacity: disabled ? 0.5 : 1,
            transition: `height ${tokens.transitions.hover_out}, outline ${tokens.transitions.hover_out}`,
          } as CSSProperties}
        />
      </div>

      {/* Volume percentage display */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: '45px',
          fontSize: tokens.typography.fontSize.sm,
          color: themeVars.textSecondary,
          fontFamily: tokens.typography.fontFamily.mono,
          fontWeight: tokens.typography.fontWeight.bold,
        }}
        data-testid="volume-control-percentage"
      >
        {volumePercentage}%
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
export const VolumeControl = memo(VolumeControlComponent);

VolumeControl.displayName = 'VolumeControl';

export default VolumeControl;
