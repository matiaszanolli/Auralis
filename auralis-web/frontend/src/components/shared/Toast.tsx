import React, { useState, useEffect, createContext, useContext } from 'react';
import { Snackbar, Alert, AlertColor, styled, keyframes } from '@mui/material';
import { colors, gradients } from '../../theme/auralisTheme';

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
  const getBackgroundColor = () => {
    switch (severity) {
      case 'success':
        return 'rgba(0, 212, 170, 0.15)';
      case 'error':
        return 'rgba(255, 71, 87, 0.15)';
      case 'warning':
        return 'rgba(255, 165, 2, 0.15)';
      case 'info':
        return 'rgba(102, 126, 234, 0.15)';
      default:
        return colors.background.surface;
    }
  };

  const getBorderColor = () => {
    switch (severity) {
      case 'success':
        return colors.accent.success;
      case 'error':
        return colors.accent.error;
      case 'warning':
        return colors.accent.warning;
      case 'info':
        return '#667eea';
      default:
        return colors.text.disabled;
    }
  };

  return {
    background: getBackgroundColor(),
    color: colors.text.primary,
    border: `1px solid ${getBorderColor()}`,
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
    backdropFilter: 'blur(12px)',
    animation: `${slideIn} 0.3s ease-out`,
    fontSize: '14px',
    fontWeight: 500,

    '& .MuiAlert-icon': {
      color: getBorderColor(),
    },

    '& .MuiAlert-message': {
      padding: '6px 0',
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

  const showToast = (
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
  };

  const success = (message: string, duration?: number) => {
    showToast(message, 'success', duration);
  };

  const error = (message: string, duration?: number) => {
    showToast(message, 'error', duration);
  };

  const info = (message: string, duration?: number) => {
    showToast(message, 'info', duration);
  };

  const warning = (message: string, duration?: number) => {
    showToast(message, 'warning', duration);
  };

  const handleClose = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  const value: ToastContextValue = {
    showToast,
    success,
    error,
    info,
    warning,
  };

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
