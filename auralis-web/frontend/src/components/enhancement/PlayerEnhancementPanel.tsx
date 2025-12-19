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

import React, { useMemo, useCallback, useState } from 'react';
import { useSelector } from 'react-redux';
import { tokens } from '@/design-system';

// Streaming components
import { EnhancedPlaybackControls } from './EnhancedPlaybackControls';
import { StreamingProgressBar } from './StreamingProgressBar';
import { StreamingErrorBoundary, StreamingErrorType } from './StreamingErrorBoundary';

// Playback hooks
import { usePlayNormal } from '@/hooks/enhancement/usePlayNormal';

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
}) => {
  // Get streaming state from Redux
  const streaming = useSelector((state: any) => state.player?.streaming || {});
  const currentTrack = useSelector((state: any) => state.player?.currentTrack);

  // Play mode state (normal vs enhanced)
  const [playMode, setPlayMode] = useState<'normal' | 'enhanced'>('enhanced');

  // Playback hooks
  const playNormal = usePlayNormal();

  // Determine panel visibility
  const shouldShow = useMemo(() => {
    return isVisible && (trackId || currentTrack?.id);
  }, [isVisible, trackId, currentTrack?.id]);

  // Use provided trackId or fall back to current track
  const activeTrackId = useMemo(() => {
    return trackId || currentTrack?.id || 0;
  }, [trackId, currentTrack?.id]);

  /**
   * Determine if we're currently streaming
   */
  const isStreaming = useMemo(() => {
    return streaming?.state === 'streaming' || streaming?.state === 'buffering';
  }, [streaming?.state]);

  /**
   * Handle play enhanced callback
   */
  const handlePlayEnhanced = useCallback(
    (preset: string, intensity: number) => {
      console.log(`[PlayerEnhancementPanel] Playing enhanced: ${preset} @ ${intensity}x`);
      // Redis will handle state updates via WebSocket
    },
    []
  );

  /**
   * Handle play mode toggle
   */
  const handleModeToggle = useCallback(
    (mode: 'normal' | 'enhanced') => {
      if (mode === playMode) return; // Already in this mode

      console.log(`[PlayerEnhancementPanel] Switching to ${mode} mode`);

      if (mode === 'normal') {
        // Stop enhanced, start normal
        setPlayMode('normal');
        playNormal.playNormal(activeTrackId);
      } else {
        // Stop normal, start enhanced
        setPlayMode('enhanced');
        // EnhancedPlaybackControls will handle starting enhanced playback
      }
    },
    [playMode, activeTrackId, playNormal]
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
            }}
            onClick={() => handleModeToggle('normal')}
            disabled={!activeTrackId}
            title="Play original unprocessed audio"
          >
            🎵 Original
          </button>
          <button
            style={{
              ...styles.modeButton,
              ...(playMode === 'enhanced' ? styles.modeButtonActive : styles.modeButtonInactive),
            }}
            onClick={() => handleModeToggle('enhanced')}
            disabled={!activeTrackId}
            title="Play with audio enhancement/mastering"
          >
            ✨ Enhanced
          </button>
        </div>
      </div>

      {/* Main Enhancement Controls */}
      <div style={styles.controlsSection}>
        <EnhancedPlaybackControls
          trackId={activeTrackId}
          onPlayEnhanced={handlePlayEnhanced}
          disabled={!activeTrackId}
          showStatus={isStreaming}
        />
      </div>

      {/* Streaming Progress - shown when streaming or buffering */}
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

      {/* Error Boundary - shown when error occurs */}
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
    </div>
  );
};

/**
 * Map error message to StreamingErrorType
 */
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
    flexDirection: 'column',
    gap: tokens.spacing.sm,
    padding: `${tokens.spacing.sm} 0`,
    borderBottom: `1px solid ${tokens.colors.border.medium}`,
  },

  modeToggleLabel: {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: tokens.colors.text.secondary,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },

  modeToggleButtons: {
    display: 'flex',
    gap: tokens.spacing.xs,
    width: '100%',
  },

  modeButton: {
    flex: 1,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    border: `2px solid transparent`,
    borderRadius: '4px',
    fontSize: '0.9375rem',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 200ms ease-in-out',
    whiteSpace: 'nowrap',
  } as React.CSSProperties,

  modeButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.inverse,
    borderColor: tokens.colors.accent.primary,
  } as React.CSSProperties,

  modeButtonInactive: {
    backgroundColor: tokens.colors.bg.level2,
    color: tokens.colors.text.secondary,
    borderColor: tokens.colors.border.light,
  } as React.CSSProperties,

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
};

export default PlayerEnhancementPanel;
