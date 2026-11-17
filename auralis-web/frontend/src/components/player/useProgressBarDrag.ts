/**
 * useProgressBarDrag - Mouse and touch drag gestures for ProgressBar.
 *
 * Drag = one seek (#5625). A gesture only updates the visual position (and the throttled ARIA
 * announcements); exactly one seek commits on release, at the last position the pointer held.
 * mousedown/touchstart never seek, and a click that follows a committed drag is swallowed via
 * `consumeDragClick`. Split out of useProgressBarInteraction (#6275).
 */

import { TouchEvent, useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';

/** Anything with a clientX - mouse events and Touch objects both qualify. */
interface PointLike {
  clientX: number;
}

interface UseProgressBarDragArgs {
  containerRef: RefObject<HTMLDivElement | null>;
  getPositionFromEvent: (event: PointLike) => number;
  /** Latest onSeek, read at release so the global listeners stay stable. */
  onSeekRef: RefObject<(position: number) => void>;
  /** False when the bar is disabled or has no usable duration: gestures are ignored. */
  canSeek: boolean;
}

/** ARIA announcements while dragging are throttled to ~4Hz (#2538). */
const ARIA_ANNOUNCE_INTERVAL_MS = 250;

export function useProgressBarDrag({
  containerRef,
  getPositionFromEvent,
  onSeekRef,
  canSeek,
}: UseProgressBarDragArgs) {
  const [isDragging, setIsDragging] = useState(false);
  // Where the drag currently points: the played range follows it, and release commits it once.
  const [dragPosition, setDragPosition] = useState<number | null>(null);
  const [liveSeekTime, setLiveSeekTime] = useState<number | null>(null);
  const lastAriaAnnounceRef = useRef<number>(0);
  // Mirror of dragPosition for the global (ref-stable) listeners.
  const dragPositionRef = useRef<number | null>(null);
  // True once a gesture has moved (or committed), so the synthetic click that follows release
  // cannot seek a second time. Consumed by consumeDragClick.
  const didDragRef = useRef(false);

  const setPending = useCallback((position: number | null) => {
    dragPositionRef.current = position;
    setDragPosition(position);
  }, []);

  /** A pointer move: visual-only, plus the throttled live announcement. */
  const recordMove = useCallback(
    (position: number) => {
      didDragRef.current = true;
      setPending(position);
      const now = Date.now();
      if (now - lastAriaAnnounceRef.current >= ARIA_ANNOUNCE_INTERVAL_MS) {
        lastAriaAnnounceRef.current = now;
        setLiveSeekTime(position);
      }
    },
    [setPending]
  );

  /**
   * Release (mouseup or touchend): commit exactly one seek at the last held position. A mouse
   * press with no move has nothing pending - the trailing click seeks. A touch press records its
   * point as pending, because some browsers never fire the click a tap would rely on.
   */
  const commit = useCallback(() => {
    setIsDragging(false);
    setLiveSeekTime(null);
    const pending = dragPositionRef.current;
    setPending(null);
    if (pending !== null) {
      didDragRef.current = true; // swallow the click that follows
      onSeekRef.current?.(pending);
    }
  }, [setPending, onSeekRef]);

  const handleMouseDown = useCallback(() => {
    if (!canSeek) return;
    setIsDragging(true);
    didDragRef.current = false;
    setPending(null);
  }, [canSeek, setPending]);

  const handleGlobalMouseMove = useCallback(
    (event: globalThis.MouseEvent) => {
      if (!containerRef.current) return;
      recordMove(getPositionFromEvent(event));
    },
    [containerRef, getPositionFromEvent, recordMove]
  );

  const handleTouchStart = useCallback(
    (event: TouchEvent<HTMLDivElement>) => {
      if (!canSeek) return;
      setIsDragging(true);
      didDragRef.current = false;
      const touch = event.touches[0];
      if (!touch || !containerRef.current) return;
      setPending(getPositionFromEvent(touch));
    },
    [canSeek, containerRef, getPositionFromEvent, setPending]
  );

  const handleTouchMove = useCallback(
    (event: TouchEvent<HTMLDivElement>) => {
      if (!isDragging || !containerRef.current) return;
      event.preventDefault();
      const touch = event.touches[0];
      if (!touch) return;
      recordMove(getPositionFromEvent(touch));
    },
    [isDragging, containerRef, getPositionFromEvent, recordMove]
  );

  // Global listeners exist only while a mouse drag is in progress.
  useEffect(() => {
    if (!isDragging) return;
    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', commit);
    return () => {
      document.removeEventListener('mousemove', handleGlobalMouseMove);
      document.removeEventListener('mouseup', commit);
    };
  }, [isDragging, handleGlobalMouseMove, commit]);

  /** True (once) when the click being handled is the tail of a drag that already committed. */
  const consumeDragClick = useCallback(() => {
    if (!didDragRef.current) return false;
    didDragRef.current = false;
    return true;
  }, []);

  return {
    isDragging,
    dragPosition,
    liveSeekTime,
    handleMouseDown,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd: commit,
    consumeDragClick,
  };
}
