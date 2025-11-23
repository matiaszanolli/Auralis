import React, { useCallback } from 'react';
import { Snackbar } from '@mui/material';
import { ToastMessage } from './Toast';
import { StyledAlert } from './Toast.styles';

interface ToastItemProps {
  toast: ToastMessage;
  index: number;
  onClose: (id: string) => void;
}

/**
 * ToastItem - Individual toast notification element
 *
 * Displays a single Snackbar with StyledAlert positioned vertically
 * in stack (index determines position offset).
 *
 * @example
 * <ToastItem
 *   toast={toastMessage}
 *   index={0}
 *   onClose={handleClose}
 * />
 */
export const ToastItem: React.FC<ToastItemProps> = ({ toast, index, onClose }) => {
  const handleClose = useCallback(() => {
    onClose(toast.id);
  }, [toast.id, onClose]);

  return (
    <Snackbar
      key={toast.id}
      open={true}
      autoHideDuration={toast.duration}
      onClose={handleClose}
      anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      sx={{
        top: `${24 + index * 70}px !important`,
        transition: 'top 0.3s ease',
      }}
    >
      <StyledAlert
        severity={toast.type}
        onClose={handleClose}
        variant="filled"
      >
        {toast.message}
      </StyledAlert>
    </Snackbar>
  );
};

export default ToastItem;
