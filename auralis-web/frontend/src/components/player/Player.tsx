/**
 * Player - Phase 5 Orchestration Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Master player component that integrates all 6 Phase 4 UI components
 * (TimeDisplay, BufferingIndicator, ProgressBar, PlaybackControls, VolumeControl, TrackDisplay)
 * with the 3 core hooks (usePlayerStreaming, usePlayerControls, usePlayerDisplay).
 *
 * This is a thin orchestration layer that:
 * - Wires hook data to component props
 * - Coordinates streaming controls and display
 * - Provides responsive layout
 * - Audio streaming handled exclusively via WebSocket (usePlayEnhanced hook)
 *
 * @component
 * @example
 * ```tsx
 * <Player />
 * ```
 */

import React, { useMemo, useState } from 'react';
import { tokens } from '@/design-system';

// Phase 4 UI Components
import TimeDisplay from './TimeDisplay';
import BufferingIndicator from './BufferingIndicator';
import ProgressBar from './ProgressBar';
import PlaybackControls from './PlaybackControls';
import VolumeControl from './VolumeControl';
import TrackDisplay from './TrackDisplay';

// Phase 6 Queue Component
import QueuePanel from './QueuePanel';

// Phase 3 Enhancement Components
import { PlayerEnhancementPanel } from '@/components/enhancement';

// Core Phase 3 Hooks
import { usePlayerStreaming, PlayerStreamingState } from '@/hooks/player/usePlayerStreaming';
import { usePlayerDisplay, PlayerDisplayInfo } from '@/hooks/player/usePlayerDisplay';

// WebSocket Audio Streaming Hook (replaces REST API playback)
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';

// Existing hooks for track info
import { useCurrentTrack } from '@/hooks/player/usePlaybackState';
import { useSelector, useDispatch } from 'react-redux';
import {
  selectQueueTracks,
  selectCurrentIndex,
  nextTrack,
  previousTrack,
  setCurrentIndex,
} from '@/store/slices/queueSlice';
import { setCurrentTrack } from '@/store/slices/playerSlice';

/**
 * Player Component
 *
 * Full-featured music player with streaming synchronization,
 * playback controls, volume control, progress tracking, and time display.
 *
 * Architecture:
 * - Layer 1: Hooks (usePlayerStreaming, usePlayerControls, usePlayerDisplay)
 * - Layer 2: 6 UI Components (props-based, no internal state)
 * - Layer 3: Responsive layout with design tokens
 * - WebSocket Streaming: Audio playback via usePlayEnhanced hook (not HTML5 audio)
 */
