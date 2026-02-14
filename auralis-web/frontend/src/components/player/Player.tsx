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

import React, { useMemo, useState, useEffect, useRef } from 'react';
import { Box } from '@mui/material';
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

// WebSocket Audio Streaming Hook (replaces REST API playback)
import { usePlayEnhanced } from '@/hooks/enhancement/usePlayEnhanced';

// Redux hooks and actions
import { useSelector, useDispatch } from 'react-redux';
import {
  selectQueueTracks,
  selectCurrentIndex,
  nextTrack,
  previousTrack,
} from '@/store/slices/queueSlice';
import { setCurrentTrack, setVolume } from '@/store/slices/playerSlice';

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
  // Provides: playEnhanced, seekTo, pausePlayback, resumePlayback, stopPlayback, setVolume
  const {
    playEnhanced,
    seekTo,
    pausePlayback,
    resumePlayback,
    stopPlayback,
    setVolume: setStreamingVolume,
    isStreaming,
    streamingState,
    processedChunks,
    totalChunks,
    currentTime: wsCurrentTime,
    isPaused,
    isSeeking,
    error: streamingError,
  } = usePlayEnhanced();

  // Derived buffering state for UI
  const isBuffering = streamingState === 'buffering';
  const hasError = streamingState === 'error';

  // Use streaming progress as buffered percentage (chunks received / total chunks)
  const wsBufferedPercentage = totalChunks > 0 ? (processedChunks / totalChunks) * 100 : 0;

  // Note: usePlayerStreaming is not used - all streaming is via WebSocket (usePlayEnhanced)

  // Handle seeking via WebSocket
  // Sends seek message to backend which restarts streaming from the target chunk
  const handleSeek = (position: number) => {
    if (!isStreaming && !currentTrack?.id) {
      console.warn('[Player] Cannot seek: no track playing');
      return;
    }
    console.log('[Player] Seeking to position:', position);
    seekTo(position);
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
      // Volume is 0-1 range in WebSocket/AudioEngine, 0-100 in Redux/Backend
      setStreamingVolume(vol);

      // Persist volume to Redux (convert 0-1 to 0-100)
      const volumeForRedux = Math.round(vol * 100);
      dispatch(setVolume(volumeForRedux));

      console.log('[Player] Volume changed:', vol, '(Redux:', volumeForRedux, ')');
    } catch (err) {
      console.error('[Player] Volume command error:', err);
    }
  };

  // Auto-advance to next track when current track ends
  // Detects when streaming is complete and playback has reached near the end
  const hasAutoAdvancedRef = useRef(false);
  const trackDuration = currentTrack?.duration ?? 0;

  useEffect(() => {
    // Reset auto-advance flag when track changes
    hasAutoAdvancedRef.current = false;
  }, [currentTrack?.id]);

  useEffect(() => {
    // Conditions for auto-advance:
    // 1. All chunks received (streamingState === 'complete')
    // 2. Playback has reached near the end (within 0.5s of duration)
    // 3. Track has meaningful duration (> 0)
    // 4. Haven't already auto-advanced for this track
    const isComplete = streamingState === 'complete';
    const nearEnd = trackDuration > 0 && wsCurrentTime >= trackDuration - 0.5;
    const hasMoreTracks = currentQueueIndex < queueTracks.length - 1;

    if (isComplete && nearEnd && hasMoreTracks && !hasAutoAdvancedRef.current) {
      hasAutoAdvancedRef.current = true;
      console.log('[Player] Track ended, auto-advancing to next track');
      handleNext();
    }
  }, [streamingState, wsCurrentTime, trackDuration, currentQueueIndex, queueTracks.length]);

  // Note: usePlayerDisplay not used - TimeDisplay component handles formatting

  // Extract volume from Redux state (0-100 range)
  const volume = useMemo(() => {
    return state.volume ?? 50;
  }, [state.volume, isStreaming]);

  // Muted state - check if volume is 0 or explicitly muted
  const isMuted = useMemo(() => {
    return volume === 0 || state.isMuted === true;
  }, [volume, state.isMuted]);

  return (
    <Box
      data-testid="player"
      sx={styles.player}
    >
      {/* Progress Bar - Full width at top */}
      <Box sx={styles.progressBarContainer}>
        <BufferingIndicator
          isBuffering={isBuffering || isSeeking}
          bufferedPercentage={wsBufferedPercentage}
          isError={hasError}
          errorMessage={isSeeking ? 'Seeking...' : (streamingError ?? undefined)}
        />
        <ProgressBar
          currentTime={wsCurrentTime}
          duration={currentTrack?.duration ?? 0}
          bufferedPercentage={wsBufferedPercentage}
          onSeek={handleSeek}
          disabled={hasError || isSeeking}  /* Disable during errors or while seeking */
        />
      </Box>

      {/* Main compact player row */}
      <Box sx={styles.mainRow}>
        {/* Left: Track info + time */}
        <Box sx={styles.trackInfoSection}>
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
        </Box>

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
        <Box sx={styles.rightSection}>
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

          {/* Queue Button - Compact with glass effects */}
          <button
            onClick={() => setQueuePanelOpen(!queuePanelOpen)}
            style={{
              ...styles.queueButton,
              // Active state: medium glass effect with accent color
              background: queuePanelOpen ? tokens.glass.medium.background : 'transparent',
              backdropFilter: queuePanelOpen ? tokens.glass.medium.backdropFilter : 'none',
              border: queuePanelOpen ? `1px solid ${tokens.colors.accent.primary}` : tokens.glass.subtle.border,
              boxShadow: queuePanelOpen ? `0 0 12px ${tokens.colors.accent.primary}44` : 'none',
            }}
            title="Toggle queue (Q)"
            aria-label="Toggle queue"
            onMouseEnter={(e) => {
              if (!queuePanelOpen) {
                // Hover: subtle glass effect
                e.currentTarget.style.background = tokens.glass.subtle.background;
                e.currentTarget.style.backdropFilter = tokens.glass.subtle.backdropFilter;
                e.currentTarget.style.border = tokens.glass.subtle.border;
                e.currentTarget.style.boxShadow = tokens.glass.subtle.boxShadow;
              }
            }}
            onMouseLeave={(e) => {
              if (!queuePanelOpen) {
                // Return to idle: transparent
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.backdropFilter = 'none';
                e.currentTarget.style.border = tokens.glass.subtle.border;
                e.currentTarget.style.boxShadow = 'none';
              }
            }}
          >
            ♪
          </button>
        </Box>
      </Box>

      {/* Queue Panel - Expands when opened */}
      {queuePanelOpen && (
        <Box sx={styles.queuePanelWrapper}>
          <QueuePanel
            collapsed={false}
            onToggleCollapse={() => setQueuePanelOpen(false)}
          />
        </Box>
      )}

      {/* Enhancement Panel - REMOVED: Redundant playback mode controls */}
      {/* {(() => {
        console.log('[Player] 🔍 Checking Enhancement Panel condition:', {
          currentTrack: currentTrack?.title || 'NO TRACK',
          hasTrack: !!currentTrack,
          trackId: currentTrack?.id,
        });
        return currentTrack && (
          <Box sx={styles.enhancementPanelWrapper}>
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
          </Box>
        );
      })()} */}

      {/* Error State Indicator */}
      {hasError && (
        <Box sx={styles.errorBanner}>
          <span style={styles.errorText}>
            {streamingError || 'Playback error occurred'}
          </span>
        </Box>
      )}
    </Box>
  );
};

