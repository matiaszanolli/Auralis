/**
 * Player Enhancement Panel Component
 *
 * Integrates enhanced playback controls with streaming progress and error handling.
 * Provides a unified interface for triggering and managing WebSocket PCM streaming.
 *
 * Features:
 * - Enhanced playback controls (play with preset selection)
 * - Real-time streaming progress visualization
 * - Error handling with recovery options
 * - Seamless integration with existing player
 *
 * Used in: Player.tsx right section for easy access to enhanced playback
 */

import React, { useMemo, useCallback, useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { playerSelectors } from '@/store/selectors';
import type { RootState } from '@/store';
import { tokens } from '@/design-system';

// Playback hooks
import { usePlayNormal } from '@/hooks/enhancement/usePlayNormal';

/**
 * Playback control functions passed from parent Player component
 */
export interface PlaybackControls {
  /** Start enhanced playback */
  playEnhanced: (trackId: number, preset: string, intensity: number) => Promise<void>;
  /** Stop playback */
  stopPlayback: () => void;
  /** Pause playback */
  pausePlayback: () => void;
  /** Resume playback */
  resumePlayback: () => void;
  /** Whether currently streaming */
  isStreaming: boolean;
  /** Whether playback is paused */
  isPaused: boolean;
}

/**
 * Props for PlayerEnhancementPanel
 */
export interface PlayerEnhancementPanelProps {
  /** Current track ID */
  trackId?: number;

  /** Whether to show the panel (hide if no track) */
  isVisible?: boolean;

  /** Optional custom className */
  className?: string;

  /** Playback controls from parent Player component (prevents duplicate streaming) */
  playbackControls: PlaybackControls;
}

/**
 * PlayerEnhancementPanel Component
 *
 * Provides a unified interface for enhanced audio playback with streaming controls,
 * progress visualization, and error handling.
 */
export const PlayerEnhancementPanel: React.FC<PlayerEnhancementPanelProps> = ({
  trackId,
  isVisible = true,
  className,
  playbackControls,
}) => {
  // Get streaming state from Redux (typed selectors fix #2463)
  const streaming = useSelector((state: RootState) => state.player.streaming.enhanced);
  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);

  // Play mode state (normal vs enhanced)
  const [playMode, setPlayMode] = useState<'normal' | 'enhanced'>('enhanced');

  // Use playback controls passed from parent Player component (no duplicate hook instance)
  // This prevents the double-streaming bug where both Player and PlayerEnhancementPanel
  // were creating separate usePlayEnhanced() instances
  const playNormal = usePlayNormal();

  // Debug: Log when component mounts/updates
  useEffect(() => {
    console.log('[PlayerEnhancementPanel] ✅ Component mounted/updated!', {
      trackId,
      isVisible,
      currentTrack: currentTrack?.title,
      playMode,
    });
  }, [trackId, isVisible, currentTrack?.title, playMode]);

  // Determine panel visibility
  const shouldShow = useMemo(() => {
    const show = isVisible && (trackId || currentTrack?.id);
    console.log('[PlayerEnhancementPanel] Visibility check:', {
      isVisible,
      trackId,
      currentTrackId: currentTrack?.id,
      shouldShow: show,
    });
    return show;
  }, [isVisible, trackId, currentTrack?.id]);

  // Use provided trackId or fall back to current track
  const activeTrackId = useMemo(() => {
    return trackId || currentTrack?.id || 0;
  }, [trackId, currentTrack?.id]);

  /**
   * Use streaming state from playback controls (passed from Player)
   * This ensures we use the same state as the Player component
   */
  const isStreaming = playbackControls.isStreaming;

  /**
   * Get streaming status for display
   */
  const streamingStatus = useMemo(() => {
    if (streaming?.state === 'buffering') return 'Buffering...';
    if (streaming?.state === 'streaming') return 'Playing';
    if (streaming?.state === 'error') return 'Error';
    return null;
  }, [streaming?.state]);

  /**
   * Handle play mode toggle
   *
   * When switching modes:
   * 1. Stop any current playback
   * 2. Update the mode state
   * 3. Start playback in the new mode
   */
  const handleModeToggle = useCallback(
    async (mode: 'normal' | 'enhanced') => {
      if (mode === playMode) return; // Already in this mode
      if (!activeTrackId) return; // No track to play

      console.log(`[PlayerEnhancementPanel] Switching to ${mode} mode for track ${activeTrackId}`);

      // Stop any current playback first
      playNormal.stopPlayback();
      playbackControls.stopPlayback();

      // Update mode state
      setPlayMode(mode);

      // Start playback in the new mode
      if (mode === 'normal') {
        console.log('[PlayerEnhancementPanel] Starting normal (original) playback');
        await playNormal.playNormal(activeTrackId);
      } else {
        console.log('[PlayerEnhancementPanel] Starting enhanced playback');
        // Use 'adaptive' preset with full intensity as default
        await playbackControls.playEnhanced(activeTrackId, 'adaptive', 1.0);
      }
    },
    [playMode, activeTrackId, playNormal, playbackControls]
  );

  if (!shouldShow) {
    return null;
  }

  return (
    <div className={className} style={styles.container}>
      {/* Playback Mode Toggle */}
      <div style={styles.modeToggleSection}>
        <div style={styles.modeToggleLabel}>Playback Mode</div>
        <div style={styles.modeToggleButtons}>
          <button
            style={{
              ...styles.modeButton,
              ...(playMode === 'normal' ? styles.modeButtonActive : styles.modeButtonInactive),
              ...(playMode === 'normal' && isStreaming ? styles.modeButtonStreaming : {}),
            }}
            onClick={() => handleModeToggle('normal')}
            disabled={!activeTrackId}
            title="Play original unprocessed audio"
          >
            🎵 Original
            {playMode === 'normal' && streamingStatus && (
              <span style={styles.streamingIndicator}>{streamingStatus}</span>
            )}
          </button>
          <button
            style={{
              ...styles.modeButton,
              ...(playMode === 'enhanced' ? styles.modeButtonActive : styles.modeButtonInactive),
              ...(playMode === 'enhanced' && isStreaming ? styles.modeButtonStreaming : {}),
            }}
            onClick={() => handleModeToggle('enhanced')}
            disabled={!activeTrackId}
            title="Play with audio enhancement/mastering"
          >
            ✨ Enhanced
            {playMode === 'enhanced' && streamingStatus && (
              <span style={styles.streamingIndicator}>{streamingStatus}</span>
            )}
          </button>
        </div>
      </div>

      {/*
        REMOVED: Large enhancement UI panel below playback bar
        User requested: "We don't need this whole section below the playback bar.
        Having the 'Enhanced' button in the right pane working snappy enough is all the customization we need."

        The compact toggle above (Original/Enhanced buttons) is sufficient.
      */}

      {/* Main Enhancement Controls - REMOVED */}
      {/*
      <div style={styles.controlsSection}>
        <EnhancedPlaybackControls
          trackId={activeTrackId}
          onPlayEnhanced={handlePlayEnhanced}
          disabled={!activeTrackId}
          showStatus={isStreaming}
        />
      </div>
      */}

      {/* Streaming Progress - REMOVED */}
      {/*
      {isStreaming && (
        <div style={styles.progressSection}>
          <StreamingProgressBar
            progress={streaming.progress || 0}
            bufferedSamples={streaming.bufferedSamples || 0}
            totalChunks={streaming.totalChunks || 0}
            processedChunks={streaming.processedChunks || 0}
            sampleRate={streaming.sampleRate || 48000}
            currentTime={streaming.currentTime || 0}
            showDetails={true}
          />
        </div>
      )}
      */}

      {/* Error Boundary - REMOVED */}
      {/*
      {streaming?.error && (
        <div style={styles.errorSection}>
          <StreamingErrorBoundary
            error={streaming.error}
            errorType={mapErrorToType(streaming.error)}
            onRetry={() => {
              // Retry is handled by the hook internally
              console.log('[PlayerEnhancementPanel] Retry streaming');
            }}
            onFallback={() => {
              // Switch to regular playback
              console.log('[PlayerEnhancementPanel] Falling back to regular playback');
            }}
            autoDismissMs={0} // Don't auto-dismiss, user must handle
            allowRetry={true}
            allowFallback={true}
            trackId={activeTrackId}
            showHistory={false}
          />
        </div>
      )}
      */}
    </div>
  );
};