const Player: React.FC = () => {
  const dispatch = useDispatch();

  // Queue panel visibility state
  const [queuePanelOpen, setQueuePanelOpen] = useState(false);

  // Redux state for current playback info
  // FIX: Read currentTrack directly from Redux instead of WebSocket hook
  const state = useSelector((state: any) => state.player || {});
  const currentTrack = state.currentTrack;

  // Queue state for next/previous functionality
  const queueTracks = useSelector(selectQueueTracks);
  const currentQueueIndex = useSelector(selectCurrentIndex);

  // WebSocket Audio Streaming Hook (replaces REST API playback)
  // Provides: playEnhanced, pausePlayback, resumePlayback, stopPlayback, setVolume
  const {
    playEnhanced,
    pausePlayback,
    resumePlayback,
    stopPlayback,
    setVolume: setStreamingVolume,
    isStreaming,
    streamingState,
    streamingProgress,
    processedChunks,
    totalChunks,
    currentTime: wsCurrentTime,
    isPaused,
    error: streamingError,
  } = usePlayEnhanced();

  // Derived buffering state for UI
  const isBuffering = streamingState === 'buffering';
  const hasError = streamingState === 'error';

  // Use streaming progress as buffered percentage (chunks received / total chunks)
  const wsBufferedPercentage = totalChunks > 0 ? (processedChunks / totalChunks) * 100 : 0;

  // Phase 3 Hook: Core streaming synchronization
  // Handles timing, buffering, position tracking, and WebSocket sync
  const streaming = usePlayerStreaming({
    audioElement: null, // Audio streaming via WebSocket (usePlayEnhanced), not HTML5 audio
    syncInterval: 5000,
    driftThreshold: 500,
    updateInterval: 100,
  });

  // DISABLED: Seeking not supported with WebSocket streaming
  // TODO: Implement chunk-based seeking in the future
  const handleSeek = (_position: number) => {
    console.warn('[Player] Seeking is not supported with WebSocket streaming');
    // Seeking requires stopping current stream, calculating chunk offset,
    // and restarting from that position - complex to implement correctly
  };

  // Next track: Stop current stream, update queue index, start new stream
  const handleNext = async () => {
    try {
      // Check if we have more tracks in the queue
      if (currentQueueIndex >= queueTracks.length - 1) {
        console.log('[Player] Already at last track in queue');
        return;
      }

      // Stop current playback
      stopPlayback();

      // Update queue index
      dispatch(nextTrack());

      // Get next track from queue
      const nextTrackData = queueTracks[currentQueueIndex + 1];
      if (nextTrackData) {
        // Update current track in player state
        dispatch(setCurrentTrack(nextTrackData));

        // Start playing the new track
        console.log('[Player] Playing next track:', nextTrackData.title);
        await playEnhanced(nextTrackData.id, 'adaptive', 1.0);
      }
    } catch (err) {
      console.error('[Player] Next command error:', err);
    }
  };

  // Previous track: Stop current stream, update queue index, start new stream
  const handlePrevious = async () => {
    try {
      // Check if we have previous tracks in the queue
      if (currentQueueIndex <= 0) {
        console.log('[Player] Already at first track in queue');
        return;
      }

      // Stop current playback
      stopPlayback();

      // Update queue index
      dispatch(previousTrack());

      // Get previous track from queue
      const prevTrackData = queueTracks[currentQueueIndex - 1];
      if (prevTrackData) {
        // Update current track in player state
        dispatch(setCurrentTrack(prevTrackData));

        // Start playing the new track
        console.log('[Player] Playing previous track:', prevTrackData.title);
        await playEnhanced(prevTrackData.id, 'adaptive', 1.0);
      }
    } catch (err) {
      console.error('[Player] Previous command error:', err);
    }
  };

  // Unified Play/Pause toggle handler
  // Handles three states: not streaming → start, streaming → pause, paused → resume
  const handlePlayPause = async () => {
    if (!currentTrack?.id) {
      console.warn('[Player] No track loaded, cannot play');
      return;
    }

    try {
      // If already streaming, toggle pause/resume
      if (isStreaming) {
        if (isPaused) {
          console.log('[Player] Resuming playback');
          resumePlayback();
        } else {
          console.log('[Player] Pausing playback');
          pausePlayback();
        }
      } else {
        // Not streaming - start new stream
        console.log('[Player] Starting WebSocket audio streaming for track:', currentTrack.id);
        await playEnhanced(currentTrack.id, 'adaptive', 1.0);
      }
    } catch (err) {
      console.error('[Player] Play/Pause command error:', err);
    }
  };

  const handleVolumeChange = async (vol: number) => {
    try {
      // Volume is 0-1 range in WebSocket, 0-100 in UI
      setStreamingVolume(vol);
      console.log('[Player] Volume changed:', vol);
    } catch (err) {
      console.error('[Player] Volume command error:', err);
    }
  };

  // Phase 3 Hook: Display formatting
  // Converts raw streaming data to formatted display strings
  const display = usePlayerDisplay({
    currentTime: wsCurrentTime,
    duration: currentTrack?.duration ?? 0,
    isPlaying: isStreaming && !isPaused,
    bufferedPercentage: wsBufferedPercentage,
  });

  // Extract volume from Redux state (0-1 range, convert to 0-100 for components)
  const volume = useMemo(() => {
    return state.volume ?? 50;
  }, [state.volume, isStreaming]);

  // Muted state - check if volume is 0 or explicitly muted
  const isMuted = useMemo(() => {
    return volume === 0 || state.isMuted === true;
  }, [volume, state.isMuted]);

  return (
    <div
      data-testid="player"
      style={styles.player}
    >
      {/* Progress Bar - Full width at top */}
      <div style={styles.progressBarContainer}>
        <BufferingIndicator
          isBuffering={isBuffering}
          bufferedPercentage={wsBufferedPercentage}
          isError={hasError}
          errorMessage={streamingError ?? undefined}
        />
        <ProgressBar
          currentTime={wsCurrentTime}
          duration={currentTrack?.duration ?? 0}
          bufferedPercentage={wsBufferedPercentage}
          onSeek={handleSeek}
          disabled={true}  /* Seeking disabled until WebSocket chunk-based seeking is implemented */
        />
      </div>

      {/* Main compact player row */}
      <div style={styles.mainRow}>
        {/* Left: Track info + time */}
        <div style={styles.trackInfoSection}>
          <TrackDisplay
            title={currentTrack?.title ?? 'No track'}
            artist={currentTrack?.artist}
            album={currentTrack?.album}
            isLoading={isBuffering}
            className="player-track-display"
          />
          <TimeDisplay
            currentTime={wsCurrentTime}
            duration={currentTrack?.duration ?? 0}
          />
        </div>

        {/* Center: Playback Controls */}
        <PlaybackControls
          isPlaying={isStreaming && !isPaused}
          onPlay={handlePlayPause}
          onPause={handlePlayPause}
          onNext={handleNext}
          onPrevious={handlePrevious}
          isLoading={isBuffering}
          disabled={hasError}
        />

        {/* Right: Volume + Queue */}
        <div style={styles.rightSection}>
          <VolumeControl
            volume={volume / 100}
            onVolumeChange={handleVolumeChange}
            isMuted={isMuted}
            onMuteToggle={async () => {
              const newVolume = isMuted ? 0.5 : 0;
              await handleVolumeChange(newVolume);
            }}
            disabled={hasError}
          />

          {/* Queue Button - Compact */}
          <button
            onClick={() => setQueuePanelOpen(!queuePanelOpen)}
            style={{
              ...styles.queueButton,
              backgroundColor: queuePanelOpen ? tokens.colors.accent.primary : 'transparent',
              color: tokens.colors.text.primary,
              borderColor: queuePanelOpen ? tokens.colors.accent.primary : tokens.colors.border.medium,
            }}
            title="Toggle queue (Q)"
            aria-label="Toggle queue"
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = tokens.colors.accent.primary;
              if (!queuePanelOpen) {
                e.currentTarget.style.backgroundColor = tokens.colors.bg.secondary;
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = tokens.colors.border.medium;
              if (!queuePanelOpen) {
                e.currentTarget.style.backgroundColor = 'transparent';
              }
            }}
          >
            ♪
          </button>
        </div>
      </div>

      {/* Queue Panel - Expands when opened */}
      {queuePanelOpen && (
        <div style={styles.queuePanelWrapper}>
          <QueuePanel
            collapsed={false}
            onToggleCollapse={() => setQueuePanelOpen(false)}
          />
        </div>
      )}

      {/* Enhancement Panel - Integrated streaming controls */}
      {(() => {
        console.log('[Player] 🔍 Checking Enhancement Panel condition:', {
          currentTrack: currentTrack?.title || 'NO TRACK',
          hasTrack: !!currentTrack,
          trackId: currentTrack?.id,
        });
        return currentTrack && (
          <div style={styles.enhancementPanelWrapper}>
            <PlayerEnhancementPanel
              trackId={currentTrack?.id}
              isVisible={!!currentTrack}
              playbackControls={{
                playEnhanced,
                stopPlayback,
                pausePlayback,
                resumePlayback,
                isStreaming,
                isPaused,
              }}
            />
          </div>
        );
      })()}

      {/* Error State Indicator */}
      {hasError && (
        <div style={styles.errorBanner}>
          <span style={styles.errorText}>
            {streamingError || 'Playback error occurred'}
          </span>
        </div>
      )}
    </div>
  );
};

