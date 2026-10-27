/**
 * useWebSocketErrors Hook
 *
 * Subscribes to `error` WebSocket messages (rate-limit rejections,
 * schema validation failures) and surfaces them via toast notifications
 * so security events are visible to the user (#2874).
 *
 * Mount once at the app level inside both WebSocketProvider and ToastProvider.
 */

import { useWebSocketMessages } from './useWebSocketMessages';
import { useToast } from '@/components/shared/Toast';

export function useWebSocketErrors(): void {
  const { warning } = useToast();

  // `message` is narrowed to WebSocketErrorMessage by the subscribed type (#5636).
  useWebSocketMessages(['error'], (message) => {
    warning(message.message || 'An error occurred');
  });
}
