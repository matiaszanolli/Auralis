import React, { useCallback } from 'react';
import { tokens } from '@/design-system';

interface PlaybackControlsProps {
  intensity: number;
  isPaused: boolean;
  isStreaming: boolean;
  disabled?: boolean;
  error?: string | null;
  onIntensityChange?: (intensity: number) => void;
  onPlayEnhanced?: () => void;
  onTogglePause?: () => void;
  onStop?: () => void;
  onDismissError?: () => void;
}

export const PlaybackControls = ({
  intensity,
  isPaused,
  isStreaming,
  disabled = false,
  error,
  onIntensityChange,
  onPlayEnhanced,
  onTogglePause,
  onStop,
  onDismissError,
}: PlaybackControlsProps) => {
  const handleIntensityChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = Math.max(0, Math.min(1, parseFloat(e.target.value)));
      onIntensityChange?.(value);
    },
    [onIntensityChange]
  );

  return (
    <>
      {!isStreaming && (
        <div style={styles.intensitySection}>
          <label style={styles.sectionLabel}>
            Intensity: {(intensity * 100).toFixed(0)}%
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={intensity}
            onChange={handleIntensityChange}
            style={styles.intensitySlider}
            disabled={disabled}
            aria-label={`Enhancement intensity: ${(intensity * 100).toFixed(0)}%`}
          />
        </div>
      )}

      <div style={styles.controlRow}>
        {!isStreaming ? (
          <button
            style={{
              ...styles.playButton,
              opacity: disabled ? 0.5 : 1,
              cursor: disabled ? 'not-allowed' : 'pointer',
            }}
            onClick={onPlayEnhanced}
            disabled={disabled}
            title="Play with enhanced audio processing"
          >
            &#x25B6; Play Enhanced
          </button>
        ) : (
          <>
            <button
              style={styles.controlButton}
              onClick={onTogglePause}
              title={isPaused ? 'Resume playback' : 'Pause playback'}
            >
              {isPaused ? '\u25B6 Resume' : '\u23F8 Pause'}
            </button>

            <button
              style={styles.controlButton}
              onClick={onStop}
              title="Stop enhanced playback"
            >
              &#x23F9; Stop
            </button>
          </>
        )}
      </div>

      {error && (
        <div style={styles.errorDisplay}>
          <div style={styles.errorContent}>
            <span style={styles.errorIcon}>&#x26A0;&#xFE0F;</span>
            <div style={styles.errorMessage}>{error}</div>
            <button
              style={styles.errorDismiss}
              onClick={onDismissError}
              title="Dismiss error"
            >
              &#x2715;
            </button>
          </div>
        </div>
      )}
    </>
  );
};

const styles: Record<string, React.CSSProperties> = {
  sectionLabel: {
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.secondary,
    fontFamily: tokens.typography.fontFamily.primary,
  },

  intensitySection: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.sm,
  },

  intensitySlider: {
    width: '100%',
    height: '4px',
    borderRadius: tokens.borderRadius.full,
    backgroundColor: tokens.colors.border.medium,
    cursor: 'pointer',
    appearance: 'none',
    outline: 'none',
  },

  controlRow: {
    display: 'flex',
    gap: tokens.spacing.sm,
    alignItems: 'center',
  },

  playButton: {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
    border: 'none',
    borderRadius: tokens.borderRadius.sm,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.base,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: tokens.transitions.base,
  },

  controlButton: {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,
    border: tokens.glass.subtle.border,
    boxShadow: tokens.glass.subtle.boxShadow,
    color: tokens.colors.text.primary,
    borderRadius: tokens.borderRadius.sm,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.base,
    fontWeight: tokens.typography.fontWeight.medium,
    transition: tokens.transitions.fast,
  },

  errorDisplay: {
    padding: tokens.spacing.md,
    backgroundColor: `${tokens.colors.semantic.error}10`,
    border: `1px solid ${tokens.colors.semantic.error}`,
    borderRadius: tokens.borderRadius.sm,
    display: 'flex',
  },

  errorContent: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  },

  errorIcon: {
    fontSize: tokens.typography.fontSize.lg,
    minWidth: '24px',
  },

  errorMessage: {
    flex: 1,
    fontSize: tokens.typography.fontSize.base,
    color: tokens.colors.semantic.error,
    fontWeight: tokens.typography.fontWeight.medium,
  },

  errorDismiss: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: 'transparent',
    border: 'none',
    color: tokens.colors.semantic.error,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    minWidth: '24px',
    transition: tokens.transitions.fast,
  },
};
