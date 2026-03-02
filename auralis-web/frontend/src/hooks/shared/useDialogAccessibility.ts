/**
 * useDialogAccessibility
 *
 * Provides focus trapping, Escape key dismissal, and focus restoration
 * for custom modal dialogs. Attach the returned ref to the dialog
 * content container (the element with role="dialog").
 */

import { useEffect, useRef, useCallback } from 'react';
import { focusManager } from '@/a11y/focusManagement';

export function useDialogAccessibility(onClose: () => void) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // Stable ref to onClose so the effect doesn't re-run on every render
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const stableOnClose = useCallback(() => onCloseRef.current(), []);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;

    focusManager.saveFocus();
    const removeTrap = focusManager.createFocusTrap(el, stableOnClose);

    return () => {
      removeTrap();
      focusManager.restoreFocus();
    };
  }, [stableOnClose]);

  return dialogRef;
}
