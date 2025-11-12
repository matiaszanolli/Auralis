/**
 * useWebSocket Hook (DEPRECATED - Phase 4c)
 *
 * ⚠️ DEPRECATED: Use `useWebSocketContext` from '../contexts/WebSocketContext' instead
 *
 * This hook is maintained for backward compatibility only.
 * Phase 4c optimization integrated WebSocketContext with Phase 3c error handling utilities
 * (WebSocketManager) for robust reconnection and error recovery.
 *
 * Migration example:
 * ```ts
 * // OLD:
 * const { connected, lastMessage } = useWebSocket('ws://localhost:8765/ws');
 *
 * // NEW:
 * const { isConnected, subscribe } = useWebSocketContext();
 * useEffect(() => {
 *   const unsubscribe = subscribe('player_state', (message) => {
 *     console.log(message.data);
 *   });
 *   return unsubscribe;
 * }, [subscribe]);
 * ```
 *
 * The new WebSocketContext provides:
 * - Single shared WebSocket connection (no duplication)
 * - Subscription-based message handling
 * - Automatic reconnection with exponential backoff (via WebSocketManager)
 * - Message queueing during disconnection
 * - Centralized error handling (Phase 3c integration)
 */

import { useWebSocketContext } from '../contexts/WebSocketContext';

/**
 * Adapter interface for backward compatibility
 */
export interface UseWebSocketReturn {
  connected: boolean;
  lastMessage: string | null;
  sendMessage: (message: any) => void;
}

/**
 * Deprecated hook - adapts new WebSocketContext to old interface
 * Phase 4c: This is now a thin compatibility wrapper
 */
export const useWebSocket = (url: string): UseWebSocketReturn => {
  // Note: url parameter is ignored since WebSocketContext uses a shared connection
  // This maintains backward compatibility while delegating to the centralized context

  const { isConnected, send } = useWebSocketContext();

  console.warn(
    '⚠️  useWebSocket is deprecated. Use useWebSocketContext() instead. ' +
    'See comments in src/hooks/useWebSocket.ts for migration guide.'
  );

  return {
    connected: isConnected,
    lastMessage: null, // Not tracked in new context (use subscribe instead)
    sendMessage: send
  };
};