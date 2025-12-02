/**
 * Modal Primitive Component
 *
 * Modal dialog for important actions and information.
 *
 * Usage:
 *   <Modal open={open} onClose={handleClose} title="Confirm">
 *     <p>Are you sure?</p>
 *   </Modal>
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiDialog, { DialogProps as MuiDialogProps } from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import IconButton from './IconButton';
import CloseIcon from '@mui/icons-material/Close';
import { tokens } from '../tokens';

export interface ModalProps extends Omit<MuiDialogProps, 'title'> {
  /**
   * Modal title
   */
  title?: string;

  /**
   * Size
   */
  size?: 'sm' | 'md' | 'lg' | 'xl';

  /**
   * Footer actions
   */
  actions?: React.ReactNode;

  /**
   * Show close button
   */
  showClose?: boolean;

  /**
   * On close callback
   */
  onClose?: () => void;
}

const StyledDialog = styled(MuiDialog, {
  shouldForwardProp: (prop) => prop !== 'size',
})<{ size?: 'sm' | 'md' | 'lg' | 'xl' }>(({ size = 'md' }) => {
  const sizeStyles = {
    sm: { maxWidth: '400px' },
    md: { maxWidth: '600px' },
    lg: { maxWidth: '800px' },
    xl: { maxWidth: '1200px' },
  };

  return {
    '& .MuiDialog-paper': {
      ...sizeStyles[size as keyof typeof sizeStyles],
      width: '100%',
      background: tokens.colors.bg.level4,  // Surface elevation (modals)
      borderRadius: tokens.borderRadius.xl,
      border: `1px solid ${tokens.colors.border.light}`,
      boxShadow: tokens.shadows['2xl'],
      backdropFilter: 'blur(20px)',
    },
    '& .MuiBackdrop-root': {
      background: 'rgba(0, 0, 0, 0.60)',  // Standard modal backdrop
      backdropFilter: 'blur(4px)',
    },
  };
});

const StyledDialogTitle = styled(DialogTitle)({
  padding: tokens.spacing.lg,
  borderBottom: `1px solid ${tokens.colors.border.light}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  color: tokens.colors.text.primary,
  fontSize: tokens.typography.fontSize.xl,
  fontWeight: tokens.typography.fontWeight.semibold,
});

const StyledDialogContent = styled(DialogContent)({
  padding: tokens.spacing.lg,
  color: tokens.colors.text.secondary,
});

const StyledDialogActions = styled(DialogActions)({
  padding: tokens.spacing.lg,
  borderTop: `1px solid ${tokens.colors.border.light}`,
  gap: tokens.spacing.sm,
});

export const Modal: React.FC<ModalProps> = ({
  children,
  title,
  size = 'md',
  actions,
  showClose = true,
  onClose,
  ...props
}) => {
  return (
    <StyledDialog size={size} onClose={onClose} {...props}>
      {title && (
        <StyledDialogTitle>
          {title}
          {showClose && onClose && (
            <IconButton
              onClick={onClose}
              size="sm"
              variant="ghost"
              sx={{ marginLeft: 'auto' }}
            >
              <CloseIcon />
            </IconButton>
          )}
        </StyledDialogTitle>
      )}
      <StyledDialogContent>{children}</StyledDialogContent>
      {actions && <StyledDialogActions>{actions}</StyledDialogActions>}
    </StyledDialog>
  );
};

export default Modal;
