/**
 * useKeyboardSeek - coalesced keyboard seeking for the progress bar (#5885).
 *
 * Holding an arrow key auto-repeats at ~30 Hz, and every keydown used to call
 * onSeek — each one stops the engine, resets the PCM buffer and restarts the
 * backend stream, and the burst overran the backend's 10 msg/s limiter, whose
 * rejections could drop the final target. Like a drag (#5625), a key burst now
 * commits at most two seeks: the first press seeks at once (a single tap stays
 * immediate), further presses within KEY_SEEK_SETTLE_MS only move the preview
 * target, and that target is committed once the keys have been quiet that long.
 */

import { KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { keyboardSeekTarget } from './progressBarMath';

/** Quiet time after the last keydown before a burst's target is committed. */
export const KEY_SEEK_SETTLE_MS = 300;

export interface UseKeyboardSeekArgs {
  currentTime: number;
  duration: number;
  onSeek: (position: number) => void;
  disabled: boolean;
}

export function useKeyboardSeek({ currentTime, duration, onSeek, disabled }: UseKeyboardSeekArgs) {
  // Where the current burst points, for the progress display.
  const [keyboardTarget, setKeyboardTarget] = useState<number | null>(null);
  // Steps accumulate from the burst's target: the playback clock does not
  // advance to it until the committed seek lands.
  const targetRef = useRef<number | null>(null);
  // A target newer than the one last sent to onSeek.
  const uncommittedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSeekRef = useRef(onSeek);
  onSeekRef.current = onSeek;

  const settle = useCallback(() => {
    timerRef.current = null;
    const target = targetRef.current;
    const uncommitted = uncommittedRef.current;
    targetRef.current = null;
    uncommittedRef.current = false;
    setKeyboardTarget(null);
    if (uncommitted && target !== null) onSeekRef.current(target);
  }, []);

  useEffect(() => () => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      const target = keyboardSeekTarget(event.key, targetRef.current ?? currentTime, duration);
      if (target === null) return;

      event.preventDefault();
      targetRef.current = target;
      setKeyboardTarget(target);
      if (timerRef.current === null) {
        onSeekRef.current(target); // leading edge: a single press seeks now
      } else {
        clearTimeout(timerRef.current);
        uncommittedRef.current = true;
      }
      timerRef.current = setTimeout(settle, KEY_SEEK_SETTLE_MS);
    },
    [disabled, duration, currentTime, settle]
  );

  return { handleKeyDown, keyboardTarget };
}
