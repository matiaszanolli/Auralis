/**
 * EnhancementInspectionLayer - Phase 3: Detailed controls on interaction
 *
 * Revealed on-demand layer showing:
 * - Full preset dropdown menu (5 options with descriptions)
 * - Intensity slider with percentage label
 * - Detailed streaming progress (chunks, time, progress bar)
 * - Playback control buttons (pause/stop)
 * - Error message display
 *
 * Design: "Inspection, not settings" - glass effect, detailed but not overwhelming
 */

import React, { useCallback, useMemo } from 'react';
import { tokens } from '@/design-system';
import type { PresetName } from '@/store/slices/playerSlice';

export interface EnhancementInspectionLayerProps {
  /** Currently selected preset */
  selectedPreset: PresetName;

  /** Intensity value (0.0-1.0) */
  intensity: number;

  /** Fingerprint analysis status */
  fingerprintStatus: 'idle' | 'analyzing' | 'complete' | 'error' | 'failed';

  /** Fingerprint message (for errors) */
  fingerprintMessage?: string;

  /** Streaming state */
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';

  /** Streaming progress (0-100) */
  progress: number;

  /** Processed chunks count */
  processedChunks: number;

  /** Total chunks count */
  totalChunks: number;

  /** Current playback time (seconds) */
  currentTime: number;

  /** Is playback paused? */
  isPaused: boolean;

  /** Error message (if any) */
  error?: string;

  /** Is currently streaming? */
  isStreaming: boolean;

  /** Disabled state */
  disabled?: boolean;

  /** Callback when preset changes */
  onPresetChange?: (preset: PresetName) => void;

  /** Callback when intensity changes */
  onIntensityChange?: (intensity: number) => void;

  /** Callback when play enhanced is triggered */
  onPlayEnhanced?: () => void;

  /** Callback when pause/resume is triggered */
  onTogglePause?: () => void;

  /** Callback when stop is triggered */
  onStop?: () => void;