/**
 * Component styles using design tokens
 *
 * Layout:
 * - Top: Track display + current time
 * - Middle: Progress bar with buffering
 * - Bottom: Playback controls + volume
 *
 * Responsive breakpoints:
 * - Desktop (1024px+): Full width side-by-side
 * - Tablet (768-1024px): Stacked, adjusted spacing
 * - Mobile (<768px): Compact, minimal spacing
 */
const styles = {
  player: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    backgroundColor: tokens.colors.bg.primary,
    borderTop: `1px solid ${tokens.colors.border.medium}`,
    boxShadow: tokens.shadows.sm,
    zIndex: 1000,
    padding: 0,
    gap: 0,
  },

  progressBarContainer: {
    width: '100%',
    height: 'auto',
    padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
    paddingBottom: tokens.spacing.xs,
  },

  mainRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacing.lg,
    padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
    minHeight: '64px',

    '@media (max-width: 768px)': {
      flexDirection: 'column' as const,
      alignItems: 'stretch',
      padding: tokens.spacing.md,
      minHeight: 'auto',
      gap: tokens.spacing.md,
    },
  },

  trackInfoSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    minWidth: '200px',
    flex: '1 1 auto',

    '@media (max-width: 768px)': {
      minWidth: 'auto',
      width: '100%',
    },
  },

  rightSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    flex: '1 1 auto',
    justifyContent: 'flex-end',

    '@media (max-width: 768px)': {
      width: '100%',
      justifyContent: 'space-between',
    },
  },

  queueButton: {
    width: '40px',
    height: '40px',
    padding: 0,
    border: `1px solid ${tokens.colors.border.medium}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.medium,
    transition: tokens.transitions.all,
    backgroundColor: 'transparent',
    color: tokens.colors.text.primary,
    outline: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  queuePanelWrapper: {
    borderTop: `1px solid ${tokens.colors.border.medium}`,
    padding: tokens.spacing.lg,
    maxHeight: '400px',
    overflowY: 'auto' as const,
    backgroundColor: tokens.colors.bg.secondary,
  },

  enhancementPanelWrapper: {
    borderTop: `1px solid ${tokens.colors.border.medium}`,
    padding: tokens.spacing.lg,
    backgroundColor: tokens.colors.bg.secondary,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
  },

  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.semantic.error || '#ff4444',
    borderRadius: tokens.borderRadius.md,
    margin: tokens.spacing.sm,
  },

  errorText: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};

export default Player;
