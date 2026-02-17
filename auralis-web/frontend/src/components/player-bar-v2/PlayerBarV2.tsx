/**
 * PlayerBarV2 - Presentational player bar component
 *
 * Props-based API (vs the hook-based Player.tsx) for testability
 * and use as a controlled component in layouts.
 */

import React from 'react';

// ============================================================================
// Types
// ============================================================================

export interface PlayerBarTrack {
  id: number;
  title: string;
  artist: string;
  album: string;
  artwork_url?: string;
  duration: number;
}

export interface PlayerBarState {
  currentTrack: PlayerBarTrack | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isEnhanced: boolean;
  queue?: PlayerBarTrack[];
  queueIndex?: number;
}

export interface PlayerBarV2Props {
  player: PlayerBarState;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (time: number) => void;
  onVolumeChange: (volume: number) => void;
  onEnhancementToggle: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

// ============================================================================
// Helpers
// ============================================================================

function formatTime(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// ============================================================================
// Component
// ============================================================================

export const PlayerBarV2: React.FC<PlayerBarV2Props> = ({
  player,
  onPlay,
  onPause,
  onSeek,
  onVolumeChange,
  onEnhancementToggle,
  onPrevious,
  onNext,
}) => {
  const { currentTrack, isPlaying, currentTime, duration, volume, isEnhanced } = player;

  return (
    <div role="region" aria-label="Player controls">
      {/* Track info */}
      {currentTrack && (
        <div>
          {currentTrack.artwork_url && (
            <img
              src={currentTrack.artwork_url}
              alt={`${currentTrack.album} artwork`}
            />
          )}
          <span>{currentTrack.title}</span>
          <span>{currentTrack.artist}</span>
        </div>
      )}

      {/* Navigation and playback controls */}
      <div>
        <button aria-label="Previous track" onClick={onPrevious}>
          ⏮
        </button>

        {isPlaying ? (
          <button aria-label="Pause" onClick={onPause}>
            ⏸
          </button>
        ) : (
          <button aria-label="Play" onClick={onPlay}>
            ▶
          </button>
        )}

        <button aria-label="Next track" onClick={onNext}>
          ⏭
        </button>
      </div>

      {/* Progress bar */}
      <div>
        <span>{formatTime(currentTime)}</span>
        <input
          type="range"
          aria-label="Seek"
          min={0}
          max={duration || 0}
          step={0.1}
          value={currentTime}
          onChange={(e) => onSeek(Number(e.target.value))}
        />
        <span>{formatTime(duration)}</span>
      </div>

      {/* Volume control */}
      <div>
        <button
          aria-label={volume > 0 ? 'Mute' : 'Unmute'}
          onClick={() => onVolumeChange(volume > 0 ? 0 : 1)}
        >
          {volume > 0 ? '🔊' : '🔇'}
        </button>
        <input
          type="range"
          aria-label="Volume"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={(e) => onVolumeChange(Number(e.target.value))}
          onPointerDown={() => onVolumeChange(volume)}
        />
      </div>

      {/* Enhancement toggle */}
      <div>
        <button
          aria-label={isEnhanced ? 'Disable enhancement' : 'Enable enhancement'}
          onClick={onEnhancementToggle}
        >
          {isEnhanced ? 'Enhanced' : 'Original'}
        </button>
      </div>
    </div>
  );
};

export default PlayerBarV2;
