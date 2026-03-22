/**
 * Player Controls Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Integrated playback controls consuming Redux player state:
 * - Play/pause/seek controls
 * - Volume control with mute
 * - Next/previous navigation
 * - Preset selection
 * - Current track info display
 *
 * Phase C.2: Advanced UI Components
 * Refactored (CQ-11): Uses Redux state exclusively, no local WS subscription.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { tokens } from '@/design-system';
import { usePlayer } from '@/hooks/shared/useReduxState';
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';
import { TrackInfo } from './TrackInfo';
import { ProgressBar } from './ProgressBar';
import { TransportControls } from './TransportControls';
import { VolumeControl } from './VolumeControl';
import { PresetSelector } from './PresetSelector';

interface PlayerControlsProps {
  disabled?: boolean;
  compact?: boolean;
  showPresetSelector?: boolean;
}

export function PlayerControls({
  disabled = false,
  compact = false,
  showPresetSelector = true,
}: PlayerControlsProps) {
  const player = usePlayer();
  const { seek: controlSeek, next, previous } = usePlaybackControl();

  const handlePlayPause = () => {
    player.togglePlay();
  };

  const handleSeek = async (position: number) => {
    player.seek(position);
    await controlSeek(position);
  };

  const handleVolumeChange = (value: number) => {
    player.setVolume(value);
    player.setMuted(false);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.lg,
        padding: tokens.spacing.lg,
        background: tokens.colors.bg.secondary,
        borderRadius: '12px',
        border: `1px solid ${tokens.colors.border.medium}`,
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? 'none' : 'auto',
      }}
    >
      {!compact && player.currentTrack && (
        <TrackInfo
          title={player.currentTrack.title}
          artist={player.currentTrack.artist}
        />
      )}

      <ProgressBar
        currentTime={player.currentTime}
        duration={player.duration}
        onSeek={handleSeek}
      />

      <TransportControls
        isPlaying={player.isPlaying}
        isLoading={player.isLoading}
        onPlayPause={handlePlayPause}
        onNext={() => next()}
        onPrevious={() => previous()}
      />

      <VolumeControl
        volume={player.volume}
        isMuted={player.isMuted}
        onVolumeChange={handleVolumeChange}
        onToggleMute={player.toggleMute}
      />

      {showPresetSelector && (
        <PresetSelector
          activePreset={player.preset}
          onSelect={player.setPreset}
        />
      )}
    </div>
  );
}

export default PlayerControls;
