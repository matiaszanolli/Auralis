import React from 'react';
import { tokens } from '@/design-system';

interface ClearQueueDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export const ClearQueueDialog = ({ onConfirm, onCancel }: ClearQueueDialogProps) => {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: tokens.colors.opacityScale.dark.intense,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: tokens.zIndex.dropdown,
      }}
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="clear-queue-dialog-title"
        onKeyDown={(e) => { if (e.key === 'Escape') onCancel(); }}
        style={{
          background: tokens.colors.bg.secondary,
          borderRadius: tokens.borderRadius.md,
          border: `1px solid ${tokens.colors.border.medium}`,
          padding: tokens.spacing.lg,
          maxWidth: '360px',
          boxShadow: `0 10px 40px ${tokens.colors.opacityScale.dark.strong}`,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="clear-queue-dialog-title"
          style={{
            margin: `0 0 ${tokens.spacing.lg} 0`,
            color: tokens.colors.text.primary,
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
              border: `1px solid ${tokens.colors.border.medium}`,
              borderRadius: tokens.borderRadius.sm,
              color: tokens.colors.text.secondary,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
              background: tokens.colors.semantic.error,
              border: 'none',
              borderRadius: tokens.borderRadius.sm,
              color: tokens.colors.text.primaryFull,
              cursor: 'pointer',
              fontWeight: tokens.typography.fontWeight.semibold,
            }}
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
};
