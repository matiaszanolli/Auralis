/**
 * The one-job effects usePlaybackTransport composes (#6703).
 *
 * Each hook owns exactly one effect concern, so a dependency-array fix in one
 * (#3624, #4668, #5621 were all in this territory) cannot reorder or re-fire
 * another. usePlaybackTransport calls them in the order the effects used to be
 * declared, which keeps the effect run order identical.
 *
 * @module hooks/enhancement/playbackTransportEffects
 */

import { useEffect, useRef } from 'react';
import { useSelector } from 'react-redux';
import type { StreamCommand } from '@/types/ws/commands';
import type { useWebSocketContext } from '@/contexts/WebSocketContext';
import { selectIsMuted, selectVolume, engineGainFromPlayerState } from '@/store/slices/playerSlice';
import type { AudioPlaybackEngine } from '@/services/audio/AudioPlaybackEngine';

const DEBUG = import.meta.env.DEV;

type EngineRef = React.MutableRefObject<AudioPlaybackEngine | null>;

/**
 * #5607: WS-sourced volume changes (volume_changed / player_state.volume) and
 * mute toggles reach only Redux; the imperative slider path is the only thing
 * that touches the engine directly. Re-apply whenever the authoritative gain
 * changes so the current engine always matches the UI, whatever the source.
 * (Each NEW engine is seeded from the same conversion in useEnhancedStreamStart.)
 */
export function useEngineGainSync(playbackEngineRef: EngineRef): void {
  const volume = useSelector(selectVolume);
  const isMuted = useSelector(selectIsMuted);
  const engineGain = engineGainFromPlayerState({ volume, isMuted });
  useEffect(() => {
    playbackEngineRef.current?.setVolume(engineGain);
  }, [engineGain, playbackEngineRef]);
}

/**
 * Poll the engine's playback time at 10 Hz into `setCurrentTime`. Gated on
 * isPlaying so the interval doesn't fire setCurrentTime gratuitously when idle
 * (#3970); an unchanged time keeps the previous state object.
 */
export function usePlaybackClock(
  isPlaying: boolean,
  playbackEngineRef: EngineRef,
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>
): void {
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      const time = playbackEngineRef.current?.getCurrentPlaybackTime() || 0;
      setCurrentTime((prev) => (time === prev ? prev : time));
    }, 100);
    return () => clearInterval(interval);
  }, [isPlaying, playbackEngineRef, setCurrentTime]);
}

/**
 * Follow Redux isPlaying on the engine, so a pause/stop command stops it
 * immediately instead of waiting for buffered audio to drain (#2252).
 *
 * #3624: isPaused is read through a ref so it does not re-run the effect;
 * having it in the deps caused two pausePlayback() calls per transition,
 * because setIsPaused(true) re-fired the effect.
 */
export function useEnginePlayingSync(
  isPlaying: boolean,
  isPaused: boolean,
  playbackEngineRef: EngineRef,
  resumePlayback: () => void,
  setIsPaused: React.Dispatch<React.SetStateAction<boolean>>
): void {
  const isPausedRef = useRef(isPaused);
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);

  useEffect(() => {
    const engine = playbackEngineRef.current;
    if (!engine) return;
    if (!isPlaying) {
      engine.pausePlayback();
      setIsPaused(true);
    } else if (isPausedRef.current) {
      resumePlayback();
    }
  }, [isPlaying, resumePlayback, playbackEngineRef, setIsPaused]);
}

/**
 * Register the resume-position getter the WS reconnect path reads (#3185), for
 * this stream's command and, when it also accepts them, normal streams.
 *
 * Depends on `setResumePositionGetter` (stable, #3730), not the whole context:
 * the context object's identity changes on every WS status flicker, which used
 * to unregister and re-register the getters for no reason (#4668, #5621).
 */
export function useResumePositionRegistration(
  setResumePositionGetter: ReturnType<typeof useWebSocketContext>['setResumePositionGetter'],
  sendType: StreamCommand['type'],
  acceptNormalStream: boolean,
  playbackEngineRef: EngineRef
): void {
  useEffect(() => {
    const getPosition = () => playbackEngineRef.current?.getCurrentPlaybackTime() ?? 0;
    setResumePositionGetter(sendType, getPosition);
    if (acceptNormalStream) setResumePositionGetter('play_normal', getPosition);
    return () => {
      setResumePositionGetter(sendType, null);
      if (acceptNormalStream) setResumePositionGetter('play_normal', null);
    };
  }, [setResumePositionGetter, sendType, acceptNormalStream, playbackEngineRef]);
}

/**
 * On WS disconnect keep the engine and its buffer, so buffered audio plays
 * through while the socket reconnects (#3185, replacing #2847's teardown).
 * Only `onDisconnectExtra` runs.
 */
export function useDisconnectKeepalive(
  isConnected: boolean,
  playbackEngineRef: EngineRef,
  logPrefix: string,
  onDisconnectExtra?: () => void
): void {
  useEffect(() => {
    if (isConnected || !playbackEngineRef.current) return;
    DEBUG && console.log(`${logPrefix} WebSocket disconnected - keeping playback engine alive`);
    onDisconnectExtra?.();
  }, [isConnected, logPrefix, onDisconnectExtra, playbackEngineRef]);
}
