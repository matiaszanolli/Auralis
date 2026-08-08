import { useId } from 'react';
import Box from '@mui/material/Box';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
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
        zIndex: tokens.zIndex.toast,
      }}
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          background: themeVars.surfacePrimary,
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
            color: isDangerous ? tokens.colors.semantic.error : themeVars.textPrimary,
          }}
        >
          {title}
        </h3>

        <p
          style={{
            margin: `0 0 ${tokens.spacing.lg} 0`,
            fontSize: tokens.typography.fontSize.base,
            color: themeVars.textSecondary,
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
          <Box
            component="button"
            onClick={onCancel}
            disabled={disabled}
            sx={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: themeVars.surfaceSecondary,
              border: `1px solid ${tokens.colors.border.light}`,
              borderRadius: tokens.borderRadius.sm,
              color: themeVars.textPrimary,
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.medium,
              transition: tokens.transitions.hover_out,
              '&:hover': {
                background: themeVars.surfaceRaised,
              },
            }}
          >
            {cancelText}
          </Box>
          <Box
            component="button"
            onClick={onConfirm}
            disabled={disabled}
            sx={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: isDangerous ? tokens.colors.semantic.error : tokens.colors.accent.primary,
              border: 'none',
              borderRadius: tokens.borderRadius.sm,
              color: themeVars.onAccent,
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.semibold,
              opacity: disabled ? 0.6 : 0.9,
              transition: tokens.transitions.hover_out,
              '&:hover:not(:disabled)': {
                opacity: 1,
              },
            }}
          >
            {confirmText}
          </Box>
        </div>
      </div>
    </div>
  );
}
