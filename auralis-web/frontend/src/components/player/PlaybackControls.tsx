/**
 * PlaybackControls Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Main playback control buttons (play, pause, skip, etc).
 * Integrates usePlaybackControl and usePlaybackState for seamless interaction.
 *
 * Usage:
 * ```typescript
 * <PlaybackControls />
 * ```
 *
 * Props: None required (uses hooks internally)
 *
 * @module components/player/PlaybackControls
 */

import React, { useCallback } from 'react';
import { tokens } from '@/design-system/tokens';
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';
import { usePlaybackState } from '@/hooks/player/usePlaybackState';

/**
 * PlaybackControls component
 *
 * Displays play, pause, next, previous buttons with proper states.
 * Shows loading state while commands execute.
 * Handles errors gracefully with visual feedback.
 */
export const PlaybackControls: React.FC = () => {
  const { isPlaying } = usePlaybackState();
  const { play, pause, next, previous, isLoading, error } = usePlaybackControl();

  /**
   * Handle play button click
   */
  const handlePlayClick = useCallback(async () => {
    try {
      await play();
    } catch (err) {
      console.error('Failed to play:', err);
    }
  }, [play]);

  /**
   * Handle pause button click
   */
  const handlePauseClick = useCallback(async () => {
    try {
      await pause();
    } catch (err) {
      console.error('Failed to pause:', err);
    }
  }, [pause]);

  /**
   * Handle next button click
   */
  const handleNextClick = useCallback(async () => {
    try {
      await next();
    } catch (err) {
      console.error('Failed to skip to next:', err);
    }
  }, [next]);

  /**
   * Handle previous button click
   */
  const handlePreviousClick = useCallback(async () => {
    try {
      await previous();
    } catch (err) {
      console.error('Failed to skip to previous:', err);
    }
  }, [previous]);

  return (
    <div style={styles.container}>
      {/* Error message if any */}
      {error && (
        <div style={styles.errorMessage}>
          <span>{error.message}</span>
        </div>
      )}

      {/* Control buttons */}
      <div style={styles.buttonGroup}>
        {/* Previous button */}
        <button
          onClick={handlePreviousClick}
          disabled={isLoading}
          style={styles.button}
          aria-label="Previous track"
          title="Previous track"
        >
          <span style={styles.buttonIcon}>⏮</span>
        </button>

        {/* Play/Pause button (toggle based on state) */}
        {isPlaying ? (
          <button
            onClick={handlePauseClick}
            disabled={isLoading}
            style={{ ...styles.button, ...styles.primaryButton }}
            aria-label="Pause"
            title="Pause playback"
          >
            <span style={styles.buttonIcon}>⏸</span>
          </button>
        ) : (
          <button
            onClick={handlePlayClick}
            disabled={isLoading}
            style={{ ...styles.button, ...styles.primaryButton }}
            aria-label="Play"
            title="Play"
          >
            <span style={styles.buttonIcon}>▶</span>
          </button>
        )}

        {/* Next button */}
        <button
          onClick={handleNextClick}
          disabled={isLoading}
          style={styles.button}
          aria-label="Next track"
          title="Next track"
        >
          <span style={styles.buttonIcon}>⏭</span>
        </button>
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <div style={styles.loadingIndicator}>
          <span>Loading...</span>
        </div>
      )}
    </div>
  );
};

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
  },

  buttonGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    justifyContent: 'center',
  },

  button: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '48px',
    height: '48px',
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.primary,
    border: `2px solid ${tokens.colors.border.default}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    color: tokens.colors.text.primary,
    fontSize: '20px',
    fontWeight: tokens.typography.fontWeight.bold,

    '&:hover': {
      backgroundColor: tokens.colors.bg.hover,
      borderColor: tokens.colors.accent.primary,
    },

    '&:active': {
      transform: 'scale(0.95)',
    },

    '&:disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  primaryButton: {
    backgroundColor: tokens.colors.accent.primary,
    borderColor: tokens.colors.accent.primary,
    color: tokens.colors.text.onAccent,
    width: '56px',
    height: '56px',
  },

  buttonIcon: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '24px',
  },

  errorMessage: {
    display: 'flex',
    alignItems: 'center',
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.error,
    borderRadius: tokens.borderRadius.sm,
    color: tokens.colors.text.onError,
    fontSize: tokens.typography.fontSize.sm,
  },

  loadingIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
  },
};

export default PlaybackControls;