/**
 * Component styles using design tokens (Design Language v1.2.0)
 *
 * Layout:
 * - Top: Track display + current time
 * - Middle: Progress bar with buffering
 * - Bottom: Playback controls + volume
 *
 * Glass Effects: Applied to main container for elevated, glossy aesthetic
 * Organic Spacing: Cluster (8px), Group (16px), Section (32px) for natural rhythm
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

    // Glass effect for PlayerBar - semi-transparent for starfield visibility
    background: 'rgba(16, 23, 41, 0.50)',                 // 50% opacity for starfield visibility
    backdropFilter: 'blur(10px) saturate(1.08)',          // Moderate blur preserves starfield
    border: 'none',
    // Glass bevel: top highlight + outer shadow
    boxShadow: '0 -8px 32px rgba(0, 0, 0, 0.20), inset 0 1px 0 rgba(255, 255, 255, 0.10)',

    zIndex: 1000,
    padding: 0,
    gap: 0,
  },

  progressBarContainer: {
    width: '100%',
    height: 'auto',
    padding: `${tokens.spacing.cluster} ${tokens.spacing.lg}`,  // 8px top, organic spacing
    paddingBottom: tokens.spacing.xs,
  },

  mainRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacing.group,                            // 16px - organic group spacing
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

    // Glass effect for queue button (idle state)
    background: 'transparent',
    border: tokens.glass.subtle.border,                   // Subtle glass border
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic

    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,              // 20px for impact
    fontWeight: tokens.typography.fontWeight.medium,
    transition: `${tokens.transitions.base}, backdrop-filter ${tokens.transitions.base}`,
    color: tokens.colors.text.primary,
    outline: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  queuePanelWrapper: {
    // Glass effect for expanded queue panel
    background: tokens.glass.subtle.background,           // Subtle glass background
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 20px blur for consistency
    borderTop: tokens.glass.subtle.border,                // Subtle glass border separator
    boxShadow: tokens.glass.subtle.boxShadow,             // Depth + inner glow

    padding: tokens.spacing.lg,
    maxHeight: '400px',
    overflowY: 'auto' as const,
  },

  // enhancementPanelWrapper: REMOVED - No longer used after removing playback mode panel

  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    padding: tokens.spacing.md,

    // Glass effect for error banner (strong presence)
    background: 'rgba(255, 68, 68, 0.15)',                // Error tint with transparency
    backdropFilter: 'blur(20px) saturate(1.1)',           // Glass blur
    border: '1px solid rgba(255, 68, 68, 0.3)',           // Error border
    boxShadow: '0 4px 16px rgba(255, 68, 68, 0.2), 0 0 0 1px rgba(255, 255, 255, 0.05)',

    borderRadius: tokens.borderRadius.md,                 // 12px - softer curves
    margin: tokens.spacing.sm,
  },

  errorText: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};

export default Player;
