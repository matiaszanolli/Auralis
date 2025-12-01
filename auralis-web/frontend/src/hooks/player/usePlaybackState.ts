/**
 * usePlaybackState Hook
 *
 * Listen-only hook for tracking playback state from WebSocket messages.
 * Does not initiate any actions, just subscribes to state changes.
 */

import { useState, useEffect } from 'react';
import { useWebSocketSubscription } from '../websocket/useWebSocketSubscription';
import type { PlayerStateData, TrackInfo } from '../../types/websocket';
import type {
  PlaybackStartedMessage,
  PlaybackPausedMessage,
  PlaybackStoppedMessage,
  TrackLoadedMessage,
  TrackChangedMessage,
  PositionChangedMessage,
  VolumeChangedMessage,
  PlayerStateMessage,
} from '../../types/websocket';

export interface PlaybackState {
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  volume: number;
  position: number;
  duration: number;
  queue: TrackInfo[];
  queueIndex: number;
  gapless_enabled: boolean;
  crossfade_enabled: boolean;
  crossfade_duration: number;
  isLoading: boolean;
  error: string | null;
}

const INITIAL_STATE: PlaybackState = {
  currentTrack: null,
  isPlaying: false,
  volume: 1.0,
  position: 0,
  duration: 0,
  queue: [],
  queueIndex: -1,
  gapless_enabled: true,
  crossfade_enabled: true,
  crossfade_duration: 3.0,
  isLoading: false,
  error: null,
};

/**
 * Subscribe to WebSocket playback state messages.
 * Returns the current playback state.
 */
export function usePlaybackState(): PlaybackState {
  const [state, setState] = useState<PlaybackState>(INITIAL_STATE);

  // Subscribe to all playback-related messages
  useWebSocketSubscription(
    [
      'player_state',
      'playback_started',
      'playback_paused',
      'playback_stopped',
      'track_loaded',
      'track_changed',
      'position_changed',
      'volume_changed',
    ],
    (message) => {
      setState((prevState) => {
        switch (message.type) {
          case 'player_state': {
            const msg = message as PlayerStateMessage;
            return {
              ...msg.data,
              isLoading: false,
              error: null,
            } as PlaybackState;
          }

          case 'playback_started': {
            return {
              ...prevState,
              isPlaying: true,
              isLoading: false,
              error: null,
            };
          }

          case 'playback_paused': {
            return {
              ...prevState,
              isPlaying: false,
              isLoading: false,
              error: null,
            };
          }

          case 'playback_stopped': {
            return {
              ...prevState,
              isPlaying: false,
              currentTrack: null,
              queue: [],
              position: 0,
              queueIndex: -1,
              isLoading: false,
              error: null,
            };
          }

          case 'track_loaded': {
            return {
              ...prevState,
              isLoading: false,
              error: null,
            };
          }

          case 'track_changed': {
            return {
              ...prevState,
              position: 0, // Reset position when track changes
              isLoading: false,
              error: null,
            };
          }

          case 'position_changed': {
            const msg = message as PositionChangedMessage;
            return {
              ...prevState,
              position: msg.data.position,
            };
          }

          case 'volume_changed': {
            const msg = message as VolumeChangedMessage;
            return {
              ...prevState,
              volume: msg.data.volume,
            };
          }

          default:
            return prevState;
        }
      });
    }
  );

  return state;
}

/**
 * Subscribe to position changes only.
 * Useful for progress bar updates.
 */
export function usePlaybackPosition(): { position: number; duration: number } {
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);

  useWebSocketSubscription(
    ['player_state', 'position_changed', 'track_loaded', 'track_changed'],
    (message) => {
      if (message.type === 'player_state') {
        const msg = message as PlayerStateMessage;
        setPosition(msg.data.position);
        setDuration(msg.data.duration);
      } else if (message.type === 'position_changed') {
        const msg = message as PositionChangedMessage;
        setPosition(msg.data.position);
      } else if (message.type === 'track_changed' || message.type === 'track_loaded') {
        setPosition(0);
      }
    }
  );

  return { position, duration };
}

/**
 * Subscribe to current track changes only.
 * Useful for track info display.
 */
export function useCurrentTrack(): TrackInfo | null {
  const [track, setTrack] = useState<TrackInfo | null>(null);

  useWebSocketSubscription(
    ['player_state', 'track_loaded', 'track_changed'],
    (message) => {
      if (message.type === 'player_state') {
        const msg = message as PlayerStateMessage;
        setTrack(msg.data.currentTrack);
      }
    }
  );

  return track;
}

/**
 * Subscribe to playback status (playing/paused) only.
 * Useful for play/pause button.
 */
export function useIsPlaying(): boolean {
  const [isPlaying, setIsPlaying] = useState(false);

  useWebSocketSubscription(
    ['player_state', 'playback_started', 'playback_paused', 'playback_stopped'],
    (message) => {
      switch (message.type) {
        case 'player_state': {
          const msg = message as PlayerStateMessage;
          setIsPlaying(msg.data.isPlaying);
          break;
        }
        case 'playback_started':
          setIsPlaying(true);
          break;
        case 'playback_paused':
        case 'playback_stopped':
          setIsPlaying(false);
          break;
      }
    }
  );

  return isPlaying;
}

/**
 * Subscribe to volume changes only.
 * Useful for volume control.
 */
export function useVolume(): number {
  const [volume, setVolume] = useState(1.0);

  useWebSocketSubscription(
    ['player_state', 'volume_changed'],
    (message) => {
      if (message.type === 'player_state') {
        const msg = message as PlayerStateMessage;
        setVolume(msg.data.volume);
      } else if (message.type === 'volume_changed') {
        const msg = message as VolumeChangedMessage;
        setVolume(msg.data.volume);
      }
    }
  );

  return volume;
}
