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

import React, { useMemo } from 'react';
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
        style={{
          ...styles.secondaryButton,
          opacity: isDisabled ? 0.7 : 1,
          color: isDisabled ? tokens.colors.text.disabled : tokens.colors.text.secondary,
          cursor: isDisabled ? 'not-allowed' : 'pointer',
        }}
        onMouseEnter={(e) => {
          if (!isDisabled) {
            e.currentTarget.style.backgroundColor = tokens.colors.bg.tertiary;
            e.currentTarget.style.borderColor = tokens.colors.accent.primary;
            e.currentTarget.style.transform = 'scale(1.05)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
          e.currentTarget.style.borderColor = tokens.colors.border.light;
          e.currentTarget.style.transform = 'scale(1)';
        }}
        onFocus={(e) => {
          if (!isDisabled) {
            e.currentTarget.style.outline = `3px solid ${tokens.colors.accent.primary}`;
            e.currentTarget.style.outlineOffset = '2px';
          }
        }}
        onBlur={(e) => {
          e.currentTarget.style.outline = 'none';
        }}
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
          style={{
            ...styles.primaryButton,
            opacity: isDisabled ? 0.7 : 1,
            color: isDisabled ? tokens.colors.text.disabled : tokens.colors.text.primary,
            cursor: isDisabled ? 'not-allowed' : 'pointer',
          }}
          onMouseEnter={(e) => {
            if (!isDisabled) {
              e.currentTarget.style.transform = 'scale(1.08)';
              e.currentTarget.style.boxShadow = tokens.shadows.glowMd;
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.boxShadow = tokens.shadows.md;
          }}
          onFocus={(e) => {
            if (!isDisabled) {
              e.currentTarget.style.outline = `3px solid ${tokens.colors.accent.primary}`;
              e.currentTarget.style.outlineOffset = '2px';
            }
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none';
          }}
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
          style={{
            ...styles.primaryButton,
            opacity: isDisabled ? 0.7 : 1,
            color: isDisabled ? tokens.colors.text.disabled : tokens.colors.text.primary,
            cursor: isDisabled ? 'not-allowed' : 'pointer',
          }}
          onMouseEnter={(e) => {
            if (!isDisabled) {
              e.currentTarget.style.transform = 'scale(1.08)';
              e.currentTarget.style.boxShadow = tokens.shadows.glowMd;
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.boxShadow = tokens.shadows.md;
          }}
          onFocus={(e) => {
            if (!isDisabled) {
              e.currentTarget.style.outline = `3px solid ${tokens.colors.accent.primary}`;
              e.currentTarget.style.outlineOffset = '2px';
            }
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none';
          }}
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
        style={{
          ...styles.secondaryButton,
          opacity: isDisabled ? 0.7 : 1,
          color: isDisabled ? tokens.colors.text.disabled : tokens.colors.text.secondary,
          cursor: isDisabled ? 'not-allowed' : 'pointer',
        }}
        onMouseEnter={(e) => {
          if (!isDisabled) {
            e.currentTarget.style.backgroundColor = tokens.colors.bg.tertiary;
            e.currentTarget.style.borderColor = tokens.colors.accent.primary;
            e.currentTarget.style.transform = 'scale(1.05)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
          e.currentTarget.style.borderColor = tokens.colors.border.light;
          e.currentTarget.style.transform = 'scale(1)';
        }}
        onFocus={(e) => {
          if (!isDisabled) {
            e.currentTarget.style.outline = `3px solid ${tokens.colors.accent.primary}`;
            e.currentTarget.style.outlineOffset = '2px';
          }
        }}
        onBlur={(e) => {
          e.currentTarget.style.outline = 'none';
        }}
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
