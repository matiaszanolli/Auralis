/**
 * useProgressBarInteraction - Mouse/touch/keyboard seek handling for ProgressBar.
 *
 * Owns drag/hover/focus state, the position-from-event math, and the global
 * mousemove/mouseup listeners used while dragging. Extracted from
 * ProgressBar.tsx to keep the component under the 300-line guideline (#4456).
 *
 * Drag = one seek (#5625). Every mousemove/touchmove used to call onSeek —
 * and each seek stops playback, resets the PCM buffer and starts a new
 * backend stream, so scrubbing fired tens of stream restarts per gesture and
 * kept audio silent for the whole drag, with a second seek on the trailing
 * click. A drag now updates only the visual position (and the throttled ARIA
 * announcements); exactly one seek commits on release, at the last position
 * the pointer held. A plain click still seeks once: mousedown does not seek,
 * the click event does — unless a drag just committed, which the trailing
 * click is taught to swallow. Keyboard bursts get the same treatment in
 * useKeyboardSeek (#5885). The drag/touch gesture lives in useProgressBarDrag (#6275).
 */

import { MouseEvent, useCallback, useMemo, useRef, useState } from 'react';
import { positionFromPointer, progressPercent } from './progressBarMath';
import { useKeyboardSeek } from './useKeyboardSeek';
import { useProgressBarDrag } from './useProgressBarDrag';

export interface UseProgressBarInteractionArgs {
  currentTime: number;
  duration: number;
  onSeek: (position: number) => void;
  disabled: boolean;
}

/** Anything with a clientX — mouse events and Touch objects both qualify. */
interface PointLike {
  clientX: number;
}

export function useProgressBarInteraction({
  currentTime,
  duration,
  onSeek,
  disabled,
}: UseProgressBarInteractionArgs) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [hoverPosition, setHoverPosition] = useState(0);
  const [isFocused, setIsFocused] = useState(false);

  // Stable refs for values used in drag handlers to avoid recreating
  // callbacks on every playback tick (#3103)
  const durationRef = useRef(duration);
  durationRef.current = duration;
  const currentTimeRef = useRef(currentTime);
  currentTimeRef.current = currentTime;
  const onSeekRef = useRef(onSeek);
  onSeekRef.current = onSeek;

  // Handle mouse/touch position calculation (stable - reads from refs)
  const getPositionFromEvent = useCallback((event: PointLike) => {
    if (!containerRef.current) return currentTimeRef.current;

    return positionFromPointer(
      event.clientX,
      containerRef.current.getBoundingClientRect(),
      durationRef.current,
      currentTimeRef.current
    );
  }, []);

  const canSeek = !disabled && Number.isFinite(duration) && duration > 0;
  const {
    isDragging,
    dragPosition,
    liveSeekTime,
    handleMouseDown,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    consumeDragClick,
  } = useProgressBarDrag({ containerRef, getPositionFromEvent, onSeekRef, canSeek });

  // Keyboard seeks are coalesced too (#5885); see useKeyboardSeek.
  const { handleKeyDown, keyboardTarget } = useKeyboardSeek({ currentTime, duration, onSeek, disabled });

  // During a drag (or a key burst) the played range follows the pending
  // target, not the (frozen) playback clock - the seek lands later (#5625).
  const displayTime = dragPosition ?? keyboardTarget ?? currentTime;

  const progressPercentage = useMemo(
    () => progressPercent(displayTime, duration),
    [displayTime, duration]
  );

  // Handle click to seek. The click that follows a drag release must not seek again - the
  // release already committed the drag's final position (#5625).
  const handleClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (!canSeek || consumeDragClick()) return;
      onSeek(getPositionFromEvent(event));
    },
    [canSeek, consumeDragClick, getPositionFromEvent, onSeek]
  );

  // Handle mouse move for hover preview
  const handleMouseMove = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (disabled || !containerRef.current) return;
      setHoverPosition(getPositionFromEvent(event));
    },
    [disabled, getPositionFromEvent]
  );

  return {
    containerRef,
    isHovering,
    setIsHovering,
    hoverPosition,
    isDragging,
    isFocused,
    setIsFocused,
    liveSeekTime,
    progressPercentage,
    handleClick,
    handleMouseMove,
    handleMouseDown,
    handleKeyDown,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
  };
}