/**
 * Map error message to StreamingErrorType - COMMENTED OUT (not used in compact toggle mode)
 */
/*
function mapErrorToType(error: string): StreamingErrorType {
  const lowerError = error.toLowerCase();

  if (lowerError.includes('network') || lowerError.includes('connection')) {
    return StreamingErrorType.NETWORK;
  } else if (lowerError.includes('buffer')) {
    return StreamingErrorType.BUFFER_UNDERRUN;
  } else if (lowerError.includes('audio') || lowerError.includes('context')) {
    return StreamingErrorType.AUDIO_CONTEXT;
  } else if (lowerError.includes('server') || lowerError.includes('500')) {
    return StreamingErrorType.SERVER;
  } else if (lowerError.includes('invalid') || lowerError.includes('format')) {
    return StreamingErrorType.INVALID_MESSAGE;
  }

  return StreamingErrorType.UNKNOWN;
}
*/

/**
 * Styles for PlayerEnhancementPanel
 */
const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,
    width: '100%',
  },

  modeToggleSection: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    padding: `${tokens.spacing.xs} 0`,
    marginBottom: tokens.spacing.sm,
  },

  modeToggleLabel: {
    fontSize: '0.6875rem',
    fontWeight: 600,
    color: tokens.colors.text.tertiary,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    flexShrink: 0,
  },

  modeToggleButtons: {
    display: 'flex',
    gap: tokens.spacing.xs,
    flex: 1,
  },

  modeButton: {
    flex: 1,
    padding: `6px 12px`,
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: '4px',
    fontSize: '0.8125rem',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 150ms ease-in-out',
    whiteSpace: 'nowrap',
    background: 'none',
  } as React.CSSProperties,

  modeButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
    borderColor: tokens.colors.accent.primary,
    boxShadow: `0 0 8px ${tokens.colors.accent.primary}40`,
  } as React.CSSProperties,

  modeButtonInactive: {
    backgroundColor: 'transparent',
    color: tokens.colors.text.tertiary,
    borderColor: tokens.colors.border.light,
  } as React.CSSProperties,

  modeButtonStreaming: {
    animation: 'pulse 2s ease-in-out infinite',
  } as React.CSSProperties,

  streamingIndicator: {
    display: 'block',
    fontSize: '0.625rem',
    fontWeight: 400,
    marginTop: '2px',
    opacity: 0.8,
  } as React.CSSProperties,

  // COMMENTED OUT - Not used in compact toggle mode
  /*
  controlsSection: {
    width: '100%',
  },

  progressSection: {
    width: '100%',
    padding: `0 ${tokens.spacing.sm}`,
  },

  errorSection: {
    width: '100%',
    padding: `0 ${tokens.spacing.sm}`,
  },
  */
};

// Add CSS animation keyframes for streaming pulse effect
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
`;
document.head.appendChild(styleSheet);

export default PlayerEnhancementPanel;
