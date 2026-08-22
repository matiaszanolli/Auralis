/**
 * useProgressBarInteraction - Mouse/touch/keyboard seek handling for ProgressBar.
 *
 * Owns drag/hover/focus state, the position-from-event math, and the global
 * mousemove/mouseup listeners used while dragging. Extracted from
 * ProgressBar.tsx to keep the component under the 300-line guideline (#4456).
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

export interface UseProgressBarInteractionArgs {
  currentTime: number;
  duration: number;
  onSeek: (position: number) => void;
  disabled: boolean;
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
  // Live position during drag — throttled to ~4Hz for ARIA announcements (fixes #2538)
  const [liveSeekTime, setLiveSeekTime] = useState<number | null>(null);
  const lastAriaAnnounceRef = useRef<number>(0);

  // Stable refs for values used in drag handlers to avoid recreating
  // callbacks on every playback tick (#3103)
  const durationRef = useRef(duration);
  durationRef.current = duration;
  const currentTimeRef = useRef(currentTime);
  currentTimeRef.current = currentTime;
  const onSeekRef = useRef(onSeek);
  onSeekRef.current = onSeek;

  // Calculate progress percentage
  const progressPercentage = useMemo(() => {
    if (!Number.isFinite(duration) || duration <= 0) {
      return 0;
    }
    const percentage = (currentTime / duration) * 100;
    return Math.min(Math.max(percentage, 0), 100);
  }, [currentTime, duration]);

  // Handle mouse position calculation (stable — reads from refs)
  const getPositionFromEvent = useCallback(
    (event: MouseEvent<HTMLDivElement> | globalThis.MouseEvent) => {
      if (!containerRef.current) return currentTimeRef.current;

      const rect = containerRef.current.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      return percentage * durationRef.current;
    },
    []
  );

  // Handle click to seek
  const handleClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
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

  // Handle drag start
  const handleMouseDown = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      setIsDragging(true);
      const position = getPositionFromEvent(event);
      onSeek(position);
    },
    [disabled, duration, getPositionFromEvent, onSeek]
  );

  // Handle drag during mouse move (stable — reads from refs)
  const handleGlobalMouseMove = useCallback(
    (event: globalThis.MouseEvent) => {
      if (!containerRef.current) return;

      const position = getPositionFromEvent(event);
      onSeekRef.current(position);

      // Throttle ARIA live region updates to ~4Hz during drag (fixes #2538)
      const now = Date.now();
      if (now - lastAriaAnnounceRef.current >= 250) {
        lastAriaAnnounceRef.current = now;
        setLiveSeekTime(position);
      }
    },
    [getPositionFromEvent]
  );

  // Handle drag end
  const handleGlobalMouseUp = useCallback(() => {
    setIsDragging(false);
    setLiveSeekTime(null);
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      const STEP = 1; // 1 second per arrow key
      let newPosition: number | null = null;

      switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowDown':
          event.preventDefault();
          newPosition = Math.max(0, currentTime - STEP);
          break;
        case 'ArrowRight':
        case 'ArrowUp':
          event.preventDefault();
          newPosition = Math.min(duration, currentTime + STEP);
          break;
        case 'Home':
          event.preventDefault();
          newPosition = 0;
          break;
        case 'End':
          event.preventDefault();
          newPosition = duration;
          break;
        default:
          return;
      }

      if (newPosition !== null) {
        onSeek(newPosition);
      }
    },
    [disabled, duration, currentTime, onSeek]
  );

  // Handle touch start
  const handleTouchStart = useCallback(
    (event: TouchEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      setIsDragging(true);
      const touch = event.touches[0];
      if (!touch || !containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = touch.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      const position = percentage * duration;
      onSeek(position);
    },
    [disabled, duration, onSeek]
  );

  // Handle touch move
  const handleTouchMove = useCallback(
    (event: TouchEvent<HTMLDivElement>) => {
      if (!isDragging || !containerRef.current) {
        return;
      }

      event.preventDefault();
      const touch = event.touches[0];
      if (!touch) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = touch.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      const position = percentage * duration;
      onSeek(position);

      // Throttle ARIA live region updates to ~4Hz during touch drag (fixes #2538)
      const now = Date.now();
      if (now - lastAriaAnnounceRef.current >= 250) {
        lastAriaAnnounceRef.current = now;
        setLiveSeekTime(position);
      }
    },
    [isDragging, duration, onSeek]
  );

  // Handle touch end
  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
    setLiveSeekTime(null);
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
