import React, { useState, createContext, useContext, useCallback } from 'react';
import { AlertColor, Snackbar } from '@mui/material';
import { StyledAlert } from './Toast.styles';
import { ToastItem } from './ToastItem';
import { useToastMethods } from './useToastMethods';

/**
 * Toast - Toast notification system with context provider
 *
 * Provides a composable toast system with:
 * - Context-based API (useToast hook)
 * - Typed methods (success, error, info, warning)
 * - Multiple toast stacking with auto-dismiss
 * - Slide-in animations with blurred backdrop
 * - Configurable max visible toasts
 *
 * Usage:
 * ```tsx
 * // Wrap app with provider
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 *
 * // Use in components
 * const { success, error } = useToast();
 * success('Operation completed');
 * error('Something went wrong');
 * ```
 */

export interface ToastMessage {
  id: string;
  message: string;
  type: AlertColor;
  duration?: number;
}

export interface ToastContextValue {
  showToast: (message: string, type?: AlertColor, duration?: number) => void;
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

/**
 * useToast - Hook to access toast methods from context
 *
 * Must be used within a ToastProvider
 *
 * @example
 * const { success, error } = useToast();
 * success('Done!');
 */
export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

interface ToastProviderProps {
  children: React.ReactNode;
  maxToasts?: number;
}

/**
 * ToastProvider - Context provider for toast notifications
 *
 * Manages toast state and provides context for useToast hook.
 * Automatically limits visible toasts and handles dismissal.
 *
 * @example
 * <ToastProvider maxToasts={3}>
 *   <App />
 * </ToastProvider>
 */
export const ToastProvider: React.FC<ToastProviderProps> = ({
  children,
  maxToasts = 3,
}) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const handleAddToast = useCallback((newToast: ToastMessage) => {
    setToasts((prev) => {
      const updated = [...prev, newToast];
      // Keep only the latest maxToasts
      return updated.slice(-maxToasts);
    });
  }, [maxToasts]);

  const toastMethods = useToastMethods({
    maxToasts,
    onAdd: handleAddToast,
  });

  const handleClose = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={toastMethods}>
      {children}
      {toasts.map((toast, index) => (
        <ToastItem
          key={toast.id}
          toast={toast}
          index={index}
          onClose={handleClose}
        />
      ))}
    </ToastContext.Provider>
  );
};

/**
 * Toast - Standalone toast component (without context)
 *
 * For use cases where you need simple toast without context provider.
 * Controlled via open prop.
 *
 * @example
 * const [open, setOpen] = useState(false);
 * <Toast
 *   open={open}
 *   message="Notification"
 *   type="success"
 *   onClose={() => setOpen(false)}
 * />
 */
interface ToastProps {
  open: boolean;
  message: string;
  type?: AlertColor;
  onClose: () => void;
  duration?: number;
}

export const Toast: React.FC<ToastProps> = ({
  open,
  message,
  type = 'info',
  onClose,
  duration = 4000,
}) => {
  return (
    <Snackbar
      open={open}
      autoHideDuration={duration}
      onClose={onClose}
      anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
    >
      <StyledAlert
        severity={type}
        onClose={onClose}
        variant={type}
      >
        {message}
      </StyledAlert>
    </Snackbar>
  );
};

export default Toast;
