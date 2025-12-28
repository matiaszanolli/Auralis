/**
 * Enhanced Playback Controls Component
 *
 * UI controls for triggering and managing WebSocket-based PCM audio streaming.
 * Includes preset selection, intensity control, and real-time status display.
 *
 * Features:
 * - Play Enhanced button with preset selector
 * - Intensity slider (0.0-1.0)
 * - Real-time streaming status indicator
 * - Pause/stop buttons during streaming
 * - Error message display
 */

import React, { useCallback, useState, useMemo } from 'react';
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';
import { tokens } from '@/design-system';
import type { PresetName } from '@/store/slices/playerSlice';

/**
 * Props for EnhancedPlaybackControls component
 */
export interface EnhancedPlaybackControlsProps {
  /** Track ID to play enhanced */
  trackId: number;

  /** Callback when playback starts */
  onPlayEnhanced?: (preset: PresetName, intensity: number) => void;

  /** Disable controls */
  disabled?: boolean;

  /** Show detailed status (default: false) */
  showStatus?: boolean;
}

/**
 * Preset information for display
 */
interface PresetInfo {
  name: PresetName;
  label: string;
  description: string;
  icon: string;
}

const PRESETS: Record<PresetName, PresetInfo> = {
  adaptive: {
    name: 'adaptive',
    label: 'Adaptive',
    description: 'Analyzes content and adjusts in real-time',
    icon: '🔄',
  },
  gentle: {
    name: 'gentle',
    label: 'Gentle',
    description: 'Subtle enhancement, preserves original character',
    icon: '🌿',
  },
  warm: {
    name: 'warm',
    label: 'Warm',
    description: 'Enhanced mid-range warmth and presence',
    icon: '🔥',
  },
  bright: {
    name: 'bright',
    label: 'Bright',
    description: 'Enhanced high-end clarity and definition',
    icon: '✨',
  },
  punchy: {
    name: 'punchy',
    label: 'Punchy',
    description: 'Aggressive dynamics and impact',
    icon: '💥',
  },
};

/**
 * EnhancedPlaybackControls Component
 *
 * Main interface for initiating enhanced audio playback streaming.
 */
export const EnhancedPlaybackControls: React.FC<
  EnhancedPlaybackControlsProps