  /** Callback when error is dismissed */
  onDismissError?: () => void;
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
 * EnhancementInspectionLayer Component
 *
 * Detailed controls - revealed on interaction with IdentityLayer
 */
export const EnhancementInspectionLayer: React.FC<EnhancementInspectionLayerProps> = ({
  selectedPreset,
  intensity,
  fingerprintStatus,
  fingerprintMessage,
  streamingState,
  progress,
  processedChunks,
  totalChunks,
  currentTime,
  isPaused,
  error,
  isStreaming,
  disabled = false,
  onPresetChange,
  onIntensityChange,
  onPlayEnhanced,
  onTogglePause,
  onStop,
  onDismissError,
}) => {
  const [showPresetMenu, setShowPresetMenu] = React.useState(false);

  /**
   * Handle intensity slider change
   */
  const handleIntensityChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = Math.max(0, Math.min(1, parseFloat(e.target.value)));
      onIntensityChange?.(value);
    },
    [onIntensityChange]
  );

  /**
   * Handle preset selection
   */
  const handlePresetSelect = useCallback(
    (preset: PresetName) => {
      onPresetChange?.(preset);
      setShowPresetMenu(false);
    },
    [onPresetChange]
  );

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

      {/* Preset Selection */}
      <div style={styles.presetSection}>
        <label style={styles.sectionLabel}>Preset</label>
        <div style={styles.presetSelectorContainer}>
          <button
            style={{
              ...styles.presetSelector,
              opacity: disabled ? 0.5 : 1,
              cursor: disabled ? 'not-allowed' : 'pointer',
            }}
            onClick={() => !disabled && setShowPresetMenu(!showPresetMenu)}
            disabled={disabled}
            title="Select enhancement preset"
          >
            <span style={styles.presetIcon}>{PRESETS[selectedPreset].icon}</span>
            <span style={styles.presetLabel}>{PRESETS[selectedPreset].label}</span>
            <span style={styles.presetDropdownIcon}>▼</span>
          </button>

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
                  onClick={() => handlePresetSelect(preset.name)}
                >
                  <div style={styles.presetIcon}>{preset.icon}</div>
                  <div>
                    <div style={styles.presetItemLabel}>{preset.label}</div>
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
        </div>
      </div>

      {/* Intensity Control */}
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
            title="Adjust enhancement intensity (0-100%)"
          />
        </div>
      )}

      {/* Main Control Buttons */}
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
            ▶ Play Enhanced
          </button>
        ) : (
          <>
            <button
              style={styles.controlButton}
              onClick={onTogglePause}
              title={isPaused ? 'Resume playback' : 'Pause playback'}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>

            <button
              style={styles.controlButton}
              onClick={onStop}
              title="Stop enhanced playback"
            >
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      {/* Streaming Status Display */}
      {isStreaming && (
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
                width: `${Math.min(progress, 100)}%`,
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
              onClick={onDismissError}
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
 * Styles - Glass effect, detailed controls (Phase 3)
 */
const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,                               // 12px - organic spacing
    padding: tokens.spacing.lg,                           // 16px
    borderRadius: tokens.borderRadius.md,                 // 12px

    // Medium glass effect - detailed inspection layer (Phase 3: Inspection layer)
    background: tokens.glass.medium.background,
    backdropFilter: tokens.glass.medium.backdropFilter,   // 32px blur
    border: tokens.glass.medium.border,                   // 18% white opacity
    boxShadow: tokens.glass.medium.boxShadow,             // Deeper shadow + inner glow
  },

  presetSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.sm,                               // 8px
  },

  sectionLabel: {
    fontSize: tokens.typography.fontSize.sm,              // 13px
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.secondary,
    fontFamily: tokens.typography.fontFamily.primary,     // Inter for labels
  },

  presetSelectorContainer: {
    position: 'relative',
  },

  presetSelector: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,                               // 12px
    padding: tokens.spacing.md,                           // 12px
    backgroundColor: tokens.colors.bg.secondary,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.sm,                 // 8px
    cursor: 'pointer',
    transition: tokens.transitions.fast,                  // 150ms hover
    fontSize: tokens.typography.fontSize.base,            // 16px
    fontWeight: tokens.typography.fontWeight.medium,
    color: tokens.colors.text.primary,
  },

  presetDropdownIcon: {
    marginLeft: 'auto',
    fontSize: tokens.typography.fontSize.sm,              // 13px
    color: tokens.colors.text.secondary,
  },

  presetMenu: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    marginTop: tokens.spacing.xs,                         // 4px

    // Glass effect for dropdown menu (Design Language v1.2.0 §4.2)
    background: tokens.glass.medium.background,
    backdropFilter: tokens.glass.medium.backdropFilter,   // 32px blur
    border: tokens.glass.medium.border,                   // 18% white opacity
    boxShadow: tokens.glass.medium.boxShadow,
    borderRadius: tokens.borderRadius.md,                 // 12px

    zIndex: 1000,
    maxHeight: '300px',                                   // Vertical scroll limit
    overflowY: 'auto',
  },

  presetItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,                               // 12px
    padding: tokens.spacing.md,                           // 12px
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    cursor: 'pointer',
    transition: tokens.transitions.fast,                  // 150ms hover
  },

  presetIcon: {
    fontSize: '20px',
    minWidth: '24px',
    textAlign: 'center' as const,
  },

  presetLabel: {
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.base,            // 16px
    color: tokens.colors.text.primary,
  },

  presetItemLabel: {
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.base,            // 16px
    color: tokens.colors.text.primary,
  },

  presetDescription: {
    fontSize: tokens.typography.fontSize.sm,              // 13px
    color: tokens.colors.text.secondary,
    marginTop: tokens.spacing.xs,                         // 4px
  },

  presetCheckmark: {
    marginLeft: 'auto',
    color: tokens.colors.semantic.success,
    fontSize: '16px',
    fontWeight: 'bold',
  },

  intensitySection: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.sm,                               // 8px
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

  controlRow: {
    display: 'flex',
    gap: tokens.spacing.sm,                               // 8px
    alignItems: 'center',
  },

  playButton: {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
    border: 'none',
    borderRadius: tokens.borderRadius.sm,                 // 8px
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.base,            // 16px
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: tokens.transitions.base,                  // 400ms smooth
  },

  controlButton: {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,

    // Glass effect for control buttons (Design Language v1.2.0 §4.2)
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 24px blur
    border: tokens.glass.subtle.border,                   // 15% white opacity
    boxShadow: tokens.glass.subtle.boxShadow,

    color: tokens.colors.text.primary,
    borderRadius: tokens.borderRadius.sm,                 // 8px
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.base,            // 16px
    fontWeight: tokens.typography.fontWeight.medium,
    transition: tokens.transitions.fast,                  // 150ms hover
  },

  statusDisplay: {
    padding: tokens.spacing.md,                           // 12px

    // Glass effect for status display (Design Language v1.2.0 §4.2)
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 24px blur
    border: tokens.glass.subtle.border,                   // 15% white opacity
    boxShadow: tokens.glass.subtle.boxShadow,
    borderLeft: `3px solid ${tokens.colors.semantic.success}`,  // Status accent bar

    borderRadius: tokens.borderRadius.sm,                 // 8px
    fontSize: tokens.typography.fontSize.sm,              // 13px
    color: tokens.colors.text.primary,
  },

  statusRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: tokens.spacing.sm,                      // 8px
    fontWeight: 500,
  },

  statusMetrics: {
    color: tokens.colors.text.secondary,
    fontSize: tokens.typography.fontSize.sm,              // 13px
  },

  progressBarContainer: {
    width: '100%',
    height: '4px',
    backgroundColor: tokens.colors.border.medium,
    borderRadius: tokens.borderRadius.full,               // 9999px - pill shape
    overflow: 'hidden',
    marginBottom: tokens.spacing.xs,                      // 4px
  },

  progressBar: {
    height: '100%',
    backgroundColor: tokens.colors.accent.primary,
    transition: `width ${tokens.transitions.slow}`,       // 500-600ms slow state change
  },

  timeDisplay: {
    color: tokens.colors.text.secondary,
    fontSize: tokens.typography.fontSize.sm,              // 13px
  },

  errorDisplay: {
    padding: tokens.spacing.md,                           // 12px
    backgroundColor: `${tokens.colors.semantic.error}10`,  // 10% error tint
    border: `1px solid ${tokens.colors.semantic.error}`,
    borderRadius: tokens.borderRadius.sm,                 // 8px
    display: 'flex',
  },

  errorContent: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,                               // 8px
  },

  errorIcon: {
    fontSize: tokens.typography.fontSize.lg,              // 18px
    minWidth: '24px',
  },

  errorMessage: {
    flex: 1,
    fontSize: tokens.typography.fontSize.base,            // 16px
    color: tokens.colors.semantic.error,
    fontWeight: tokens.typography.fontWeight.medium,
  },

  errorDismiss: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,  // 4px 8px
    backgroundColor: 'transparent',
    border: 'none',
    color: tokens.colors.semantic.error,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,              // 18px
    minWidth: '24px',
    transition: tokens.transitions.fast,                  // 150ms hover
  },

  fingerprintIndicator: {
    padding: tokens.spacing.md,                           // 12px
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
    gap: tokens.spacing.sm,                               // 8px
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
    fontSize: tokens.typography.fontSize.base,            // 16px
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

export default EnhancementInspectionLayer;
