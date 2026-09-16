import { createPortal } from 'react-dom';
import { useDialogAccessibility } from '@/hooks/shared/useDialogAccessibility';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

interface ClearQueueDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export const ClearQueueDialog = ({ onConfirm, onCancel }: ClearQueueDialogProps) => {
  // Shared focus trap (#3007, #5394): Tab/Shift+Tab wrap, Escape cancels,
  // focus moves to the first button (Cancel) and returns to the trigger on
  // unmount, the same hook ConfirmationDialog and QueueSearchPanel use. The
  // parent mounts this only while open, so the default isActive applies.
  const dialogRef = useDialogAccessibility(onCancel);

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
