/**
 * useWebSocketMessages Hook
 *
 * Subscribe to one or more WebSocket message types, backed by the single
 * WebSocketContext subscription system (#4380). Automatically unsubscribes on
 * unmount.
 *
 * Replaces the former `useWebSocketSubscription`, which routed through a
 * module-level singleton (`WebSocketManager`) that was never armed in
 * production (`setWebSocketManager` had no production caller), leaving its
 * consumers permanently in the "manager not available" branch.
 *
 * WebSocketContext.subscribe registers handlers in a persistent ref with stable
 * identity, so it is available immediately (no startup-race deferral) and
 * survives reconnects automatically — the prior hook's manager-version /
 * manager-ready machinery is no longer needed.
 *
 * The callback is held in a ref so passing an inline arrow does not tear down
 * and rebuild the subscription every render. The dependency key is order-
 * independent so `['a','b']` and `['b','a']` don't force a resubscribe.
 */

import { useEffect, useRef } from 'react';
import { useWebSocketContext, type MessageHandler } from '@/contexts/WebSocketContext';
import type { WebSocketMessage, WebSocketMessageType } from '@/types/websocket';

export function useWebSocketMessages(
  messageTypes: WebSocketMessageType[],
  callback: (message: WebSocketMessage) => void
): void {
  const { subscribe } = useWebSocketContext();

  // Ref so an inline callback does not resubscribe on every render.
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  // Order-independent, value-stable key so inline array literals or reordering
  // don't churn the subscription (mirrors the prior hook's #2487 / #3366 fixes).
  const messageTypesKey = [...messageTypes].sort().join('\x00');

  useEffect(() => {
    const stable: MessageHandler = (message) =>
      callbackRef.current(message as WebSocketMessage);

    // Recover the (sorted) types from the stable key so the effect depends only
    // on messageTypesKey + subscribe — no exhaustive-deps escape hatch needed.
    const unsubscribes = messageTypesKey
      .split('\x00')
      .filter(Boolean)
      .map((type) => subscribe(type as WebSocketMessageType, stable));

    return () => {
      for (const unsubscribe of unsubscribes) unsubscribe();
    };
  }, [messageTypesKey, subscribe]);
}
