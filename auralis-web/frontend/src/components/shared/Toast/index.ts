/**
 * Toast Module
 *
 * Toast notification system with context provider, typed methods, and animations.
 * Supports multiple stacked toasts with auto-dismiss.
 */

export { Toast, useToast, ToastProvider } from './Toast';
export type { ToastMessage, ToastContextValue } from './Toast';
export { ToastItem } from './ToastItem';
export { useToastMethods } from './useToastMethods';
export { StyledAlert, slideIn } from './Toast.styles';
export { getToastBackgroundColor, getToastBorderColor } from './toastColors';
