/**
 * Volume and mute handlers for PlaybackSessionProvider (#6275).
 *
 * Volume is 0-1 in the WebSocket/AudioEngine and 0-100 in Redux/the backend; unmute restores the
 * level the user had before muting.
 *
 * @module contexts/usePlaybackVolume
 */

import { useCallback, useRef } from 'react';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store';
import { setVolume as setVolumeAction } from '@/store/slices/playerSlice';

interface UsePlaybackVolumeArgs {
  /** Redux volume, 0-100. */
  playerVolume: number | null | undefined;
  playerIsMuted: boolean | null | undefined;
  setStreamingVolume: (volume: number) => void;
}

export function usePlaybackVolume({ playerVolume, playerIsMuted, setStreamingVolume }: UsePlaybackVolumeArgs) {
  const dispatch = useDispatch<AppDispatch>();
  const preMuteVolumeRef = useRef<number>(0.5);

  const handleVolumeChange = useCallback(async (vol: number) => {
    try {
      setStreamingVolume(vol);
      dispatch(setVolumeAction(Math.round(vol * 100)));
    } catch (err) {
      console.error('[PlaybackSession] Volume command error:', err);
    }
  }, [setStreamingVolume, dispatch]);

  const handleMuteToggle = useCallback(async (): Promise<boolean> => {
    const volume = playerVolume ?? 50;
    const isMuted = volume === 0 || playerIsMuted === true;

    if (isMuted) {
      await handleVolumeChange(preMuteVolumeRef.current);
      return false;
    }
    preMuteVolumeRef.current = volume / 100;
    await handleVolumeChange(0);
    return true;
  }, [playerVolume, playerIsMuted, handleVolumeChange]);

  return { handleVolumeChange, handleMuteToggle };
}
