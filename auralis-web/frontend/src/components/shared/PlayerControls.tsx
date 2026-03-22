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

import { useState } from 'react';
import { tokens } from '@/design-system';
import { formatDuration } from '@/utils/timeFormat';
import { usePlayer } from '@/hooks/shared/useReduxState';
import { usePlaybackControl } from '@/hooks/player/usePlaybackControl';
import type { PresetName } from '@/store/slices/playerSlice';

interface PlayerControlsProps {
  disabled?: boolean;
  compact?: boolean;
  showPresetSelector?: boolean;
}

const PRESETS = [
  { name: 'Adaptive', icon: '🎯', value: 'adaptive' },
  { name: 'Gentle', icon: '🌸', value: 'gentle' },
  { name: 'Warm', icon: '🔥', value: 'warm' },
  { name: 'Bright', icon: '✨', value: 'bright' },
  { name: 'Punchy', icon: '💥', value: 'punchy' },
] as const;

// --- Sub-components (each < 100 lines) ---

function TrackInfo({ title, artist }: { title: string; artist: string }) {
  return (
    <div
      style={{
        paddingBottom: tokens.spacing.md,
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      <div
        style={{
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.text.primary,
          marginBottom: tokens.spacing.xs,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.secondary,
        }}
      >
        {artist}
      </div>
    </div>
  );
}

function ProgressBar({
  currentTime,
  duration,
  onSeek,
}: {
  currentTime: number;
  duration: number;
  onSeek: (position: number) => void;
}) {
  const [isSeeking, setIsSeeking] = useState(false);
  const seekPercentage = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.sm }}>
      <div
        role="slider"
        aria-label="Seek"
        aria-valuenow={Math.round(currentTime)}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        tabIndex={0}
        style={{
          height: '6px',
          background: tokens.colors.bg.elevated,
          borderRadius: '3px',
          overflow: 'hidden',
          cursor: 'pointer',
        }}
        onClick={(e) => {
          const rect = (e.target as HTMLElement).getBoundingClientRect();
          const percentage = (e.clientX - rect.left) / rect.width;
          onSeek(percentage * duration);
        }}
        onMouseDown={() => setIsSeeking(true)}
        onMouseUp={() => setIsSeeking(false)}
        onKeyDown={(e) => {
          const step = 5;
          if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault();
            onSeek(Math.min(currentTime + step, duration));
          } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault();
            onSeek(Math.max(currentTime - step, 0));
          } else if (e.key === 'Home') {
            e.preventDefault();
            onSeek(0);
          } else if (e.key === 'End') {
            e.preventDefault();
            onSeek(duration);
          }
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${seekPercentage}%`,
            background: tokens.colors.accent.primary,
            transition: isSeeking ? 'none' : 'width 0.1s linear',
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.tertiary,
        }}
      >
        <span>{formatDuration(currentTime)}</span>
        <span>{formatDuration(duration)}</span>
      </div>
    </div>
  );
}

function TransportControls({
  isPlaying,
  isLoading,
  onPlayPause,
  onNext,
  onPrevious,
}: {
  isPlaying: boolean;
  isLoading: boolean;
  onPlayPause: () => void;
  onNext: () => void;
  onPrevious: () => void;
}) {
  const smallButtonStyle = {
    width: '44px',
    height: '44px',
    border: 'none',
    borderRadius: '50%',
    background: tokens.colors.bg.tertiary,
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.lg,
    cursor: isLoading ? 'not-allowed' : 'pointer',
    opacity: isLoading ? 0.5 : 0.8,
    transition: 'all 0.2s',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  } as const;

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing.md }}>
      <button onClick={onPrevious} disabled={isLoading} aria-label="Previous" style={smallButtonStyle}>
        ⏮️
      </button>
      <button
        onClick={onPlayPause}
        disabled={isLoading}
        aria-label={isPlaying ? 'Pause' : 'Play'}
        style={{
          width: '64px',
          height: '64px',
          border: `2px solid ${tokens.colors.accent.primary}`,
          borderRadius: '50%',
          background: tokens.colors.accent.primary,
          color: tokens.colors.text.primary,
          fontSize: tokens.typography.fontSize.xl,
          fontWeight: tokens.typography.fontWeight.bold,
          cursor: isLoading ? 'not-allowed' : 'pointer',
          opacity: isLoading ? 0.5 : 0.9,
          transition: 'all 0.2s',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {isLoading ? '⏳' : isPlaying ? '⏸️' : '▶️'}
      </button>
      <button onClick={onNext} disabled={isLoading} aria-label="Next" style={smallButtonStyle}>
        ⏭️
      </button>
    </div>
  );
}

function VolumeControl({
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
}: {
  volume: number;
  isMuted: boolean;
  onVolumeChange: (value: number) => void;
  onToggleMute: () => void;
}) {
  const displayVolume = isMuted ? 0 : volume;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing.md,
        paddingTop: tokens.spacing.md,
        borderTop: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      <button
        onClick={onToggleMute}
        aria-label={isMuted ? 'Unmute' : 'Mute'}
        style={{
          width: '32px',
          height: '32px',
          border: 'none',
          borderRadius: '6px',
          background: isMuted ? tokens.colors.semantic.warning : tokens.colors.bg.tertiary,
          color: tokens.colors.text.primary,
          cursor: 'pointer',
          fontSize: tokens.typography.fontSize.md,
          opacity: 0.8,
          transition: 'all 0.2s',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {isMuted ? '🔇' : '🔊'}
      </button>
      <input
        type="range"
        min="0"
        max="100"
        value={displayVolume}
        onChange={(e) => onVolumeChange(parseInt(e.target.value))}
        aria-label="Volume"
        style={{
          flex: 1,
          cursor: 'pointer',
          height: '6px',
          borderRadius: '3px',
          appearance: 'none',
          WebkitAppearance: 'none',
          background: `linear-gradient(to right, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.primary} ${displayVolume}%, ${tokens.colors.bg.elevated} ${displayVolume}%, ${tokens.colors.bg.elevated} 100%)`,
        }}
      />
      <div
        style={{
          fontSize: tokens.typography.fontSize.sm,
          color: tokens.colors.text.tertiary,
          minWidth: '35px',
          textAlign: 'right',
        }}
      >
        {displayVolume}%
      </div>
    </div>
  );
}

function PresetSelector({
  activePreset,
  onSelect,
}: {
  activePreset: string;
  onSelect: (preset: PresetName) => void;
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: tokens.spacing.sm,
        paddingTop: tokens.spacing.md,
        borderTop: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      {PRESETS.map((preset) => (
        <button
          key={preset.value}
          onClick={() => onSelect(preset.value)}
          aria-label={preset.name}
          aria-pressed={activePreset === preset.value}
          style={{
            flex: 1,
            padding: tokens.spacing.sm,
            border: `2px solid ${activePreset === preset.value ? tokens.colors.accent.primary : tokens.colors.border.light}`,
            borderRadius: '6px',
            background: activePreset === preset.value ? `${tokens.colors.accent.primary}20` : tokens.colors.bg.tertiary,
            color: tokens.colors.text.primary,
            cursor: 'pointer',
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: activePreset === preset.value ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
            transition: 'all 0.2s',
          }}
        >
          {preset.icon}
        </button>
      ))}
    </div>
  );
}

// --- Main component ---

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
