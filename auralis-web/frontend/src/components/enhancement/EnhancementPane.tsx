/**
 * EnhancementPane - Phase 3: Identity/Inspection Layer Orchestrator
 *
 * Manages the two-layer enhancement UI:
 * - IdentityLayer: Always visible, ambient minimal display
 * - InspectionLayer: Revealed on interaction (click), detailed controls
 *
 * Interaction model:
 * - Default: Only IdentityLayer visible
 * - Click IdentityLayer or "Details" button → InspectionLayer appears with fade-in
 * - Click "Close" or outside InspectionLayer → InspectionLayer fades out
 *
 * Design: "Ambient by default, expressive by interaction"
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { tokens } from '@/design-system';
import { EnhancementIdentityLayer } from './EnhancementIdentityLayer';
import { EnhancementInspectionLayer } from './EnhancementInspectionLayer';
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';
import type { PresetName } from '@/store/slices/playerSlice';

export interface EnhancementPaneProps {
  /** Track ID to play enhanced */
  trackId: number;

  /** Callback when playback starts */
  onPlayEnhanced?: (preset: PresetName, intensity: number) => void;

  /** Disable controls */
  disabled?: boolean;
}

/**
 * EnhancementPane Component
 *
 * Orchestrates IdentityLayer and InspectionLayer with show/hide logic
 */
export const EnhancementPane: React.FC<EnhancementPaneProps> = ({
  trackId,
  onPlayEnhanced,
  disabled = false,
}) => {
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
  const [showInspection, setShowInspection] = useState(false);

  // Ref for click-outside detection
  const inspectionRef = useRef<HTMLDivElement>(null);

  /**
   * Handle click outside InspectionLayer to close it
   */
  useEffect(() => {
    if (!showInspection) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        inspectionRef.current &&
        !inspectionRef.current.contains(event.target as Node)
      ) {
        setShowInspection(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showInspection]);

  /**
   * Handle reveal inspection layer (from IdentityLayer click)
   */
  const handleRevealInspection = useCallback(() => {
    setShowInspection(true);
  }, []);

  /**
   * Handle close inspection layer
   */
  const handleCloseInspection = useCallback(() => {
    setShowInspection(false);
  }, []);

  /**
   * Handle play enhanced button click
   */
  const handlePlayEnhanced = useCallback(async () => {
    try {
      await playEnhanced(trackId, selectedPreset, intensity);
      onPlayEnhanced?.(selectedPreset, intensity);
    } catch (err) {
      console.error('[EnhancementPane] Play failed:', err);
    }
  }, [trackId, selectedPreset, intensity, playEnhanced, onPlayEnhanced]);

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
   * Handle error dismissal
   */
  const handleDismissError = useCallback(() => {
    stopPlayback();
  }, [stopPlayback]);

  return (
    <div style={styles.container}>
      {/* Identity Layer - Always Visible */}
      <EnhancementIdentityLayer
        selectedPreset={selectedPreset}
        fingerprintStatus={fingerprintStatus}
        streamingState={streamingState}
        progress={streamingProgress}
        onRevealInspection={handleRevealInspection}
      />

      {/* Inspection Layer - Revealed on Interaction */}
      {showInspection && (
        <div
          ref={inspectionRef}
          style={{
            ...styles.inspectionContainer,
            animation: 'fadeIn 300ms cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          {/* Close Button */}
          <button
            style={styles.closeButton}
            onClick={handleCloseInspection}
            title="Close detailed controls"
          >
            ✕
          </button>

          <EnhancementInspectionLayer
            selectedPreset={selectedPreset}
            intensity={intensity}
            fingerprintStatus={fingerprintStatus}
            fingerprintMessage={fingerprintMessage}
            streamingState={streamingState}
            progress={streamingProgress}
            processedChunks={processedChunks}
            totalChunks={totalChunks}
            currentTime={currentTime}
            isPaused={isPaused}
            error={error}
            isStreaming={isStreaming}
            disabled={disabled}
            onPresetChange={setSelectedPreset}
            onIntensityChange={setIntensity}
            onPlayEnhanced={handlePlayEnhanced}
            onTogglePause={handleTogglePause}
            onStop={stopPlayback}
            onDismissError={handleDismissError}
          />
        </div>
      )}
    </div>
  );
};

/**
 * Styles - Layer orchestration (Phase 3)
 */
const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,                               // 12px - organic spacing between layers
    position: 'relative',                                 // For absolute positioning of InspectionLayer
  },

  inspectionContainer: {
    position: 'relative',                                 // For close button positioning
    marginTop: tokens.spacing.md,                         // 12px - section spacing
  },

  closeButton: {
    position: 'absolute',
    top: tokens.spacing.sm,                               // 8px from top
    right: tokens.spacing.sm,                             // 8px from right
    zIndex: 10,                                           // Above InspectionLayer content

    width: '32px',
    height: '32px',
    padding: 0,

    // Glass effect for close button (Design Language v1.2.0 §4.2)
    background: tokens.glass.subtle.background,
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 24px blur
    border: tokens.glass.subtle.border,                   // 15% white opacity
    boxShadow: tokens.glass.subtle.boxShadow,

    borderRadius: tokens.borderRadius.full,               // 9999px - perfect circle
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.base,            // 16px
    color: tokens.colors.text.secondary,
    transition: tokens.transitions.fast,                  // 150ms hover

    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
};

// Add CSS animation keyframes for fade-in
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(-8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;
document.head.appendChild(styleSheet);

export default EnhancementPane;
