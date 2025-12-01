/**
 * PlaybackControls - Playback control buttons (play, pause, next, previous)
 *
 * Provides interactive controls for playback with visual feedback.
 * Displays loading state during operations and supports disabled state.
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
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing.md,
        justifyContent: 'center',
      }}
    >
      {/* Previous button */}
      <button
        onClick={onPrevious}
        disabled={isDisabled}
        data-testid="playback-controls-previous"
        aria-label="Previous track"
        title="Previous track"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '44px',
          height: '44px',
          padding: tokens.spacing.xs,
          backgroundColor: tokens.colors.bg.primary,
          border: `1px solid ${tokens.colors.border.default}`,
          borderRadius: '4px',
          cursor: isDisabled ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s ease',
          color: tokens.colors.text.primary,
          fontSize: '18px',
          opacity: isDisabled ? 0.5 : 1,
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
          title="Pause playback"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '52px',
            height: '52px',
            padding: tokens.spacing.xs,
            backgroundColor: tokens.colors.accent.primary,
            border: `1px solid ${tokens.colors.accent.primary}`,
            borderRadius: '4px',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            color: tokens.colors.text.primary,
            fontSize: '20px',
            opacity: isDisabled ? 0.5 : 1,
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
          title="Play"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '52px',
            height: '52px',
            padding: tokens.spacing.xs,
            backgroundColor: tokens.colors.accent.primary,
            border: `1px solid ${tokens.colors.accent.primary}`,
            borderRadius: '4px',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            color: tokens.colors.text.primary,
            fontSize: '20px',
            opacity: isDisabled ? 0.5 : 1,
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
        title="Next track"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '44px',
          height: '44px',
          padding: tokens.spacing.xs,
          backgroundColor: tokens.colors.bg.primary,
          border: `1px solid ${tokens.colors.border.default}`,
          borderRadius: '4px',
          cursor: isDisabled ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s ease',
          color: tokens.colors.text.primary,
          fontSize: '18px',
          opacity: isDisabled ? 0.5 : 1,
        }}
      >
        ⏭
      </button>

      {/* Loading indicator */}
      {isLoading && (
        <div
          data-testid="playback-controls-loading"
          style={{
            fontSize: tokens.typography.fontSize.xs,
            color: tokens.colors.text.secondary,
            marginLeft: tokens.spacing.md,
          }}
        >
          Loading...
        </div>
      )}
    </div>
  );
};

export default PlaybackControls;
