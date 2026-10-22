/**
 * Pure position / percentage / keyboard-step maths for the progress bar.
 *
 * Split out of useProgressBarInteraction.ts (#5840) so the drag state machine
 * there deals only in events and refs.
 */

const KEYBOARD_STEP_SECONDS = 1; // 1 second per arrow key

/** Played fraction of the bar in [0, 100]; 0 for an unknown or empty duration. */
export function progressPercent(displayTime: number, duration: number): number {
  if (!Number.isFinite(duration) || duration <= 0) {
    return 0;
  }
  const percentage = (displayTime / duration) * 100;
  return Math.min(Math.max(percentage, 0), 100);
}

/**
 * Seek position under a pointer. A zero-width rect (unlaid-out container,
 * jsdom) makes x/width NaN, which previously reached onSeek as a NaN
 * position — treat it as "no measurable position" and fall back.
 */
export function positionFromPointer(
  clientX: number,
  rect: Pick<DOMRect, 'left' | 'width'>,
  duration: number,
  fallback: number
): number {
  if (rect.width <= 0) return fallback;

  const x = clientX - rect.left;
  const fraction = Math.max(0, Math.min(1, x / rect.width));
  return fraction * duration;
}

/**
 * Target position for a seek key, or null when the key is not one. Each
 * keypress is a deliberate, discrete seek request (unchanged by #5625).
 */
export function keyboardSeekTarget(
  key: string,
  currentTime: number,
  duration: number
): number | null {
  switch (key) {
    case 'ArrowLeft':
    case 'ArrowDown':
      return Math.max(0, currentTime - KEYBOARD_STEP_SECONDS);
    case 'ArrowRight':
    case 'ArrowUp':
      return Math.min(duration, currentTime + KEYBOARD_STEP_SECONDS);
    case 'Home':
      return 0;
    case 'End':
      return duration;
    default:
      return null;
  }
}
