import { useCallback, useMemo } from 'react';
import { AlertColor } from '@mui/material';
import { ToastMessage } from './Toast';

interface UseToastMethodsProps {
  maxToasts: number;
  onAdd: (toast: ToastMessage) => void;
}

/**
 * useToastMethods - Provides typed methods for showing toasts (success, error, info, warning)
 *
 * Encapsulates toast helper methods with memoization for performance.
 * Used by ToastProvider to offer convenient typed methods.
 */
export const useToastMethods = ({ maxToasts, onAdd }: UseToastMethodsProps) => {
  const showToast = useCallback((
    message: string,
    type: AlertColor = 'info',
    duration: number = 4000
  ) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    const newToast: ToastMessage = { id, message, type, duration };
    onAdd(newToast);
  }, [maxToasts, onAdd]);

  const success = useCallback((message: string, duration?: number) => {
    showToast(message, 'success', duration);
  }, [showToast]);

  const error = useCallback((message: string, duration?: number) => {
    showToast(message, 'error', duration);
  }, [showToast]);

  const info = useCallback((message: string, duration?: number) => {
    showToast(message, 'info', duration);
  }, [showToast]);

  const warning = useCallback((message: string, duration?: number) => {
    showToast(message, 'warning', duration);
  }, [showToast]);

  return useMemo(() => ({
    showToast,
    success,
    error,
    info,
    warning,
  }), [showToast, success, error, info, warning]);
};
