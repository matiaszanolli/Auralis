/**
 * useWebSocketErrors Hook
 *
 * Subscribes to `error` WebSocket messages (rate-limit rejections,
 * schema validation failures) and surfaces them via toast notifications
 * so security events are visible to the user (#2874).
 *
 * Mount once at the app level inside both WebSocketProvider and ToastProvider.
 */

import { useWebSocketSubscription } from './useWebSocketSubscription';
import { useToast } from '@/components/shared/Toast';
import type { WebSocketMessage, WebSocketErrorMessage } from '@/types/websocket';

export function useWebSocketErrors(): void {
  const { warning } = useToast();

  useWebSocketSubscription(['error'], (message: WebSocketMessage) => {
    const err = message as unknown as WebSocketErrorMessage;
    warning(err.message || 'An error occurred');
  });
}
