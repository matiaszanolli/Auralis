/**
 * PlaybackControls - Modern playback control buttons
 *
 * Provides interactive controls for playback with:
 * - Smooth hover and active state transitions
 * - Gradient accent for play button
 * - Proper visual hierarchy between primary (play/pause) and secondary controls
 * - Touch-friendly button sizing
 *
 * @component
 * @example
 * <PlaybackControls
 *   isPlaying={true}
 *   onPlay={() => console.log('play')}
 *   onPause={() => console.log('pause')}
 *   onNext={() => console.log('next')}
 *   onPrevious={() => console.log('previous')}
 *   isLoading={false}
 * />
 */

import React, { useMemo, useState } from 'react';
import { tokens } from '@/design-system';
import styles from './PlaybackControlsStyles';

export interface PlaybackControlsProps {
  /**
   * Whether playback is currently active
   */
  isPlaying: boolean;

  /**
   * Callback when play button is clicked
   */
  onPlay: () => void | Promise<void>;

  /**
   * Callback when pause button is clicked
   */
  onPause: () => void | Promise<void>;

  /**
   * Callback when next button is clicked
   */
  onNext: () => void | Promise<void>;

  /**
   * Callback when previous button is clicked
   */
  onPrevious: () => void | Promise<void>;

  /**
   * Whether controls are currently loading/disabled
   * Default: false
   */
  isLoading?: boolean;

  /**
   * Additional CSS class names
   */
  className?: string;

  /**
   * Disable all controls
   * Default: false
   */
  disabled?: boolean;
}

/**
 * PlaybackControls Component
 *
 * Renders play/pause, next, and previous buttons with proper state management.
 */
export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  isPlaying,
  onPlay,
  onPause,
  onNext,
  onPrevious,
  isLoading = false,
  className = '',
  disabled = false,
}) => {
  // Determine if buttons should be disabled
  const isDisabled = useMemo(() => {
    return disabled || isLoading;
  }, [disabled, isLoading]);

  // Hover and focus state tracking per button
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [focusedButton, setFocusedButton] = useState<string | null>(null);

  // Compute secondary button hover/focus styles based on state
  const getSecondaryButtonStyle = (buttonId: string) => ({
    ...styles.secondaryButton,
    opacity: isDisabled ? 0.7 : 1,
    color: isDisabled ? tokens.colors.text.disabled : tokens.colors.text.secondary,
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    ...(hoveredButton === buttonId && !isDisabled ? {
      backgroundColor: tokens.colors.bg.tertiary,
      borderColor: tokens.colors.accent.primary,
      transform: 'scale(1.05)',
    } : {}),
    ...(focusedButton === buttonId && !isDisabled ? {
      outline: `3px solid ${tokens.colors.accent.primary}`,
      outlineOffset: '2px',
    } : {}),
  });

  // Compute primary button hover/focus styles based on state
  const getPrimaryButtonStyle = () => ({
    ...styles.primaryButton,
    opacity: isDisabled ? 0.7 : 1,
    color: isDisabled ? tokens.colors.text.disabled : tokens.colors.text.primary,
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    ...(hoveredButton === 'primary' && !isDisabled ? {
      transform: 'scale(1.08)',
      boxShadow: tokens.shadows.glowMd,
    } : {}),
    ...(focusedButton === 'primary' && !isDisabled ? {
      outline: `3px solid ${tokens.colors.accent.primary}`,
      outlineOffset: '2px',
    } : {}),
  });

  return (
    <div
      className={className}
      data-testid="playback-controls"
      style={styles.container}
    >
      {/* Previous button */}
      <button
        onClick={onPrevious}
        disabled={isDisabled}
        data-testid="playback-controls-previous"
        aria-label="Previous track"
        title="Previous track (⌨ ← )"
        style={getSecondaryButtonStyle('previous')}
        onMouseEnter={() => setHoveredButton('previous')}
        onMouseLeave={() => setHoveredButton(null)}
        onFocus={() => setFocusedButton('previous')}
        onBlur={() => setFocusedButton(null)}
      >
        ⏮
      </button>

      {/* Play/Pause button (toggle based on state) */}
      {isPlaying ? (
        <button
          onClick={onPause}
          disabled={isDisabled}
          data-testid="playback-controls-pause"
          aria-label="Pause"
          title="Pause playback (⌨ Space )"
          style={getPrimaryButtonStyle()}
          onMouseEnter={() => setHoveredButton('primary')}
          onMouseLeave={() => setHoveredButton(null)}
          onFocus={() => setFocusedButton('primary')}
          onBlur={() => setFocusedButton(null)}
        >
          ⏸
        </button>
      ) : (
        <button
          onClick={onPlay}
          disabled={isDisabled}
          data-testid="playback-controls-play"
          aria-label="Play"
          title="Play (⌨ Space )"
          style={getPrimaryButtonStyle()}
          onMouseEnter={() => setHoveredButton('primary')}
          onMouseLeave={() => setHoveredButton(null)}
          onFocus={() => setFocusedButton('primary')}
          onBlur={() => setFocusedButton(null)}
        >
          ▶
        </button>
      )}

      {/* Next button */}
      <button
        onClick={onNext}
        disabled={isDisabled}
        data-testid="playback-controls-next"
        aria-label="Next track"
        title="Next track (⌨ → )"
        style={getSecondaryButtonStyle('next')}
        onMouseEnter={() => setHoveredButton('next')}
        onMouseLeave={() => setHoveredButton(null)}
        onFocus={() => setFocusedButton('next')}
        onBlur={() => setFocusedButton(null)}
      >
        ⏭
      </button>

      {/* Loading indicator with live region announcement */}
      {isLoading && (
        <div
          data-testid="playback-controls-loading"
          role="status"
          aria-live="polite"
          aria-atomic="true"
          style={styles.loadingIndicator}
        >
          Loading...
        </div>
      )}
    </div>
  );
};

export default PlaybackControls;
