/**
 * Player Controls Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Integrated playback controls with WebSocket synchronization:
 * - Play/pause/seek controls
 * - Volume control with mute
 * - Next/previous navigation
 * - Preset selection
 * - Current track info display
 *
 * Phase C.2: Advanced UI Components
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { useState } from 'react';
import { tokens } from '@/design-system';
import { usePlayerCommands, usePlayerStateUpdates } from '@/hooks/websocket/useWebSocketProtocol';

interface PlayerState {
  isPlaying: boolean;
  currentTrack?: {
    id: number;
    title: string;
    artist: string;
    duration: number;
  };
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  preset: string;
  isLoading: boolean;
}

interface PlayerControlsProps {
  /**
   * Disable controls (e.g., when not connected)
   */
  disabled?: boolean;
  /**
   * Compact layout without track info
   */
  compact?: boolean;
  /**
   * Show preset selector
   */
  showPresetSelector?: boolean;
}

const PRESETS = [
  { name: 'Adaptive', icon: '🎯', value: 'adaptive' },
  { name: 'Gentle', icon: '🌸', value: 'gentle' },
  { name: 'Warm', icon: '🔥', value: 'warm' },
  { name: 'Bright', icon: '✨', value: 'bright' },
  { name: 'Punchy', icon: '💥', value: 'punchy' },
];

/**
 * Format time display
 */
function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Player Controls Component
 */
