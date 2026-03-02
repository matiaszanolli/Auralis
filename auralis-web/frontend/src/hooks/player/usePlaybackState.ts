/**
 * usePlaybackState Hook
 *
 * Listen-only hook for tracking playback state from WebSocket messages.
 * Does not initiate any actions, just subscribes to state changes.
 */

import { useState } from 'react';
import { useWebSocketSubscription } from '../websocket/useWebSocketSubscription';
import type { TrackInfo } from '../../types/websocket';
import type {
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
  // Standardized to camelCase (fixes #2276)
  gaplessEnabled: boolean;
  crossfadeEnabled: boolean;
  crossfadeDuration: number;
  isLoading: boolean;
  error: string | null;
}

const INITIAL_STATE: PlaybackState = {
  currentTrack: null,
  isPlaying: false,
  volume: 80,  // 0-100 scale, matches backend PlayerState default (issue #2251)
  position: 0,
  duration: 0,
  queue: [],
  queueIndex: -1,
  // Standardized to camelCase (fixes #2276)
  gaplessEnabled: true,
  crossfadeEnabled: true,
  crossfadeDuration: 3.0,
  isLoading: false,
  error: null,
};

/**
 * Subscribe to WebSocket playback state messages.
 * Returns the current playback state.
 */
export function usePlaybackState(): PlaybackState {
  const [state, setState] = useState<PlaybackState>(INITIAL_STATE);

  // Subscribe to low-frequency playback state events only. position_changed is
  // intentionally excluded — it fires at 10Hz and would cause 10 re-renders/sec
  // in all usePlaybackState consumers. Use usePlaybackPosition() for live position.
  // Removing position_changed also shrinks the subscription to 7 types, reducing
  // the missed-message window on WS reconnect (fixes #2542, #2558).
  useWebSocketSubscription(
    [
      'player_state',
      'playback_started',
      'playback_paused',
      'playback_stopped',
      'track_loaded',
      'track_changed',
      'volume_changed',
    ],
    (message) => {
      setState((prevState) => {
        switch (message.type) {
          case 'player_state': {
            const msg = message as PlayerStateMessage;
            // Map snake_case from backend to camelCase for frontend
            const data = msg.data as any;
            return {
              currentTrack: data.current_track ?? null,
              isPlaying: data.is_playing ?? false,
              volume: data.volume ?? 80,  // 0-100 scale, matches backend default (issue #2251)
              position: data.current_time ?? 0,
              duration: data.duration ?? 0,
              queue: data.queue ?? [],
              queueIndex: data.queue_index ?? -1,
              // Backend sends snake_case; mapped to camelCase (fixes #2276)
              gaplessEnabled: data.gapless_enabled ?? true,
              crossfadeEnabled: data.crossfade_enabled ?? true,
              crossfadeDuration: data.crossfade_duration ?? 3.0,
              isLoading: false,
              error: null,
            };
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
        setPosition((msg.data as any).current_time ?? msg.data.position ?? 0);
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
 *
 * DEPRECATED: Use Redux selector selectCurrentTrack instead.
 * This hook may miss initial state if component mounts after playback starts.
 *
 * @deprecated Use `useSelector(selectCurrentTrack)` from Redux instead.
 */
export function useCurrentTrack(): TrackInfo | null {
  const [track, setTrack] = useState<TrackInfo | null>(null);

  useWebSocketSubscription(
    ['player_state', 'track_loaded', 'track_changed'],
    (message) => {
      if (message.type === 'player_state') {
        const msg = message as PlayerStateMessage;
        // Backend sends current_track (snake_case)
        const data = msg.data as any;
        setTrack(data.current_track ?? null);
      } else if (message.type === 'track_loaded' || message.type === 'track_changed') {
        // TrackLoadedMessage.data = { track_path } and TrackChangedMessage.data = { action }.
        // Neither type includes a 'track' field, so the previous branch was dead
        // code that silently missed updates.  Track info comes exclusively from
        // player_state messages (fixes #2355).
      }
    }
  );

  return track;
}

/**
 * Subscribe to playback status (playing/paused) only.
 * Useful for play/pause button.
 *
 * DEPRECATED: Use Redux selector selectIsPlaying instead.
 * This hook may miss initial state if component mounts after playback starts.
 *
 * @deprecated Use `useSelector(selectIsPlaying)` from Redux instead.
 */
export function useIsPlaying(): boolean {
  const [isPlaying, setIsPlaying] = useState(false);

  useWebSocketSubscription(
    ['player_state', 'playback_started', 'playback_paused', 'playback_stopped'],
    (message) => {
      switch (message.type) {
        case 'player_state': {
          const msg = message as PlayerStateMessage;
          // Backend sends is_playing (snake_case)
          const data = msg.data as any;
          setIsPlaying(data.is_playing ?? false);
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
  const [volume, setVolume] = useState(80);  // 0-100 scale, matches backend default (issue #2251)

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
