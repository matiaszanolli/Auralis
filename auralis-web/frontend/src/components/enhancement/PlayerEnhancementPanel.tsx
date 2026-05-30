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

const DEBUG = import.meta.env.DEV;

import { CSSProperties, useCallback, useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import { keyframes } from '@mui/material';
import { playerSelectors } from '@/store/selectors';
import type { RootState } from '@/store';
import { tokens } from '@/design-system';

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
`;

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
export const PlayerEnhancementPanel = ({
  trackId,
  isVisible = true,
  className,
  playbackControls,
}: PlayerEnhancementPanelProps) => {
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
    DEBUG && console.log('[PlayerEnhancementPanel] ✅ Component mounted/updated!', {
      trackId,
      isVisible,
      currentTrack: currentTrack?.title,
      playMode,
    });
  }, [trackId, isVisible, currentTrack?.title, playMode]);

  // Determine panel visibility (pure computation — no side effects)
  const shouldShow = useMemo(() => {
    return isVisible && (trackId || currentTrack?.id);
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

      DEBUG && console.log(`[PlayerEnhancementPanel] Switching to ${mode} mode for track ${activeTrackId}`);

      // Stop any current playback first
      playNormal.stopPlayback();
      playbackControls.stopPlayback();

      // Update mode state
      setPlayMode(mode);

      // Start playback in the new mode
      if (mode === 'normal') {
        DEBUG && console.log('[PlayerEnhancementPanel] Starting normal (original) playback');
        await playNormal.playNormal(activeTrackId);
      } else {
        DEBUG && console.log('[PlayerEnhancementPanel] Starting enhanced playback');
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
            aria-label="Play original audio"
            aria-pressed={playMode === 'normal'}
          >
            <span aria-hidden="true">🎵</span> Original
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
            aria-label="Play with enhancement"
            aria-pressed={playMode === 'enhanced'}
          >
            <span aria-hidden="true">✨</span> Enhanced
            {playMode === 'enhanced' && streamingStatus && (
              <span style={styles.streamingIndicator}>{streamingStatus}</span>
            )}
          </button>
        </div>
      </div>

    </div>
  );
};

/**
 * Styles for PlayerEnhancementPanel
 */
const styles: Record<string, CSSProperties> = {
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
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.semibold,
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
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.medium,
    cursor: 'pointer',
    transition: tokens.transitions.hover_out,
    whiteSpace: 'nowrap',
    background: 'none',
  } as CSSProperties,

  modeButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primary,
    borderColor: tokens.colors.accent.primary,
    boxShadow: `0 0 8px ${tokens.colors.accent.primary}40`,
  } as CSSProperties,

  modeButtonInactive: {
    backgroundColor: 'transparent',
    color: tokens.colors.text.tertiary,
    borderColor: tokens.colors.border.light,
  } as CSSProperties,

  modeButtonStreaming: {
    animation: `${pulse} 2s ease-in-out infinite`,
  } as CSSProperties,

  streamingIndicator: {
    display: 'block',
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.normal,
    marginTop: '2px',
    opacity: 0.8,
  } as CSSProperties,

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

export default PlayerEnhancementPanel;
