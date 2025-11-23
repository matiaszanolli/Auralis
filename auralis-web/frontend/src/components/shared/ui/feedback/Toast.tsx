import React, { useState, useEffect, createContext, useContext, useCallback, useMemo } from 'react';
import { Snackbar, Alert, AlertColor, styled, keyframes } from '@mui/material';
import { auroraOpacity, colorAuroraPrimary } from '../library/Color.styles';
import { spacingXSmall } from '../library/Spacing.styles';
import { tokens } from '@/design-system/tokens';

interface ToastMessage {
  id: string;
  message: string;
  type: AlertColor;
  duration?: number;
}

interface ToastContextValue {
  showToast: (message: string, type?: AlertColor, duration?: number) => void;
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

const slideIn = keyframes`
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
`;

const StyledAlert = styled(Alert)<{ severity: AlertColor }>(({ severity }) => {
  // Helper to add alpha to hex colors
  const hexToRgba = (hex: string, alpha: number): string => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const getBackgroundColor = () => {
    switch (severity) {
      case 'success':
        return hexToRgba(tokens.colors.accent.success, 0.15);
      case 'error':
        return hexToRgba(tokens.colors.accent.error, 0.15);
      case 'warning':
        return hexToRgba(tokens.colors.accent.warning, 0.15);
      case 'info':
        return auroraOpacity.lighter;
      default:
        return tokens.colors.bg.secondary;
    }
  };

  const getBorderColor = () => {
    switch (severity) {
      case 'success':
        return tokens.colors.accent.success;
      case 'error':
        return tokens.colors.accent.error;
      case 'warning':
        return tokens.colors.accent.warning;
      case 'info':
        return colorAuroraPrimary;
      default:
        return tokens.colors.text.disabled;
    }
  };

  return {
    background: getBackgroundColor(),
    color: tokens.colors.text.primary,
    border: `1px solid ${getBorderColor()}`,
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.19)',
    backdropFilter: 'blur(12px)',
    animation: `${slideIn} 0.3s ease-out`,
    fontSize: '14px',
    fontWeight: 500,

    '& .MuiAlert-icon': {
      color: getBorderColor(),
    },

    '& .MuiAlert-message': {
      padding: `${spacingXSmall} 0`,
    },
  };
});

interface ToastProviderProps {
  children: React.ReactNode;
  maxToasts?: number;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({
  children,
  maxToasts = 3,
}) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback((
    message: string,
    type: AlertColor = 'info',
    duration: number = 4000
  ) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    const newToast: ToastMessage = { id, message, type, duration };

    setToasts((prev) => {
      const updated = [...prev, newToast];
      // Keep only the latest maxToasts
      return updated.slice(-maxToasts);
    });
  }, [maxToasts]);

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

  const handleClose = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const value: ToastContextValue = useMemo(() => ({
    showToast,
    success,
    error,
    info,
    warning,
  }), [showToast, success, error, info, warning]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {toasts.map((toast, index) => (
        <Snackbar
          key={toast.id}
          open={true}
          autoHideDuration={toast.duration}
          onClose={() => handleClose(toast.id)}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
          sx={{
            top: `${24 + index * 70}px !important`,
            transition: 'top 0.3s ease',
          }}
        >
          <StyledAlert
            severity={toast.type}
            onClose={() => handleClose(toast.id)}
            variant="filled"
          >
            {toast.message}
          </StyledAlert>
        </Snackbar>
      ))}
    </ToastContext.Provider>
  );
};

// Standalone Toast component (if not using context)
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
      <StyledAlert severity={type} onClose={onClose} variant="filled">
        {message}
      </StyledAlert>
    </Snackbar>
  );
};

export default Toast;