export function PlayerControls({
  disabled = false,
  compact = false,
  showPresetSelector = true,
}: PlayerControlsProps) {
  const [playerState, setPlayerState] = useState<PlayerState>({
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    volume: 70,
    isMuted: false,
    preset: 'adaptive',
    isLoading: false,
  });

  const [localVolume, setLocalVolume] = useState(70);
  const [isSeeking, setIsSeeking] = useState(false);

  const commands = usePlayerCommands();

  // Subscribe to player state updates
  usePlayerStateUpdates((state) => {
    setPlayerState((prev) => ({
      ...prev,
      ...state,
    }));
  });

  const handlePlayPause = async () => {
    try {
      if (playerState.isPlaying) {
        await commands.pause();
      } else {
        await commands.play();
      }
    } catch (error) {
      console.error('Failed to toggle playback:', error);
    }
  };

  const handleSeek = async (position: number) => {
    try {
      setPlayerState((prev) => ({
        ...prev,
        currentTime: position,
      }));
      await commands.seek(position);
      setIsSeeking(false);
    } catch (error) {
      console.error('Failed to seek:', error);
      setIsSeeking(false);
    }
  };

  const handleVolumeChange = (value: number) => {
    setLocalVolume(value);
    setPlayerState((prev) => ({
      ...prev,
      volume: value,
      isMuted: false,
    }));
  };

  const handleMute = () => {
    setPlayerState((prev) => ({
      ...prev,
      isMuted: !prev.isMuted,
    }));
  };

  const handleNext = async () => {
    try {
      await commands.next();
    } catch (error) {
      console.error('Failed to skip to next:', error);
    }
  };

  const handlePrevious = async () => {
    try {
      await commands.previous();
    } catch (error) {
      console.error('Failed to skip to previous:', error);
    }
  };

  const seekPercentage = playerState.duration > 0 ? (playerState.currentTime / playerState.duration) * 100 : 0;

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
      {/* Current Track Info */}
      {!compact && playerState.currentTrack && (
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
            {playerState.currentTrack.title}
          </div>
          <div
            style={{
              fontSize: tokens.typography.fontSize.xs,
              color: tokens.colors.text.secondary,
            }}
          >
            {playerState.currentTrack.artist}
          </div>
        </div>
      )}

      {/* Progress Bar */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: tokens.spacing.sm,
        }}
      >
        <div
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
            const newTime = percentage * playerState.duration;
            handleSeek(newTime);
          }}
          onMouseDown={() => setIsSeeking(true)}
          onMouseUp={() => setIsSeeking(false)}
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
          <span>{formatTime(playerState.currentTime)}</span>
          <span>{formatTime(playerState.duration)}</span>
        </div>
      </div>

      {/* Playback Controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: tokens.spacing.md,
        }}
      >
        <button
          onClick={handlePrevious}
          disabled={playerState.isLoading}
          aria-label="Previous"
          style={{
            width: '44px',
            height: '44px',
            border: 'none',
            borderRadius: '50%',
            background: tokens.colors.bg.tertiary,
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.lg,
            cursor: playerState.isLoading ? 'not-allowed' : 'pointer',
            opacity: playerState.isLoading ? 0.5 : 0.8,
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseOver={(e) => {
            if (!playerState.isLoading) {
              (e.target as HTMLButtonElement).style.opacity = '1';
              (e.target as HTMLButtonElement).style.background = tokens.colors.bg.elevated;
            }
          }}
          onMouseOut={(e) => {
            if (!playerState.isLoading) {
              (e.target as HTMLButtonElement).style.opacity = '0.8';
              (e.target as HTMLButtonElement).style.background = tokens.colors.bg.tertiary;
            }
          }}
        >
          ⏮️
        </button>

        <button
          onClick={handlePlayPause}
          disabled={playerState.isLoading}
          aria-label={playerState.isPlaying ? 'Pause' : 'Play'}
          style={{
            width: '64px',
            height: '64px',
            border: `2px solid ${tokens.colors.accent.primary}`,
            borderRadius: '50%',
            background: tokens.colors.accent.primary,
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.xl,
            fontWeight: tokens.typography.fontWeight.bold,
            cursor: playerState.isLoading ? 'not-allowed' : 'pointer',
            opacity: playerState.isLoading ? 0.5 : 0.9,
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseOver={(e) => {
            if (!playerState.isLoading) {
              (e.target as HTMLButtonElement).style.opacity = '1';
              (e.target as HTMLButtonElement).style.transform = 'scale(1.05)';
            }
          }}
          onMouseOut={(e) => {
            if (!playerState.isLoading) {
              (e.target as HTMLButtonElement).style.opacity = '0.9';
              (e.target as HTMLButtonElement).style.transform = 'scale(1)';
            }
          }}
        >
          {playerState.isLoading ? '⏳' : playerState.isPlaying ? '⏸️' : '▶️'}
        </button>

        <button
          onClick={handleNext}
          disabled={playerState.isLoading}
          aria-label="Next"
          style={{
            width: '44px',
            height: '44px',
            border: 'none',
            borderRadius: '50%',
            background: tokens.colors.bg.tertiary,
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.lg,
            cursor: playerState.isLoading ? 'not-allowed' : 'pointer',
            opacity: playerState.isLoading ? 0.5 : 0.8,
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseOver={(e) => {
            if (!playerState.isLoading) {
              (e.target as HTMLButtonElement).style.opacity = '1';
              (e.target as HTMLButtonElement).style.background = tokens.colors.bg.elevated;
            }
          }}
          onMouseOut={(e) => {
            if (!playerState.isLoading) {
              (e.target as HTMLButtonElement).style.opacity = '0.8';
              (e.target as HTMLButtonElement).style.background = tokens.colors.bg.tertiary;
            }
          }}
        >
          ⏭️
        </button>
      </div>

      {/* Volume Control */}
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
          onClick={handleMute}
          aria-label={playerState.isMuted ? 'Unmute' : 'Mute'}
          style={{
            width: '32px',
            height: '32px',
            border: 'none',
            borderRadius: '6px',
            background: playerState.isMuted ? tokens.colors.semantic.warning : tokens.colors.bg.tertiary,
            color: tokens.colors.text.primary,
            cursor: 'pointer',
            fontSize: tokens.typography.fontSize.md,
            opacity: 0.8,
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseOver={(e) => {
            (e.target as HTMLButtonElement).style.opacity = '1';
          }}
          onMouseOut={(e) => {
            (e.target as HTMLButtonElement).style.opacity = '0.8';
          }}
        >
          {playerState.isMuted ? '🔇' : '🔊'}
        </button>

        <input
          type="range"
          min="0"
          max="100"
          value={playerState.isMuted ? 0 : localVolume}
          onChange={(e) => handleVolumeChange(parseInt(e.target.value))}
          aria-label="Volume"
          style={{
            flex: 1,
            cursor: 'pointer',
            height: '6px',
            borderRadius: '3px',
            appearance: 'none',
            WebkitAppearance: 'none',
            background: `linear-gradient(to right, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.primary} ${playerState.isMuted ? 0 : localVolume}%, ${tokens.colors.bg.elevated} ${playerState.isMuted ? 0 : localVolume}%, ${tokens.colors.bg.elevated} 100%)`,
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
          {playerState.isMuted ? '0%' : `${localVolume}%`}
        </div>
      </div>

      {/* Preset Selector */}
      {showPresetSelector && (
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
              onClick={() => {
                setPlayerState((prev) => ({
                  ...prev,
                  preset: preset.value,
                }));
              }}
              title={preset.name}
              style={{
                flex: 1,
                padding: tokens.spacing.sm,
                border: `2px solid ${
                  playerState.preset === preset.value
                    ? tokens.colors.accent.primary
                    : tokens.colors.border.light
                }`,
                borderRadius: '6px',
                background:
                  playerState.preset === preset.value
                    ? `${tokens.colors.accent.primary}20`
                    : tokens.colors.bg.tertiary,
                color: tokens.colors.text.primary,
                cursor: 'pointer',
                fontSize: tokens.typography.fontSize.sm,
                fontWeight:
                  playerState.preset === preset.value ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
                transition: 'all 0.2s',
              }}
              onMouseOver={(e) => {
                if (playerState.preset !== preset.value) {
                  (e.target as HTMLButtonElement).style.borderColor = tokens.colors.accent.primary;
                  (e.target as HTMLButtonElement).style.opacity = '0.8';
                }
              }}
              onMouseOut={(e) => {
                if (playerState.preset !== preset.value) {
                  (e.target as HTMLButtonElement).style.borderColor = tokens.colors.border.light;
                  (e.target as HTMLButtonElement).style.opacity = '1';
                }
              }}
            >
              {preset.icon}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default PlayerControls;
