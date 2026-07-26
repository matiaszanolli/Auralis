import { KeyboardEvent, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

interface ClearQueueDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export const ClearQueueDialog = ({ onConfirm, onCancel }: ClearQueueDialogProps) => {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus trap: keep Tab/Shift+Tab within the dialog (#3007)
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') { onCancel(); return; }
    if (e.key !== 'Tab') return;

    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable || focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }, [onCancel]);

  // Restore focus on unmount
  const triggerRef = useRef(document.activeElement as HTMLElement | null);
  useEffect(() => {
    return () => { triggerRef.current?.focus(); };
  }, []);

  // #3573: Render via portal so position:fixed is anchored to the viewport.
  // Without this, the Player's `backdrop-filter` creates a new containing
  // block for fixed descendants, clipping the overlay to the queue panel.
  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: themeVars.backdrop,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: tokens.zIndex.dropdown,
      }}
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="clear-queue-dialog-title"
        onKeyDown={handleKeyDown}
        style={{
          background: themeVars.surfaceRaised,
          borderRadius: tokens.borderRadius.md,
          border: `1px solid ${themeVars.borderDefault}`,
          padding: tokens.spacing.lg,
          maxWidth: '360px',
          boxShadow: themeVars.shadowOverlay,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="clear-queue-dialog-title"
          style={{
            margin: `0 0 ${tokens.spacing.lg} 0`,
            color: themeVars.textPrimary,
            fontSize: tokens.typography.fontSize.base,
            fontWeight: tokens.typography.fontWeight.semibold,
          }}
        >
          Clear the entire queue?
        </h2>
        <div style={{ display: 'flex', gap: tokens.spacing.sm, justifyContent: 'flex-end' }}>
          <button
            autoFocus
            onClick={onCancel}
            style={{
              padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
              background: 'transparent',
              border: `1px solid ${themeVars.borderDefault}`,
              borderRadius: tokens.borderRadius.sm,
              color: themeVars.textSecondary,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
              background: themeVars.error,
              border: 'none',
              borderRadius: tokens.borderRadius.sm,
              color: themeVars.onError,
              cursor: 'pointer',
              fontWeight: tokens.typography.fontWeight.semibold,
            }}
          >
            Clear
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
