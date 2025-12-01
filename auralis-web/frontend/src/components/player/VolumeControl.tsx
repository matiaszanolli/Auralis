/**
 * VolumeControl Component
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Volume slider with mute toggle and level display.
 * Interactive control with smooth slider feedback.
 *
 * Usage:
 * ```typescript
 * <VolumeControl />
 * ```
 *
 * Props: None required (uses hooks internally)
 *
 * @module components/player/VolumeControl
 */

import React, { useCallback, useState } from 'react';
import { tokens } from '@/design-system/tokens';
import { useVolume } from '@/hooks/player/usePlaybackState';
import { useVolumeControl } from '@/hooks/player/usePlaybackControl';

/**
 * VolumeControl component
 *
 * Displays volume slider with mute button.
 * Shows current volume percentage.
 * Handles dragging and discrete clicks.
 */
export const VolumeControl: React.FC = () => {
  const currentVolume = useVolume();
  const { setVolume, isLoading } = useVolumeControl();
  const [isDragging, setIsDragging] = useState(false);
  const [dragVolume, setDragVolume] = useState(currentVolume);
  const [isMuted, setIsMuted] = useState(false);

  // Store previous volume for unmute
  const [previousVolume, setPreviousVolume] = useState(currentVolume);

  /**
   * Handle volume slider change
   */
  const handleVolumeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newVolume = parseFloat(e.target.value);
      setDragVolume(newVolume);
      setIsDragging(true);
    },
    []
  );

  /**
   * Handle volume slider release
   */
  const handleVolumeRelease = useCallback(async () => {
    setIsDragging(false);
    setIsMuted(false); // Unmute when user adjusts volume

    try {
      await setVolume(dragVolume);
    } catch (err) {
      console.error('Failed to set volume:', err);
      // Reset to current volume on error
      setDragVolume(currentVolume);
    }
  }, [dragVolume, currentVolume, setVolume]);

  /**
   * Handle mute toggle
   */
  const handleMuteToggle = useCallback(async () => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);

    try {
      if (newMuted) {
        // Mute
        setPreviousVolume(currentVolume);
        await setVolume(0);
      } else {
        // Unmute
        const volumeToRestore = previousVolume > 0 ? previousVolume : 0.5;
        await setVolume(volumeToRestore);
      }
    } catch (err) {
      console.error('Failed to toggle mute:', err);
      setIsMuted(!newMuted); // Revert on error
    }
  }, [isMuted, currentVolume, previousVolume, setVolume]);

  const displayVolume = isDragging ? dragVolume : currentVolume;
  const volumePercentage = Math.round(displayVolume * 100);

  return (
    <div style={styles.container}>
      {/* Mute button */}
      <button
        onClick={handleMuteToggle}
        disabled={isLoading}
        style={styles.muteButton}
        aria-label={isMuted || displayVolume === 0 ? 'Unmute' : 'Mute'}
        title={isMuted || displayVolume === 0 ? 'Unmute' : 'Mute'}
      >
        <span style={styles.muteIcon}>
          {isMuted || displayVolume === 0 ? '🔇' : displayVolume < 0.5 ? '🔈' : '🔊'}
        </span>
      </button>

      {/* Volume slider */}
      <div style={styles.sliderContainer}>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={displayVolume}
          onChange={handleVolumeChange}
          onMouseUp={handleVolumeRelease}
          onTouchEnd={handleVolumeRelease}
          disabled={isLoading}
          style={{
            ...styles.slider,
            background: `linear-gradient(to right, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.primary} ${displayVolume * 100}%, ${tokens.colors.bg.tertiary} ${displayVolume * 100}%, ${tokens.colors.bg.tertiary} 100%)`,
          }}
          aria-label="Volume"
          title={`Volume: ${volumePercentage}%`}
        />
      </div>

      {/* Volume percentage display */}
      <div style={styles.volumeDisplay}>
        <span style={styles.volumeText}>{volumePercentage}%</span>
      </div>
    </div>
  );
};

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
    width: '100%',
    maxWidth: '300px',
  },

  muteButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '40px',
    padding: tokens.spacing.xs,
    backgroundColor: tokens.colors.bg.primary,
    border: `1px solid ${tokens.colors.border.default}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    color: tokens.colors.text.primary,
    fontSize: '18px',

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

  muteIcon: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  sliderContainer: {
    display: 'flex',
    alignItems: 'center',
    flex: 1,
    minWidth: '80px',
  },

  slider: {
    width: '100%',
    height: '4px',
    cursor: 'pointer',
    appearance: 'none' as const,
    WebkitAppearance: 'none' as const,
    borderRadius: tokens.borderRadius.full,
    border: 'none',
    outline: 'none',
  },

  volumeDisplay: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '45px',
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.secondary,
  },

  volumeText: {
    fontFamily: tokens.typography.fontFamily.monospace,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};

export default VolumeControl;
