/**
 * EnhancementIdentityLayer - Phase 3: Ambient minimal display
 *
 * Always-visible identity layer showing:
 * - Current preset (icon + label, no menu)
 * - Fingerprint/streaming state (simple indicator)
 * - Mastering confidence (subtle ambient indication)
 *
 * Design: "Ambient, slow, expressive" - not corporate charts
 */

import React, { useMemo } from 'react';
import { tokens } from '@/design-system';
import type { PresetName } from '@/store/slices/playerSlice';

export interface EnhancementIdentityLayerProps {
  /** Currently selected preset */
  selectedPreset: PresetName;

  /** Fingerprint analysis status */
  fingerprintStatus: 'idle' | 'analyzing' | 'complete' | 'error' | 'failed';

  /** Streaming state */
  streamingState: 'idle' | 'buffering' | 'streaming' | 'error' | 'complete';

  /** Streaming progress (0-100) for subtle confidence indicator */
  progress: number;

  /** Click handler to reveal inspection layer */
  onRevealInspection?: () => void;
}

/**
 * Preset info with icon and label
 */
const PRESET_INFO: Record<PresetName, { icon: string; label: string }> = {
  adaptive: { icon: '🔄', label: 'Adaptive' },
  gentle: { icon: '🌿', label: 'Gentle' },
  warm: { icon: '🔥', label: 'Warm' },
  bright: { icon: '✨', label: 'Bright' },
  punchy: { icon: '💥', label: 'Punchy' },
};

/**
 * EnhancementIdentityLayer Component
 *
 * Minimal ambient display - "the system listening to the music"
 */
export const EnhancementIdentityLayer: React.FC<EnhancementIdentityLayerProps> = ({
  selectedPreset,
  fingerprintStatus,
  streamingState,
  progress,
  onRevealInspection,
}) => {
  const preset = PRESET_INFO[selectedPreset];

  /**
   * Get ambient state indicator
   */
  const stateIndicator = useMemo(() => {
    // Fingerprint takes priority (analyzing phase)
    if (fingerprintStatus === 'analyzing') {
      return { icon: '⏳', label: 'Analyzing', color: tokens.colors.semantic.warning };
    }
    if (fingerprintStatus === 'error' || fingerprintStatus === 'failed') {
      return { icon: '⚠️', label: 'Analysis Failed', color: tokens.colors.semantic.error };
    }

    // Streaming states
    if (streamingState === 'buffering') {
      return { icon: '📥', label: 'Buffering', color: tokens.colors.semantic.warning };
    }
    if (streamingState === 'streaming') {
      return { icon: '🎵', label: 'Streaming', color: tokens.colors.semantic.success };
    }
    if (streamingState === 'error') {
      return { icon: '❌', label: 'Error', color: tokens.colors.semantic.error };
    }
    if (streamingState === 'complete') {
      return { icon: '✅', label: 'Complete', color: tokens.colors.semantic.success };
    }

    // Default idle state (fingerprint complete, no streaming)
    if (fingerprintStatus === 'complete') {
      return { icon: '✓', label: 'Ready', color: tokens.colors.accent.primary };
    }

    return { icon: '⏸️', label: 'Idle', color: tokens.colors.text.secondary };
  }, [fingerprintStatus, streamingState]);

  return (
    <div
      style={styles.container}
      onClick={onRevealInspection}
      role="button"
      tabIndex={0}
      title="Click for detailed controls"
    >
      {/* Preset Display - Icon + Label Only */}
      <div style={styles.presetSection}>
        <div style={styles.presetIcon}>{preset.icon}</div>
        <div style={styles.presetLabel}>{preset.label}</div>
      </div>

      {/* State Indicator - Ambient Minimal */}
      <div style={styles.stateSection}>
        <div style={{ ...styles.stateIcon, color: stateIndicator.color }}>
          {stateIndicator.icon}
        </div>
        <div style={{ ...styles.stateLabel, color: stateIndicator.color }}>
          {stateIndicator.label}
        </div>
      </div>

      {/* Confidence Indicator - Subtle Progress Bar (only when active) */}
      {(streamingState === 'streaming' || streamingState === 'buffering') && (
        <div style={styles.confidenceContainer}>
          <div
            style={{
              ...styles.confidenceBar,
              width: `${Math.min(progress, 100)}%`,
              backgroundColor: stateIndicator.color,
            }}
          />
        </div>
      )}
    </div>
  );
};

/**
 * Styles - Ambient, minimal, expressive (Phase 3)
 */
const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,                               // 12px - organic spacing
    padding: tokens.spacing.lg,                           // 16px
    borderRadius: tokens.borderRadius.md,                 // 12px
    cursor: 'pointer',
    transition: tokens.transitions.base,                  // 400ms smooth

    // Subtle glass effect - calm by default (Phase 3: Identity layer)
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 24px blur
    border: tokens.glass.subtle.border,                   // 15% white opacity
    boxShadow: 'none',                                    // No shadow - ambient, not elevated

    '&:hover': {
      background: tokens.glass.medium.background,         // Slight intensification
      boxShadow: tokens.glass.subtle.boxShadow,          // Subtle depth appears
    },
  },

  presetSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,                               // 12px
  },

  presetIcon: {
    fontSize: tokens.typography.fontSize['2xl'],          // 32px - prominent but not loud
    minWidth: '40px',
    textAlign: 'center' as const,
  },

  presetLabel: {
    fontSize: tokens.typography.fontSize.xl,              // 24px - identity text
    fontWeight: tokens.typography.fontWeight.semibold,
    color: tokens.colors.text.primary,
    fontFamily: tokens.typography.fontFamily.header,      // Manrope for identity
  },

  stateSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,                               // 8px - tight cluster
    opacity: 0.85,                                        // Slightly muted (ambient)
  },

  stateIcon: {
    fontSize: tokens.typography.fontSize.base,            // 16px
    minWidth: '20px',
    textAlign: 'center' as const,
  },

  stateLabel: {
    fontSize: tokens.typography.fontSize.sm,              // 13px
    fontWeight: tokens.typography.fontWeight.medium,
    fontFamily: tokens.typography.fontFamily.primary,     // Inter for info
  },

  confidenceContainer: {
    width: '100%',
    height: '2px',                                        // Subtle 2px bar
    backgroundColor: tokens.colors.border.light,
    borderRadius: tokens.borderRadius.full,               // 9999px pill
    overflow: 'hidden',
    opacity: 0.6,                                         // Ambient, not prominent
  },

  confidenceBar: {
    height: '100%',
    transition: `width ${tokens.transitions.slow}`,       // 500-600ms slow state change
    borderRadius: tokens.borderRadius.full,
  },
};

export default EnhancementIdentityLayer;
