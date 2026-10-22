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
 * click is taught to swallow.
 */

import {
  KeyboardEvent,
  MouseEvent,
  TouchEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { keyboardSeekTarget, positionFromPointer, progressPercent } from './progressBarMath';

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
  const [isDragging, setIsDragging] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  // Where the drag currently points — every move updates it so the played
  // range follows the pointer, and release commits it to onSeek once (#5625).
  const [dragPosition, setDragPosition] = useState<number | null>(null);
  // Live position during drag — throttled to ~4Hz for ARIA announcements (fixes #2538)
  const [liveSeekTime, setLiveSeekTime] = useState<number | null>(null);
  const lastAriaAnnounceRef = useRef<number>(0);
  // Mirrors of the drag state for the global (ref-stable) listeners.
  const dragPositionRef = useRef<number | null>(null);
  // True once a gesture has moved (or committed), so the synthetic click that
  // follows release cannot seek a second time. Consumed by handleClick.
  const didDragRef = useRef(false);

  // Stable refs for values used in drag handlers to avoid recreating
  // callbacks on every playback tick (#3103)
  const durationRef = useRef(duration);
  durationRef.current = duration;
  const currentTimeRef = useRef(currentTime);
  currentTimeRef.current = currentTime;
  const onSeekRef = useRef(onSeek);
  onSeekRef.current = onSeek;

  // During a drag the played range follows the pointer, not the (frozen)
  // playback clock — the seek only lands after release (#5625).
  const displayTime = dragPosition ?? currentTime;

  const progressPercentage = useMemo(
    () => progressPercent(displayTime, duration),
    [displayTime, duration]
  );

  // Handle mouse/touch position calculation (stable — reads from refs)
  const getPositionFromEvent = useCallback((event: PointLike) => {
    if (!containerRef.current) return currentTimeRef.current;

    return positionFromPointer(
      event.clientX,
      containerRef.current.getBoundingClientRect(),
      durationRef.current,
      currentTimeRef.current
    );
  }, []);

  // Handle click to seek
  const handleClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      // The click that follows a drag release must not seek again — the
      // release already committed the drag's final position (#5625).
      if (didDragRef.current) {
        didDragRef.current = false;
        return;
      }

      const position = getPositionFromEvent(event);
      onSeek(position);
    },
    [disabled, duration, getPositionFromEvent, onSeek]
  );

  // Handle mouse move for hover preview
  const handleMouseMove = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (disabled || !containerRef.current) {
        return;
      }

      const position = getPositionFromEvent(event);
      setHoverPosition(position);
    },
    [disabled, getPositionFromEvent]
  );

  // Handle drag start. Records the gesture but does NOT seek: mousedown used
  // to seek, then every mousemove, then the trailing click (#5625).
  const handleMouseDown = useCallback(() => {
    if (disabled || !Number.isFinite(duration) || duration <= 0) {
      return;
    }

    setIsDragging(true);
    didDragRef.current = false;
    dragPositionRef.current = null;
    setDragPosition(null);
  }, [disabled, duration]);

  // Handle drag during mouse move (stable — reads from refs). Visual-only:
  // the seek commits once, on release (#5625).
  const handleGlobalMouseMove = useCallback(
    (event: globalThis.MouseEvent) => {
      if (!containerRef.current) return;

      const position = getPositionFromEvent(event);
      didDragRef.current = true;
      dragPositionRef.current = position;
      setDragPosition(position);

      // Throttle ARIA live region updates to ~4Hz during drag (fixes #2538)
      const now = Date.now();
      if (now - lastAriaAnnounceRef.current >= 250) {
        lastAriaAnnounceRef.current = now;
        setLiveSeekTime(position);
      }
    },
    [getPositionFromEvent]
  );

  // Handle drag end: commit exactly one seek, at the last dragged position.
  const handleGlobalMouseUp = useCallback(() => {
    setIsDragging(false);
    setLiveSeekTime(null);
    const pending = dragPositionRef.current;
    dragPositionRef.current = null;
    setDragPosition(null);
    if (pending !== null) {
      didDragRef.current = true; // swallow the trailing click
      onSeekRef.current(pending);
    }
    // No move since mousedown: nothing to commit — the trailing click seeks.
  }, []);

  // Handle keyboard navigation (unchanged by #5625: each keypress is a
  // deliberate, discrete seek request)
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      const newPosition = keyboardSeekTarget(event.key, currentTime, duration);
      if (newPosition === null) return;

      event.preventDefault();
      onSeek(newPosition);
    },
    [disabled, duration, currentTime, onSeek]
  );

  // Handle touch start. Like mousedown, it must not seek (#5625) — but the
  // press point becomes the pending commit, because some browsers never fire
  // the synthetic click a tap would rely on. A drag overwrites it per move.
  const handleTouchStart = useCallback(
    (event: TouchEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      setIsDragging(true);
      didDragRef.current = false;
      const touch = event.touches[0];
      if (!touch || !containerRef.current) return;

      const position = getPositionFromEvent(touch);
      dragPositionRef.current = position;
      setDragPosition(position);
    },
    [disabled, duration, getPositionFromEvent]
  );

  // Handle touch move — visual-only, like the mouse path (#5625).
  const handleTouchMove = useCallback(
    (event: TouchEvent<HTMLDivElement>) => {
      if (!isDragging || !containerRef.current) {
        return;
      }

      event.preventDefault();
      const touch = event.touches[0];
      if (!touch) return;

      const position = getPositionFromEvent(touch);
      didDragRef.current = true;
      dragPositionRef.current = position;
      setDragPosition(position);

      // Throttle ARIA live region updates to ~4Hz during touch drag (fixes #2538)
      const now = Date.now();
      if (now - lastAriaAnnounceRef.current >= 250) {
        lastAriaAnnounceRef.current = now;
        setLiveSeekTime(position);
      }
    },
    [isDragging, getPositionFromEvent]
  );

  // Handle touch end: same single-commit rule as the mouse path.
  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
    setLiveSeekTime(null);
    const pending = dragPositionRef.current;
    dragPositionRef.current = null;
    setDragPosition(null);
    if (pending !== null) {
      didDragRef.current = true; // swallow the synthetic click after a drag
      onSeekRef.current(pending);
    }
    // Tap without move: pending is set by touchstart, so this commits the
    // tap position — and didDragRef swallows the synthetic click that some
    // browsers fire afterwards.
  }, []);

  // Set up global event listeners during drag
  useEffect(() => {
    if (!isDragging) {
      return;
    }

    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', handleGlobalMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleGlobalMouseMove);
      document.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [isDragging, handleGlobalMouseMove, handleGlobalMouseUp]); // handlers are stable (empty/minimal deps)

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
