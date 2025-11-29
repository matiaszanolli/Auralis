import React from 'react';
import { tokens } from '@/design-system';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeMap = {
  sm: '400px',
  md: '600px',
  lg: '800px',
};

/**
 * Modal component for displaying dialog content.
 */
export const Modal = React.forwardRef<
  HTMLDivElement,
  ModalProps
>(({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  className = '',
}, ref) => {
  React.useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const backdropStyles: React.CSSProperties = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: tokens.colors.bg.overlay,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: tokens.zIndex.modalBackdrop,
  };

  const modalStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.lg,
    boxShadow: tokens.shadows['2xl'],
    width: sizeMap[size],
    maxHeight: '90vh',
    overflow: 'hidden',
    zIndex: tokens.zIndex.modal,
  };

  const headerStyles: React.CSSProperties = {
    padding: tokens.spacing.lg,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  };

  const contentStyles: React.CSSProperties = {
    padding: tokens.spacing.lg,
    overflow: 'auto',
    flex: 1,
  };

  const footerStyles: React.CSSProperties = {
    padding: tokens.spacing.lg,
    borderTop: `1px solid ${tokens.colors.border.light}`,
    display: 'flex',
    gap: tokens.spacing.md,
    justifyContent: 'flex-end',
  };

  const closeButtonStyles: React.CSSProperties = {
    background: 'none',
    border: 'none',
    color: tokens.colors.text.secondary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    padding: 0,
  };

  return (
    <div style={backdropStyles} onClick={onClose}>
      <div
        ref={ref}
        style={modalStyles}
        className={className}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div style={headerStyles}>
            <h2 style={{ margin: 0, fontSize: tokens.typography.fontSize['2xl'] }}>
              {title}
            </h2>
            <button
              style={closeButtonStyles}
              onClick={onClose}
              aria-label="Close modal"
            >
              ✕
            </button>
          </div>
        )}
        <div style={contentStyles}>{children}</div>
        {footer && <div style={footerStyles}>{footer}</div>}
      </div>
    </div>
  );
});

Modal.displayName = 'Modal';
