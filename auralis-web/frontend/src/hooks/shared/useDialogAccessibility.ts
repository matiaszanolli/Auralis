/**
 * useDialogAccessibility
 *
 * Provides focus trapping, Escape key dismissal, and focus restoration
 * for custom modal dialogs. Attach the returned ref to the dialog
 * content container (the element with role="dialog").
 *
 * @param onClose  Called on Escape (the trap forwards it).
 * @param isActive Whether the dialog is currently shown. Defaults to `true`
 *   for the common pattern where the parent conditionally MOUNTS the dialog
 *   (so it only exists while open). Pass an explicit flag when the component
 *   stays mounted and toggles via an early `return null` (e.g. QueueSearchPanel,
 *   #4148): including it in the effect deps re-creates the trap when the dialog
 *   opens and tears it down (restoring focus) when it closes.
 */

import { useEffect, useRef, useCallback } from 'react';
import { focusManager } from '@/a11y/focusManagement';

export function useDialogAccessibility(onClose: () => void, isActive: boolean = true) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // Stable ref to onClose so the effect doesn't re-run on every render
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const stableOnClose = useCallback(() => onCloseRef.current(), []);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el || !isActive) return;

    focusManager.saveFocus();
    const removeTrap = focusManager.createFocusTrap(el, stableOnClose);

    return () => {
      removeTrap();
      focusManager.restoreFocus();
    };
  }, [stableOnClose, isActive]);

  return dialogRef;
}