> = ({ trackId, onPlayEnhanced, disabled = false, showStatus = true }) => {
  const {
    playEnhanced,
    stopPlayback,
    pausePlayback,
    resumePlayback,
    isStreaming,
    streamingState,
    streamingProgress,
    processedChunks,
    totalChunks,
    error,
    currentTime,
    isPaused,
    fingerprintStatus,
    fingerprintMessage,
  } = usePlayEnhanced();

  // Local state for controls
  const [selectedPreset, setSelectedPreset] = useState<PresetName>('adaptive');
  const [intensity, setIntensity] = useState(1.0);
  const [showPresetMenu, setShowPresetMenu] = useState(false);

  /**
   * Handle play enhanced button click
   */
  const handlePlayEnhanced = useCallback(async () => {
    try {
      await playEnhanced(trackId, selectedPreset, intensity);
      onPlayEnhanced?.(selectedPreset, intensity);
      setShowPresetMenu(false);
    } catch (err) {
      console.error('[EnhancedPlaybackControls] Play failed:', err);
    }
  }, [trackId, selectedPreset, intensity, playEnhanced, onPlayEnhanced]);

  /**
   * Handle intensity slider change
   */
  const handleIntensityChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = Math.max(0, Math.min(1, parseFloat(e.target.value)));
      setIntensity(value);
    },
    []
  );

  /**
   * Handle pause toggle
   */
  const handleTogglePause = useCallback(() => {
    if (isPaused) {
      resumePlayback();
    } else {
      pausePlayback();
    }
  }, [isPaused, pausePlayback, resumePlayback]);

  /**
   * Format duration from seconds
   */
  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  /**
   * Calculate estimated remaining time
   */
  const estimatedRemaining = useMemo(() => {
    if (!isStreaming || totalChunks === 0) return null;
    const remainingChunks = totalChunks - processedChunks;
    // Rough estimate: assume ~100ms per chunk
    return remainingChunks * 0.1;
  }, [isStreaming, totalChunks, processedChunks]);

  /**
   * Get status color based on streaming state
   */
  const statusColor = useMemo(() => {
    switch (streamingState) {
      case 'buffering':
        return tokens.colors.semantic.warning;
      case 'streaming':
        return tokens.colors.semantic.success;
      case 'error':
        return tokens.colors.semantic.error;
      case 'complete':
        return tokens.colors.semantic.success;
      default:
        return tokens.colors.text.secondary;
    }
  }, [streamingState]);

  /**
   * Get status label
   */
  const statusLabel = useMemo(() => {
    switch (streamingState) {
      case 'buffering':
        return '📥 Buffering...';
      case 'streaming':
        return '🎵 Streaming';
      case 'error':
        return '❌ Error';
      case 'complete':
        return '✅ Complete';
      default:
        return '⏸️ Ready';
    }
  }, [streamingState]);

  return (
    <div style={styles.container}>
      {/* Fingerprint Analysis Indicator */}
      {fingerprintStatus !== 'idle' && (
        <div
          style={{
            ...styles.fingerprintIndicator,
            backgroundColor:
              fingerprintStatus === 'analyzing'
                ? tokens.colors.semantic.warning + '15'
                : fingerprintStatus === 'complete'
                  ? tokens.colors.semantic.success + '15'
                  : fingerprintStatus === 'error' || fingerprintStatus === 'failed'
                    ? tokens.colors.semantic.error + '15'
                    : 'transparent',
            borderColor:
              fingerprintStatus === 'analyzing'
                ? tokens.colors.semantic.warning
                : fingerprintStatus === 'complete'
                  ? tokens.colors.semantic.success
                  : tokens.colors.semantic.error,
          }}
        >
          <div style={styles.fingerprintContent}>
            {fingerprintStatus === 'analyzing' && (
              <>
                <div style={styles.spinner} />
                <span style={styles.fingerprintText}>Analyzing audio for optimal mastering...</span>
              </>
            )}
            {fingerprintStatus === 'complete' && (
              <>
                <span style={{ fontSize: '16px' }}>✅</span>
                <span style={styles.fingerprintText}>Audio analysis complete</span>
              </>
            )}
            {(fingerprintStatus === 'error' || fingerprintStatus === 'failed') && (
              <>
                <span style={{ fontSize: '16px' }}>⚠️</span>
                <span style={{ ...styles.fingerprintText, color: tokens.colors.semantic.error }}>
                  {fingerprintMessage || 'Audio analysis failed'}
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Main Control Button Row */}
      <div style={styles.controlRow}>
        {!isStreaming ? (
          <>
            {/* Play Enhanced Button with Preset Menu */}
            <div style={styles.playButtonGroup}>
              <button
                style={{
                  ...styles.playButton,
                  opacity: disabled ? 0.5 : 1,
                  cursor: disabled ? 'not-allowed' : 'pointer',
                }}
                onClick={handlePlayEnhanced}
                disabled={disabled || !trackId}
                title="Play with enhanced audio processing"
              >
                ▶ Play Enhanced
              </button>

              <button
                style={{
                  ...styles.presetMenuButton,
                  opacity: disabled ? 0.5 : 1,
                }}
                onClick={() => setShowPresetMenu(!showPresetMenu)}
                disabled={disabled}
                title="Select enhancement preset"
              >
                ▼
              </button>
            </div>

            {/* Preset Menu */}
            {showPresetMenu && (
              <div style={styles.presetMenu}>
                {Object.values(PRESETS).map((preset) => (
                  <div
                    key={preset.name}
                    style={{
                      ...styles.presetItem,
                      backgroundColor:
                        selectedPreset === preset.name
                          ? tokens.colors.accent.primary + '20'
                          : 'transparent',
                      cursor: 'pointer',
                    }}
                    onClick={() => {
                      setSelectedPreset(preset.name);
                      setShowPresetMenu(false);
                    }}
                  >
                    <div style={styles.presetIcon}>{preset.icon}</div>
                    <div>
                      <div style={styles.presetLabel}>{preset.label}</div>
                      <div style={styles.presetDescription}>
                        {preset.description}
                      </div>
                    </div>
                    {selectedPreset === preset.name && (
                      <div style={styles.presetCheckmark}>✓</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            {/* Streaming Control Buttons */}
            <button
              style={styles.controlButton}
              onClick={handleTogglePause}
              title={isPaused ? 'Resume playback' : 'Pause playback'}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>

            <button
              style={styles.controlButton}
              onClick={stopPlayback}
              title="Stop enhanced playback"
            >
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      {/* Intensity Control */}
      {!isStreaming && (
        <div style={styles.intensityControl}>
          <label style={styles.intensityLabel}>
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
            title="Adjust enhancement intensity (0-100%)"
          />
        </div>
      )}

      {/* Status Display */}
      {showStatus && isStreaming && (
        <div
          style={{
            ...styles.statusDisplay,
            borderLeftColor: statusColor,
          }}
        >
          <div style={styles.statusRow}>
            <span style={{ color: statusColor }}>{statusLabel}</span>
            <span style={styles.statusMetrics}>
              {processedChunks}/{totalChunks} chunks
              {estimatedRemaining && (
                <> (~{formatTime(estimatedRemaining)} left)</>
              )}
            </span>
          </div>

          {/* Progress Bar */}
          <div style={styles.progressBarContainer}>
            <div
              style={{
                ...styles.progressBar,
                width: `${Math.min(streamingProgress, 100)}%`,
                backgroundColor:
                  streamingState === 'buffering'
                    ? tokens.colors.semantic.warning
                    : tokens.colors.semantic.success,
              }}
            />
          </div>

          {/* Time Display */}
          <div style={styles.timeDisplay}>
            {formatTime(currentTime)}
            {estimatedRemaining && (
              <> / ~{formatTime(currentTime + estimatedRemaining)}</>
            )}
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div style={styles.errorDisplay}>
          <div style={styles.errorContent}>
            <span style={styles.errorIcon}>⚠️</span>
            <div style={styles.errorMessage}>{error}</div>
            <button
              style={styles.errorDismiss}
              onClick={() => {
                // Error is in Redux, components listening to it can clear it
                stopPlayback();
              }}
              title="Dismiss error"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Styles for EnhancedPlaybackControls
 */
const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,

    // Glass effect for container (Design Language v1.2.0 §4.2)
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 20px blur
    border: tokens.glass.subtle.border,                   // 10% white opacity
    boxShadow: tokens.glass.subtle.boxShadow,
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic
  },

  controlRow: {
    display: 'flex',
    gap: tokens.spacing.sm,
    alignItems: 'center',
    position: 'relative',
  },

  playButtonGroup: {
    display: 'flex',
    gap: 0,
    flex: 1,
  },

  playButton: {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
    border: 'none',
    borderRadius: `${tokens.borderRadius.sm} 0 0 ${tokens.borderRadius.sm}`,  // 8px left corners
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.base,              // 13px
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: tokens.transitions.base,
  },

  presetMenuButton: {
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
    border: 'none',
    borderRadius: `0 ${tokens.borderRadius.sm} ${tokens.borderRadius.sm} 0`,  // 8px right corners
    borderLeft: `1px solid ${tokens.colors.accent.primary}66`,  // 40% opacity separator
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,                // 11px
    transition: tokens.transitions.base,
  },

  presetMenu: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    marginTop: tokens.spacing.xs,

    // Glass effect for dropdown menu (Design Language v1.2.0 §4.2)
    background: tokens.glass.medium.background,
    backdropFilter: tokens.glass.medium.backdropFilter,   // 28px blur
    border: tokens.glass.medium.border,                   // 12% white opacity
    boxShadow: tokens.glass.medium.boxShadow,
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic

    zIndex: 1000,
    maxHeight: '300px',                                   // Vertical scroll limit
    overflowY: 'auto',
  },

  presetItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    cursor: 'pointer',
    transition: tokens.transitions.fast,                  // 150ms hover
  },

  presetIcon: {
    fontSize: '20px',
    minWidth: '24px',
    textAlign: 'center',
  },

  presetLabel: {
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.base,             // 13px
    color: tokens.colors.text.primary,
  },

  presetDescription: {
    fontSize: tokens.typography.fontSize.sm,               // 11px
    color: tokens.colors.text.secondary,
    marginTop: tokens.spacing.xs,                          // 4px - tight spacing
  },

  presetCheckmark: {
    marginLeft: 'auto',
    color: tokens.colors.semantic.success,
    fontSize: '16px',
    fontWeight: 'bold',
  },

  controlButton: {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,

    // Glass effect for control buttons (Design Language v1.2.0 §4.2)
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 20px blur
    border: tokens.glass.subtle.border,                   // 10% white opacity
    boxShadow: tokens.glass.subtle.boxShadow,

    color: tokens.colors.text.primary,
    borderRadius: tokens.borderRadius.sm,                 // 8px
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.base,            // 13px
    fontWeight: tokens.typography.fontWeight.medium,
    transition: tokens.transitions.fast,                  // 150ms hover
  },

  intensityControl: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.xs,
  },

  intensityLabel: {
    fontSize: '13px',
    fontWeight: 500,
    color: tokens.colors.text.primary,
  },

  intensitySlider: {
    width: '100%',
    height: '4px',                                        // Track height
    borderRadius: tokens.borderRadius.full,               // 9999px - pill shape
    backgroundColor: tokens.colors.border.medium,
    cursor: 'pointer',
    appearance: 'none',
    outline: 'none',
  },

  statusDisplay: {
    padding: tokens.spacing.md,

    // Glass effect for status display (Design Language v1.2.0 §4.2)
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 20px blur
    border: tokens.glass.subtle.border,                   // 10% white opacity
    boxShadow: tokens.glass.subtle.boxShadow,
    borderLeft: `3px solid ${tokens.colors.semantic.success}`,  // Status accent bar

    borderRadius: tokens.borderRadius.sm,                 // 8px
    fontSize: tokens.typography.fontSize.sm,              // 11px
    color: tokens.colors.text.primary,
  },

  statusRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: tokens.spacing.sm,
    fontWeight: 500,
  },

  statusMetrics: {
    color: tokens.colors.text.secondary,
    fontSize: '11px',
  },

  progressBarContainer: {
    width: '100%',
    height: '4px',
    backgroundColor: tokens.colors.border.medium,
    borderRadius: tokens.borderRadius.full,               // 9999px - pill shape
    overflow: 'hidden',
    marginBottom: tokens.spacing.xs,
  },

  progressBar: {
    height: '100%',
    backgroundColor: tokens.colors.accent.primary,
    transition: `width ${tokens.transitions.slow}`,       // 400-600ms slow state change
  },

  timeDisplay: {
    color: tokens.colors.text.secondary,
    fontSize: '11px',
  },

  errorDisplay: {
    padding: tokens.spacing.md,
    backgroundColor: `${tokens.colors.semantic.error}10`,  // 10% error tint
    border: `1px solid ${tokens.colors.semantic.error}`,
    borderRadius: tokens.borderRadius.sm,                 // 8px
    display: 'flex',
  },

  errorContent: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  },

  errorIcon: {
    fontSize: tokens.typography.fontSize.lg,              // 16px
    minWidth: '24px',
  },

  errorMessage: {
    flex: 1,
    fontSize: tokens.typography.fontSize.base,            // 13px
    color: tokens.colors.semantic.error,
    fontWeight: tokens.typography.fontWeight.medium,
  },

  errorDismiss: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,  // 4px 8px
    backgroundColor: 'transparent',
    border: 'none',
    color: tokens.colors.semantic.error,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,              // 16px
    minWidth: '24px',
    transition: tokens.transitions.fast,                  // 150ms hover
  },

  fingerprintIndicator: {
    padding: tokens.spacing.md,
    borderRadius: tokens.borderRadius.sm,                 // 8px
    border: `1px solid`,                                  // Color set dynamically
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '44px',
  },

  fingerprintContent: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  },

  spinner: {
    width: '16px',
    height: '16px',
    border: `2px solid ${tokens.colors.semantic.warning}40`,  // 40% opacity ring
    borderTopColor: tokens.colors.semantic.warning,
    borderRadius: tokens.borderRadius.full,               // 9999px - perfect circle
    animation: 'spin 1s linear infinite',
  },

  fingerprintText: {
    fontSize: tokens.typography.fontSize.base,            // 13px
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.primary,
  },
};

// Add CSS animation keyframes
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(styleSheet);

export default EnhancedPlaybackControls;
