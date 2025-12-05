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

import React, { useMemo, useCallback } from 'react';
import { useSelector } from 'react-redux';
import { tokens } from '@/design-system';

// Streaming components
import { EnhancedPlaybackControls } from './EnhancedPlaybackControls';
import { StreamingProgressBar } from './StreamingProgressBar';
import { StreamingErrorBoundary, StreamingErrorType } from './StreamingErrorBoundary';

/**
 * Props for PlayerEnhancementPanel
 */
interface PlayerEnhancementPanelProps {
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
      // Redux will handle state updates via WebSocket
    },
    []
  );

  if (!shouldShow) {
    return null;
  }

  return (
    <div className={className} style={styles.container}>
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
