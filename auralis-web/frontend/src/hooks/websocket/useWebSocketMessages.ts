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
import {
  useWebSocketContext,
  type MessageHandler,
  type TypedMessageHandler,
} from '@/contexts/WebSocketContext';
import type { WebSocketMessageType } from '@/types/websocket';

/** The `subscribe` function of a WebSocketContext value. */
export type SubscribeFn = ReturnType<typeof useWebSocketContext>['subscribe'];

/** One handler per message type, each narrowed to that type's message (#5636). */
export type MessageHandlers = {
  [K in WebSocketMessageType]?: TypedMessageHandler<K>;
};

/**
 * The single implementation of the subscription lifecycle: ref-held handlers,
 * an order-independent type key, and an effect that depends only on that key
 * and on `subscribe` (#4668, #5621).
 *
 * Context-free so a hook that was handed a WebSocketContext value (rather than
 * reading it itself) can reuse it: pass that value's `subscribe`. Everything
 * else should use useWebSocketMessages.
 *
 * `subscribe` is identity-stable across connect/disconnect/error status
 * transitions, so those do not resubscribe; a genuinely new `subscribe` does.
 * Handler identity changes never resubscribe, which is what lets a caller pass
 * inline closures over fresh props.
 */
export function useMessageSubscriptions(subscribe: SubscribeFn, handlers: MessageHandlers): void {
  // Ref so inline handlers do not resubscribe on every render.
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  // Order-independent, value-stable key so inline literals or reordering
  // don't churn the subscription (mirrors the prior hook's #2487 / #3366 fixes).
  const messageTypesKey = Object.keys(handlers).sort().join('\x00');

  useEffect(() => {
    // Recover the (sorted) types from the stable key so the effect depends only
    // on messageTypesKey + subscribe — no exhaustive-deps escape hatch needed.
    const unsubscribes = messageTypesKey
      .split('\x00')
      .filter(Boolean)
      .map((type) => {
        // `type` is recovered from a string key, so the per-type handler can
        // only be called through the wide dispatch signature. dispatchMessage
        // delivers a message of exactly this type to this subscription.
        const stable: MessageHandler = (message) =>
          (handlersRef.current[type as WebSocketMessageType] as MessageHandler | undefined)?.(message);
        return subscribe(type as WebSocketMessageType, stable);
      });

    return () => {
      for (const unsubscribe of unsubscribes) unsubscribe();
    };
  }, [messageTypesKey, subscribe]);
}

export function useWebSocketMessages<K extends WebSocketMessageType>(
  messageTypes: K[],
  callback: TypedMessageHandler<K>
): void {
  const { subscribe } = useWebSocketContext();
  useMessageSubscriptions(
    subscribe,
    Object.fromEntries(messageTypes.map((type) => [type, callback])) as MessageHandlers
  );
}
