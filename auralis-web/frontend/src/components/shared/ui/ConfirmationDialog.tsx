import { useId } from 'react';
import { tokens } from '@/design-system';
import { useDialogAccessibility } from '@/hooks/shared/useDialogAccessibility';

interface ConfirmationDialogProps {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDangerous?: boolean;
  disabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmationDialog({
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDangerous = false,
  disabled = false,
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  const dialogRef = useDialogAccessibility(onCancel);
  const titleId = useId();

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: tokens.colors.opacityScale.dark.intense,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1300,
      }}
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          background: tokens.colors.bg.secondary,
          borderRadius: tokens.borderRadius.sm,
          border: `1px solid ${isDangerous ? tokens.colors.semantic.error : tokens.colors.border.medium}`,
          padding: tokens.spacing.lg,
          maxWidth: '420px',
          boxShadow: tokens.shadows.xl,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3
          id={titleId}
          style={{
            margin: `0 0 ${tokens.spacing.md} 0`,
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: isDangerous ? tokens.colors.semantic.error : tokens.colors.text.primary,
          }}
        >
          {title}
        </h3>

        <p
          style={{
            margin: `0 0 ${tokens.spacing.lg} 0`,
            fontSize: tokens.typography.fontSize.base,
            color: tokens.colors.text.secondary,
            lineHeight: tokens.typography.lineHeight.normal,
          }}
        >
          {message}
        </p>

        <div
          style={{
            display: 'flex',
            gap: tokens.spacing.md,
            justifyContent: 'flex-end',
          }}
        >
          <button
            onClick={onCancel}
            disabled={disabled}
            style={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: tokens.colors.bg.tertiary,
              border: `1px solid ${tokens.colors.border.light}`,
              borderRadius: tokens.borderRadius.sm,
              color: tokens.colors.text.primary,
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.medium,
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = tokens.colors.bg.elevated;
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = tokens.colors.bg.tertiary;
            }}
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={disabled}
            style={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: isDangerous ? tokens.colors.semantic.error : tokens.colors.accent.primary,
              border: 'none',
              borderRadius: tokens.borderRadius.sm,
              color: tokens.colors.text.primary,
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.semibold,
              opacity: disabled ? 0.6 : 0.9,
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.opacity = '1';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.opacity = '0.9';
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
