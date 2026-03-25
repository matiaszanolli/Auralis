/**
 * Player - Orchestration component integrating UI components with streaming hooks.
 * Audio streaming handled via WebSocket (usePlayEnhanced hook).
 */

const DEBUG = import.meta.env.DEV;

import { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { styles } from './Player.styles';

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
import { playerSelectors } from '@/store/selectors';

const Player = () => {
  const dispatch = useDispatch();

  // Queue panel visibility state
  const [queuePanelOpen, setQueuePanelOpen] = useState(false);

  // Store pre-mute volume so unmute restores the user's prior level
  const preMuteVolumeRef = useRef<number>(0.5);

  // Redux state for current playback info (typed selectors fix #2463)
  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);
  const playerVolume = useSelector(playerSelectors.selectVolume);
  const playerIsMuted = useSelector(playerSelectors.selectIsMuted);
  const state = { volume: playerVolume, isMuted: playerIsMuted };

  // Queue state for next/previous functionality
  const queueTracks = useSelector(selectQueueTracks);
  const currentQueueIndex = useSelector(selectCurrentIndex);

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

  const handleSeek = useCallback((position: number) => {
    if (!isStreaming && !currentTrack?.id) {
      DEBUG && console.warn('[Player] Cannot seek: no track playing');
      return;
    }
    DEBUG && console.log('[Player] Seeking to position:', position);
    seekTo(position);
  }, [isStreaming, currentTrack?.id, seekTo]);

  const handleNext = useCallback(async () => {
    try {
      // Check if we have more tracks in the queue
      if (currentQueueIndex >= queueTracks.length - 1) {
        DEBUG && console.log('[Player] Already at last track in queue');
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
        DEBUG && console.log('[Player] Playing next track:', nextTrackData.title);
        await playEnhanced(nextTrackData.id, 'adaptive', 1.0);
      }
    } catch (err) {
      console.error('[Player] Next command error:', err);
    }
  }, [currentQueueIndex, queueTracks, stopPlayback, dispatch, playEnhanced]);

  const handlePrevious = useCallback(async () => {
    try {
      // Check if we have previous tracks in the queue
      if (currentQueueIndex <= 0) {
        DEBUG && console.log('[Player] Already at first track in queue');
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
        DEBUG && console.log('[Player] Playing previous track:', prevTrackData.title);
        await playEnhanced(prevTrackData.id, 'adaptive', 1.0);
      }
    } catch (err) {
      console.error('[Player] Previous command error:', err);
    }
  }, [currentQueueIndex, queueTracks, stopPlayback, dispatch, playEnhanced]);

  const handlePlayPause = useCallback(async () => {
    if (!currentTrack?.id) {
      DEBUG && console.warn('[Player] No track loaded, cannot play');
      return;
    }

    try {
      // If already streaming, toggle pause/resume
      if (isStreaming) {
        if (isPaused) {
          DEBUG && console.log('[Player] Resuming playback');
          resumePlayback();
        } else {
          DEBUG && console.log('[Player] Pausing playback');
          pausePlayback();
        }
      } else {
        // Not streaming - start new stream
        DEBUG && console.log('[Player] Starting WebSocket audio streaming for track:', currentTrack.id);
        await playEnhanced(currentTrack.id, 'adaptive', 1.0);
      }
    } catch (err) {
      console.error('[Player] Play/Pause command error:', err);
    }
  }, [currentTrack?.id, isStreaming, isPaused, resumePlayback, pausePlayback, playEnhanced]);

  const handleVolumeChange = useCallback(async (vol: number) => {
    try {
      // Volume is 0-1 range in WebSocket/AudioEngine, 0-100 in Redux/Backend
      setStreamingVolume(vol);

      // Persist volume to Redux (convert 0-1 to 0-100)
      const volumeForRedux = Math.round(vol * 100);
      dispatch(setVolume(volumeForRedux));

      DEBUG && console.log('[Player] Volume changed:', vol, '(Redux:', volumeForRedux, ')');
    } catch (err) {
      console.error('[Player] Volume command error:', err);
    }
  }, [setStreamingVolume, dispatch]);

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
      DEBUG && console.log('[Player] Track ended, auto-advancing to next track');
      handleNext();
    }
  }, [streamingState, wsCurrentTime, trackDuration, currentQueueIndex, queueTracks.length, handleNext]);

  const volume = useMemo(() => {
    return state.volume ?? 50;
  }, [state.volume]);

  // Muted state - check if volume is 0 or explicitly muted
  const isMuted = useMemo(() => {
    return volume === 0 || state.isMuted === true;
  }, [volume, state.isMuted]);

  // Stable mute toggle handler (fixes #3163 — last inline handler)
  const handleMuteToggle = useCallback(async () => {
    if (isMuted) {
      await handleVolumeChange(preMuteVolumeRef.current);
    } else {
      preMuteVolumeRef.current = volume / 100;
      await handleVolumeChange(0);
    }
  }, [isMuted, volume, handleVolumeChange]);

  // Stable queue toggle handler
  const handleQueueToggle = useCallback(() => {
    setQueuePanelOpen(prev => !prev);
  }, []);

  return (
    <Box
      data-testid="player"
      role="region"
      aria-label="Music player"
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
            onMuteToggle={handleMuteToggle}
            disabled={hasError}
          />

          {/* Queue Button - Compact with glass effects */}
          <button
            onClick={handleQueueToggle}
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
            aria-expanded={queuePanelOpen}
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

      {/* Queue Panel - Always mounted; hidden via CSS to preserve scroll + focus (#2541) */}
      <Box sx={{ ...styles.queuePanelWrapper, display: queuePanelOpen ? undefined : 'none' }}>
        <QueuePanel
          collapsed={false}
          onToggleCollapse={() => setQueuePanelOpen(false)}
        />
      </Box>

      {/* Error State Indicator */}
      {hasError && (
        <Box sx={styles.errorBanner} role="alert" aria-live="assertive">
          <span style={styles.errorText}>
            {streamingError || 'Playback error occurred'}
          </span>
        </Box>
      )}
    </Box>
  );
};

export default Player;
