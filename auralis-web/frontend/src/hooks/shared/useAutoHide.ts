/**
 * useAutoHide
 * ~~~~~~~~~~~
 *
 * Calls `onHide` after `delayMs` whenever `active` is true. The timer is cleared
 * on deactivation or unmount, so `onHide` never fires after unmount.
 *
 * Extracted from ConnectionStatusIndicator (#4186).
 */

import { useEffect, useRef } from 'react';

export function useAutoHide(active: boolean, onHide: () => void, delayMs = 2000): void {
  // Keep the latest onHide without re-arming the timer when only the callback
  // identity changes.
  const onHideRef = useRef(onHide);
  onHideRef.current = onHide;

  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => onHideRef.current(), delayMs);
    return () => clearTimeout(timer);
  }, [active, delayMs]);
}
