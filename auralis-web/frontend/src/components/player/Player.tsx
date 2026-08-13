/**
 * Player - Orchestration component integrating UI components with streaming hooks.
 * Audio streaming handled via the shared PlaybackSessionContext (#4541), which
 * wraps usePlayEnhanced.
 */

import { useState, useCallback, useMemo } from 'react';
import { Box } from '@mui/material';
import { styles } from './Player.styles';
import { themeVars } from '@/theme/semanticTheme';

// Phase 4 UI Components
import TimeDisplay from './TimeDisplay';
import BufferingIndicator from './BufferingIndicator';
import ProgressBar from './ProgressBar';
import PlaybackControls from './PlaybackControls';
import VolumeControl from './VolumeControl';
import TrackDisplay from './TrackDisplay';

// Phase 6 Queue Component
import QueuePanel from './QueuePanel';

// Shared playback session (#4541) — the same instance the global keyboard
// shortcuts (ComfortableApp) consume, so transport actions here and Space/
// arrow-key shortcuts operate on one enhanced-audio session, not two.
// Split into two hooks (#5006): Player is the one consumer that genuinely
// needs the high-frequency progress fields (it renders the progress bar),
// so it subscribes to both; low-frequency-only consumers (ComfortableApp,
// usePlayTrack, usePlaylistContextActions) use usePlaybackControls() alone
// and no longer re-render on the 10Hz position tick.
import { usePlaybackControls, usePlaybackProgress } from '@/contexts/PlaybackSessionContext';

// Redux hooks and actions
import { useSelector } from 'react-redux';
import { playerSelectors } from '@/store/selectors';

const Player = () => {
  // Queue panel visibility state
  const [queuePanelOpen, setQueuePanelOpen] = useState(false);

  // Redux state for current playback info (typed selectors fix #2463)
  const currentTrack = useSelector(playerSelectors.selectCurrentTrack);
  const playerVolume = useSelector(playerSelectors.selectVolume);
  const playerIsMuted = useSelector(playerSelectors.selectIsMuted);

  const {
    isStreaming,
    streamingState,
    isPaused,
    isSeeking,
    isCommandPending,
    error: streamingError,
    handleSeek,
    handlePlayPause,
    handleNext,
    handlePrevious,
    handleVolumeChange,
    handleMuteToggle,
  } = usePlaybackControls();
  const {
    processedChunks,
    totalChunks,
    currentTime: wsCurrentTime,
  } = usePlaybackProgress();

  // Derived buffering state for UI
  const isBuffering = streamingState === 'buffering';
  const hasError = streamingState === 'error';

  // Use streaming progress as buffered percentage (chunks received / total chunks)
  const wsBufferedPercentage = totalChunks > 0 ? (processedChunks / totalChunks) * 100 : 0;

  const volume = playerVolume ?? 50;

  // Muted state - check if volume is 0 or explicitly muted
  const isMuted = volume === 0 || playerIsMuted === true;

  // Stable queue toggle handler
  const handleQueueToggle = useCallback(() => {
    setQueuePanelOpen(prev => !prev);
  }, []);

  // #4632: every prop reaching a memoized child must be referentially stable —
  // one inline arrow silently defeats that child's `React.memo` and the whole
  // fix becomes a no-op that still looks correct. These two were inline.
  const handleCloseQueue = useCallback(() => setQueuePanelOpen(false), []);
  const handleMuteClick = useCallback(() => { void handleMuteToggle(); }, [handleMuteToggle]);

  // The wrapper/button `sx` objects are spread literals, so they were rebuilt
  // 10x/second and re-serialized by emotion even though only one field varies.
  const queuePanelWrapperSx = useMemo(
    () => ({ ...styles.queuePanelWrapper, display: queuePanelOpen ? undefined : 'none' }),
    [queuePanelOpen]
  );
  const queueButtonSx = useMemo(() => ({
    ...styles.queueButton,
    background: queuePanelOpen ? themeVars.accentSoft : 'transparent',
    borderColor: queuePanelOpen ? themeVars.accent : themeVars.borderDefault,
    color: queuePanelOpen ? themeVars.accent : themeVars.textPrimary,
  }), [queuePanelOpen]);

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
          disabled={hasError || isSeeking || isCommandPending}
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
          isLoading={isBuffering || isCommandPending}
          disabled={hasError}
        />

        {/* Right: Volume + Queue */}
        <Box sx={styles.rightSection}>
          <VolumeControl
            volume={volume / 100}
            onVolumeChange={handleVolumeChange}
            isMuted={isMuted}
            onMuteToggle={handleMuteClick}
            disabled={hasError}
          />

          {/* Queue Button - Compact with glass effects */}
          <Box
            component="button"
            onClick={handleQueueToggle}
            sx={queueButtonSx}
            title="Toggle queue (Q)"
            aria-label="Toggle queue"
            aria-expanded={queuePanelOpen}
            aria-controls="queue-panel-region"
          >
            ♪
          </Box>
        </Box>
      </Box>

      {/* Queue Panel - Always mounted; hidden via CSS to preserve scroll + focus (#2541) */}
      <Box
        id="queue-panel-region"
        sx={queuePanelWrapperSx}
      >
        <QueuePanel
          collapsed={false}
          onToggleCollapse={handleCloseQueue}
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
